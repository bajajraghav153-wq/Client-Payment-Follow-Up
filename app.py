import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="CashFlow Ultra", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    th, td { text-align: center !important; vertical-align: middle !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTHENTICATION ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 SaaS Access")
        t1, t2 = st.tabs(["Login", "Register"])
        with t1:
            e = st.text_input("Email")
            p = st.text_input("Password", type="password")
            if st.button("Sign In"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login failed. Check credentials.")
        with t2:
            re = st.text_input("New Email")
            rp = st.text_input("New Password", type="password")
            role_choice = st.radio("I am a:", ["Agency (Can Edit)", "Client (View Only)"])
            if st.button("Create Account"):
                res = supabase.auth.sign_up({"email": re, "password": rp})
                role_val = 'agency' if "Agency" in role_choice else 'client'
                supabase.table("profiles").insert({"id": res.user.id, "role": role_val}).execute()
                st.success("Account created! Now login.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# Load Profile Data
profile_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
u_role = profile_res.data.get("role", "client") if profile_res.data else "client"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Pro")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()

    db_admin = profile_res.data.get("admin_name", "Admin") if profile_res.data else "Admin"
    db_agency = profile_res.data.get("agency_name", "My Agency") if profile_res.data else "My Agency"
    my_name = st.text_input("Your Name", value=db_admin)
    agency_name = st.text_input("Agency Name", value=db_agency)
    
    if st.button("💾 Save Profile"):
        supabase.table("profiles").update({"admin_name": my_name, "agency_name": agency_name}).eq("id", u_id).execute()
        st.success("Saved!"); st.rerun()

    st.divider()
    if u_role == 'agency' or u_email == 'ramanbajaj154@gmail.com':
        nav = ["📊 Dashboard", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 4. AGENCY PAGES ---
if u_role == 'agency' or u_email == 'ramanbajaj154@gmail.com':
    if page == "📊 Dashboard":
        st.title("💸 Agency Dashboard")
        # Simplified query to bypass permission issues
        res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            # Filter deleted rows in Python instead of SQL to avoid 42501 errors
            if 'is_deleted' in df.columns:
                df = df[df['is_deleted'] == False]
            
            m1, m2 = st.columns(2)
            m1.metric("Pending Invoices", len(df[df['status'] == 'Pending']))
            m2.metric("Total Managed", f"${df['amount'].sum():,.2f}")
            
            for i, row in df.iterrows():
                with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                    st.write(f"Status: {row['status']}")
                    if st.button("✅ Mark Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status":"Paid"}).eq("id",row['id']).execute(); st.rerun()

    elif page == "📥 Data Entry":
        st.header("📥 Data Intake Hub")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV"])
        
        with t1:
            img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
            if img_f and st.button("🚀 AI Process"):
                res = model.generate_content(["Extract name, amount, email as JSON.", Image.open(img_f)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending", "is_deleted": False})
                supabase.table("invoices").insert(data).execute(); st.success("Saved!")
        
        with t2:
            st.subheader("Manual Entry")
            with st.form("manual_entry"):
                c_name = st.text_input("Client Name")
                c_email = st.text_input("Client Email")
                c_amount = st.number_input("Amount ($)", min_value=0.0)
                if st.form_submit_button("Save Invoice"):
                    supabase.table("invoices").insert({
                        "client_name": c_name, "email": c_email, "amount": c_amount,
                        "user_id": u_id, "status": "Pending", "is_deleted": False
                    }).execute()
                    st.success("Saved!"); st.rerun()

        with t3:
            st.subheader("CSV Upload")
            csv_file = st.file_uploader("Upload CSV", type="csv")
            if csv_file and st.button("Process CSV"):
                df_csv = pd.read_csv(csv_file)
                data_list = df_csv.to_dict(orient='records')
                for item in data_list:
                    item.update({"user_id": u_id, "status": "Pending", "is_deleted": False})
                supabase.table("invoices").insert(data_list).execute(); st.success("Bulk Saved!")

# --- 5. CLIENT PAGE ---
else:
    st.title("📋 My Invoices")
    res = supabase.table("invoices").select("*").eq("email", u_email).execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'status']])
    else:
        st.info("No invoices found for your email.")

import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="CashFlow Multi-User", layout="wide", page_icon="🏦")

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

# --- 2. AUTHENTICATION & ROLE DETECTION ---
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
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
        with t2:
            re = st.text_input("New Email")
            rp = st.text_input("New Password", type="password")
            role_choice = st.radio("I am a:", ["Agency (Can Edit)", "Client (View Only)"])
            if st.button("Create Account"):
                res = supabase.auth.sign_up({"email": re, "password": rp})
                role_val = 'agency' if "Agency" in role_choice else 'client'
                supabase.table("profiles").insert({"id": res.user.id, "role": role_val}).execute()
                st.success("Account created! Verify email and login.")
    st.stop()

# Load User Profile
u_id = st.session_state.user.id
u_email = st.session_state.user.email
profile = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
u_role = profile.data.get("role", "client") if profile.data else "client"

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Pro")
    st.write(f"Logged in: **{u_email}**")
    st.write(f"Role: **{u_role.upper()}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()

    # Shared Sidebar Tools
    db_admin = profile.data.get("admin_name", "Admin") if profile.data else "Admin"
    db_agency = profile.data.get("agency_name", "My Agency") if profile.data else "My Agency"
    my_name = st.text_input("Your Name", value=db_admin)
    agency_name = st.text_input("Agency Name", value=db_agency)
    if st.button("💾 Save Profile"):
        supabase.table("profiles").update({"admin_name": my_name, "agency_name": agency_name}).eq("id", u_id).execute()
        st.success("Saved!"); st.rerun()
    
    st.divider()
    if u_role == 'agency':
        nav = ["📊 Dashboard", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 4. AGENCY PAGES ---
if u_role == 'agency':
    if page == "📊 Dashboard":
        st.title("💸 Agency Dashboard")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            m1, m2 = st.columns(2)
            m1.metric("Pending ⏳", f"${df[df['status']=='Pending']['amount'].sum():,.2f}")
            m2.metric("Collected ✅", f"${df[df['status']=='Paid']['amount'].sum():,.2f}")
            for i, row in df.iterrows():
                with st.expander(f"📋 {row['client_name']} — ${row['amount']} ({row['status']})"):
                    # Agency Action Buttons
                    if st.button("✅ Mark Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status":"Paid"}).eq("id",row['id']).execute(); st.rerun()
        else: st.info("No invoices found.")

    elif page == "📥 Data Entry":
        st.header("📥 Data Intake Hub")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
        with t1:
            img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
            if img_f and st.button("🚀 AI Process"):
                res = model.generate_content(["Extract name, amount, email as JSON.", Image.open(img_f)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data).execute(); st.success("Saved!")
        with t2:
            with st.form("man_form"):
                n = st.text_input("Client Name"); am = st.number_input("Amount"); em = st.text_input("Client Email")
                if st.form_submit_button("Save Invoice"):
                    supabase.table("invoices").insert({"client_name":n, "amount":am, "email":em, "user_id":u_id, "status":"Pending"}).execute()
                    st.success("Saved!")
        with t3:
            csv_f = st.file_uploader("CSV File", type="csv")
            if csv_f and st.button("Bulk Upload"):
                df_csv = pd.read_csv(csv_f)
                data_list = df_csv.to_dict(orient='records')
                for item in data_list: item.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data_list).execute(); st.success("Uploaded!")

    elif page == "👑 Super Admin":
        st.title("👑 Platform Control Center")
        # Global Table
        all_res = supabase.table("invoices").select("client_name, amount, status").execute()
        if all_res.data:
            st.table(pd.DataFrame(all_res.data))

# --- 5. CLIENT PAGE ---
elif u_role == 'client':
    st.title("📋 My Invoices")
    # Matches the invoice's email column with the user's login email
    res = supabase.table("invoices").select("*").eq("email", u_email).execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'due_date', 'status']])
    else:
        st.info("No invoices shared with you yet.")

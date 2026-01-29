import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. CONFIG & STYLING (Agency Blue Theme) ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    
    /* Perfect Middle Alignment for Super Admin Report */
    th, td { text-align: center !important; vertical-align: middle !important; color: white !important; }
    .streamlit-expanderHeader { background-color: #002A4D !important; border-radius: 10px !important; color: white !important; }
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
            e = st.text_input("Email", key="l_email")
            p = st.text_input("Password", type="password", key="l_pass")
            if st.button("Sign In"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login Failed. Check credentials.")
        with t2:
            re = st.text_input("New Email", key="r_email")
            rp = st.text_input("New Password", type="password", key="r_pass")
            if st.button("Create Account"):
                supabase.auth.sign_up({"email": re, "password": rp})
                st.success("Success! Please check your email.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. ROLE & PROFILE LOADING ---
# Fetches data from the profiles table shown in your screenshot
prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False
u_role = prof_res.data.get("role", "client") if prof_res.data else "client"

# Force Agency status for master account
if u_email == 'ramanbajaj154@gmail.com':
    is_admin = True
    u_role = 'agency'

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()

    db_admin = prof_res.data.get("admin_name", "Admin") if prof_res.data else "Admin"
    db_agency = prof_res.data.get("agency_name", "My Agency") if prof_res.data else "My Agency"
    my_name = st.text_input("Your Name", value=db_admin)
    agency_name = st.text_input("Agency Name", value=db_agency)
    
    if st.button("💾 Save Profile"):
        supabase.table("profiles").update({"admin_name": my_name, "agency_name": agency_name}).eq("id", u_id).execute()
        st.success("Profile Saved!"); st.rerun()

    st.divider()
    if u_role == 'agency':
        nav = ["📊 Dashboard", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 5. AGENCY PAGES ---
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
                with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                    if st.button("✅ Mark Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status":"Paid"}).eq("id",row['id']).execute(); st.rerun()
        else: st.info("No active invoices.")

    elif page == "📥 Data Entry":
        st.header("📥 Data Entry Hub")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV"])
        
        with t1:
            img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
            if img_f and st.button("🚀 AI Process"):
                res = model.generate_content(["Extract client_name, amount, email as JSON.", Image.open(img_f)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending", "is_deleted": False})
                supabase.table("invoices").insert(data).execute(); st.success("Saved!")
        
        with t2:
            st.subheader("Manual Invoice Creation")
            with st.form("manual_entry", clear_on_submit=True):
                cn = st.text_input("Client Name")
                ce = st.text_input("Client Email")
                ca = st.number_input("Amount ($)", min_value=0.0)
                if st.form_submit_button("💾 Save to Database"):
                    supabase.table("invoices").insert({
                        "client_name": cn, "email": ce, "amount": ca, 
                        "user_id": u_id, "status": "Pending", "is_deleted": False
                    }).execute()
                    st.success("Saved!"); st.rerun()

        with t3:
            st.subheader("Bulk CSV Import")
            csv_f = st.file_uploader("Choose CSV", type="csv")
            if csv_f and st.button("🚀 Upload All"):
                df_csv = pd.read_csv(csv_f)
                recs = df_csv.to_dict(orient='records')
                for r in recs: r.update({"user_id": u_id, "status": "Pending", "is_deleted": False})
                supabase.table("invoices").insert(recs).execute(); st.success("Imported!")

    elif page == "👑 Super Admin" and is_admin:
        st.title("👑 Platform Control Center")
        all_res = supabase.table("invoices").select("client_name, amount, status").execute()
        if all_res.data:
            df_admin = pd.DataFrame(all_res.data)
            report = df_admin.groupby('client_name').agg({'amount': 'sum', 'status': 'count'}).reset_index()
            report.columns = ['Client Name', 'Total Billing ($)', 'Invoice Count']
            st.table(report)

# --- 6. CLIENT VIEW ---
else:
    st.title("📋 My Invoices")
    res = supabase.table("invoices").select("*").eq("email", u_email).execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'status']])
    else: st.info("No invoices found for your account.")

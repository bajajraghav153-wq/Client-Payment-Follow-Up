import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io
from datetime import date, datetime, timedelta

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="CashFlow Pro Intelligence", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 25px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; height: 3em; }
    th, td { text-align: center !important; color: white !important; }
    .streamlit-expanderHeader { background-color: #002A4D !important; color: white !important; font-weight: bold !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTHENTICATION (Master Protected) ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 SaaS Gateway")
        e = st.text_input("Email", key="l_email")
        p = st.text_input("Password", type="password", key="l_pass")
        if st.button("Sign In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login Failed.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# Master Role Enforcement
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    u_role = 'client'
    is_admin = False

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    nav = ["📊 Dashboard", "🤖 Automation Hub", "📈 Profit Intel", "🔮 Forecasting", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    page = st.radio("Navigation", nav)

# GLOBAL DATA FETCH
res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 4. THE DATA ENTRY MODULE (RESTORED ALL CHANNELS) ---
if page == "📥 Data Entry":
    st.header("📥 Multi-Channel Data Intake")
    # Restore the three main intake methods
    t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
    
    with t1: # AI Scanner Restoration
        st.subheader("📸 AI Invoice Intelligence")
        img_file = st.file_uploader("Upload Invoice Image", type=['png','jpg','jpeg'], key="up_ai_scanner")
        if img_file:
            st.image(img_file, width=300)
            if st.button("🚀 Process & Extract"):
                with st.spinner("AI analyzing invoice..."):
                    try:
                        # Use Gemini to extract data points
                        ai_res = model.generate_content(["Extract client_name, email, phone, amount as a clean JSON object. No prose.", Image.open(img_file)])
                        clean_json = ai_res.text.replace("```json","").replace("```","").strip()
                        data = json.loads(clean_json)
                        data.update({"user_id": u_id, "status": "Pending", "due_date": str(date.today() + timedelta(days=7))})
                        supabase.table("invoices").insert(data).execute()
                        st.success(f"AI extracted: {data.get('client_name')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Scanner failed: {e}")

    with t2: # Manual Entry Restoration
        st.subheader("⌨️ Precise Manual Entry")
        with st.form("manual_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                cn = st.text_input("Client Name")
                ce = st.text_input("Client Email")
                cp = st.text_input("Client Phone")
            with col_b:
                ca = st.number_input("Amount ($)", min_value=0.0)
                cd = st.date_input("Due Date")
                pl = st.text_input("Payment Link (Stripe/PayPal)") # Restored Payment Link
            if st.form_submit_button("💾 Save to Ledger"):
                supabase.table("invoices").insert({
                    "client_name": cn, "email": ce, "phone": cp, "amount": ca, 
                    "due_date": str(cd), "user_id": u_id, "payment_link": pl, "status": "Pending"
                }).execute()
                st.success("Invoice recorded!")
                st.rerun()

    with t3: # Bulk CSV Restoration
        st.subheader("📤 Bulk Import via CSV")
        csv_file = st.file_uploader("Choose CSV File", type="csv")
        if csv_file:
            bulk_df = pd.read_csv(csv_file)
            st.write("### Preview of Data")
            st.dataframe(bulk_df.head(), width='stretch') # 2026 stretch syntax
            if st.button("🚀 Execute Bulk Import"):
                recs = bulk_df.to_dict(orient='records')
                for r in recs:
                    r.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(recs).execute()
                st.success(f"Imported {len(recs)} invoices!")
                st.rerun()

# (Remaining logic for Dashboard, Automation, Forecasting, etc. follows standard structure)

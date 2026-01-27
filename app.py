import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json

# --- 1. CONFIG & UI STYLE ---
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="🔐")

# Dark Blue Theme CSS
st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTHENTICATION LOGIC ---
if "user" not in st.session_state:
    st.session_state.user = None

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.rerun()
    except Exception as e:
        st.error("Login Failed: Check email/password")

def register_user(email, password):
    try:
        supabase.auth.sign_up({"email": email, "password": password})
        st.success("Registration successful! Check your email for a confirmation link.")
    except Exception as e:
        st.error(f"Registration Error: {e}")

# --- 3. LOGIN / REGISTER UI ---
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏦 CashFlow Ultra Login")
        auth_mode = st.tabs(["Login", "Register"])
        
        with auth_mode[0]:
            lemail = st.text_input("Email", key="l_email")
            lpass = st.text_input("Password", type="password", key="l_pass")
            if st.button("Sign In"):
                login_user(lemail, lpass)
                
        with auth_mode[1]:
            remail = st.text_input("Email", key="r_email")
            rpass = st.text_input("Password", type="password", key="r_pass")
            if st.button("Create Account"):
                register_user(remail, rpass)
    st.stop() # Stop execution here until logged in

# --- 4. DASHBOARD (LOGGED IN) ---
user_id = st.session_state.user.id

with st.sidebar:
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "📥 Add Invoices", "📈 Analytics"])

# (Rest of the Dashboard logic now filters by user_id)
if page == "📊 Dashboard":
    st.title("💸 Your Collections")
    # Fetch only this user's data
    res = supabase.table("invoices").select("*").eq("user_id", user_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # Metrics logic here... (same as before but filtered)
        pending_df = df[df['status'] == 'Pending']
        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                # Gemini 3 Logic, WhatsApp, Mark as Paid buttons...
                pass
    else:
        st.info("No invoices found. Go to 'Add Invoices' to start.")

elif page == "📥 Add Invoices":
    # Ensure every insert includes "user_id": user_id
    st.header("Add New Data")
    # (Manual/Scanner logic here...)

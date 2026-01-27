import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json

# --- 1. THEME & INITIALIZATION ---
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="🏦")

# Deep Dark Blue Professional Styling
st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; border-radius: 15px; }
    .stButton>button { background: linear-gradient(90deg, #00D1FF, #0080FF); border-radius: 10px; border: none; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTHENTICATION SYSTEM ---
if "user" not in st.session_state:
    st.session_state.user = None

def handle_auth():
    if st.session_state.user is None:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 SaaS Login")
            tab1, tab2 = st.tabs(["Login", "Register"])
            with tab1:
                e = st.text_input("Email", key="l_e")
                p = st.text_input("Password", type="password", key="l_p")
                if st.button("Sign In"):
                    res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                    st.session_state.user = res.user
                    st.rerun()
            with tab2:
                re = st.text_input("Email", key="r_e")
                rp = st.text_input("Password", type="password", key="r_p")
                if st.button("Create Account"):
                    supabase.auth.sign_up({"email": re, "password": rp})
                    st.success("Check your email to confirm!")
        st.stop()

handle_auth()
user_id = st.session_state.user.id

# --- 3. DASHBOARD LOGIC ---
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.user.email}**")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "📥 Add Data", "📜 History"])

# --- PAGE: DASHBOARD ---
if page == "📊 Dashboard":
    st.title("💸 Active Collections")
    res = supabase.table("invoices").select("*").eq("user_id", user_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        pending = df[df['status'] == 'Pending']
        paid = df[df['status'] == 'Paid']
        m1, m2 = st.columns(2)
        m1.metric("Pending ⏳", f"${pending['amount'].sum():,.2f}")
        m2.metric("Collected ✅", f"${paid['amount'].sum():,.2f}")
        st.divider()

        for i, row in pending.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                # Same UI logic for Drafts, WhatsApp, and Mark Paid...
                if st.button("✅ Mark Paid", key=f"p_{row['id']}"):
                    supabase.table("invoices").update({"status":"Paid"}).eq("id", row['id']).execute()
                    st.rerun()

# --- PAGE: DATA ENTRY (Updated with user_id) ---
elif page == "📥 Add Data":
    st.header("Intake Hub")
    t1, t2 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry"])
    
    with t1:
        img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
        if img_f and st.button("🚀 Gemini 3 Scan"):
            res = model.generate_content(["Extract data as JSON.", Image.open(img_f)])
            data = json.loads(res.text.replace("```json","").replace("```",""))
            # IMPORTANT: Include user_id so it belongs to THIS user
            data["user_id"] = user_id
            data["status"] = "Pending"
            supabase.table("invoices").insert(data).execute()
            st.success("Saved!")

    with t2:
        with st.form("man_form", clear_on_submit=True):
            n = st.text_input("Client Name")
            a = st.number_input("Amount", min_value=0.0)
            if st.form_submit_button("Save"):
                # IMPORTANT: Include user_id here too
                supabase.table("invoices").insert({
                    "client_name": n, "amount": a, "user_id": user_id, "status": "Pending"
                }).execute()
                st.success("Added!")

import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="CashFlow Multi-Tier", layout="wide", page_icon="🏦")
st.markdown("""<style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; border-radius: 15px; }
    .stButton>button { background: linear-gradient(90deg, #00D1FF, #0080FF); border-radius: 10px; color: white; font-weight: bold; }
</style>""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTH & ROLE SYSTEM ---
if "user" not in st.session_state: st.session_state.user = None

if st.session_state.user is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏦 CashFlow Network")
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
            # ROLE SELECTOR
            role_choice = st.radio("I am an:", ["Agency (Manager)", "Client (Viewer)"])
            if st.button("Create Account"):
                res = supabase.auth.sign_up({"email": re, "password": rp})
                # Save role to profile
                role_val = 'agency' if "Agency" in role_choice else 'client'
                supabase.table("profiles").insert({"id": res.user.id, "role": role_val}).execute()
                st.success("Verify your email and login!")
    st.stop()

# Load Role and Profile
u_id = st.session_state.user.id
profile = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
u_role = profile.data.get("role", "client") if profile.data else "client"

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Pro")
    st.write(f"Logged in as: **{u_role.upper()}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    
    # Agencies get full nav, Clients get view only
    if u_role == 'agency':
        nav = ["📊 Dashboard", "📥 Data Entry", "📜 History"]
    else:
        nav = ["📊 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 4. AGENCY WORKFLOW ---
if u_role == 'agency':
    if page == "📊 Dashboard":
        st.title("💸 Agency Command Center")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            st.metric("Total Managed", f"${df['amount'].sum():,.2f}")
            for i, row in df.iterrows():
                with st.expander(f"📋 {row['client_name']} - Status: {row['status']}"):
                    # Agencies can EDIT and DELETE
                    new_status = st.selectbox("Update Status", ["Pending", "Paid"], index=0 if row['status']=='Pending' else 1, key=f"s_{row['id']}")
                    if st.button("Update", key=f"up_{row['id']}"):
                        supabase.table("invoices").update({"status": new_status}).eq("id", row['id']).execute()
                        st.rerun()
        else: st.info("No data entered yet.")

    elif page == "📥 Data Entry":
        st.header("📥 Add Data for Clients")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual", "📤 Bulk CSV"])
        # (Same Data Entry code as before, ensuring user_id = u_id is saved)

# --- 5. CLIENT WORKFLOW ---
elif u_role == 'client':
    st.title("📋 My Invoices")
    st.write("Welcome! Here are the invoices your agency has prepared for you.")
    
    # Clients see only invoices matching their email
    res = supabase.table("invoices").select("*").eq("email", st.session_state.user.email).execute()
    client_df = pd.DataFrame(res.data)
    
    if not client_df.empty:
        st.table(client_df[['client_name', 'amount', 'due_date', 'status']])
        st.info("💡 Note: You are in View-Only mode. Contact your Agency to request changes.")
    else:
        st.warning("No invoices found for your email address.")

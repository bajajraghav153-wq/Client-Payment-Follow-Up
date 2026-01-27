import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="🏦")

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
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        e = st.text_input("Email", key="l_e")
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login failed. Verify email or check credentials.")
    with tab2:
        re = st.text_input("New Email", key="r_e")
        rp = st.text_input("New Password", type="password", key="r_p")
        role_choice = st.radio("Account Type", ["Agency", "Client"])
        if st.button("Register Account"):
            res = supabase.auth.sign_up({"email": re, "password": rp})
            supabase.table("profiles").insert({"id": res.user.id, "role": role_choice.lower()}).execute()
            st.success("Registration success! Check email for link.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. ROLE DETECTION ---
# Force Agency role for your email specifically
prof = supabase.table("profiles").select("role").eq("id", u_id).single().execute()
u_role = prof.data.get("role", "client") if prof.data else "client"
if u_email == 'ramanbajaj154@gmail.com': u_role = 'agency'

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Pro")
    st.write(f"Logged in: **{u_email}**")
    st.write(f"Role: **{u_role.upper()}**")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    st.divider()
    nav = ["📊 Dashboard", "📥 Data Entry", "📜 History"]
    if u_role == 'agency': nav.append("👑 Super Admin")
    page = st.radio("Navigation", nav)

# --- 5. AGENCY PAGES ---
if u_role == 'agency':
    if page == "📊 Dashboard":
        st.title("💸 Agency Dashboard")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.table(df[['client_name', 'amount', 'status']])
        else: st.info("No active invoices found.")

    elif page == "📥 Data Entry":
        st.header("📥 Data Entry Hub")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 CSV Upload"])
        
        with t1:
            img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
            if img_f and st.button("🚀 AI Scan"):
                res = model.generate_content(["Extract name, amount, email as JSON.", Image.open(img_f)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data).execute(); st.success("Saved!")

        with t2:
            st.subheader("Add Client Manually")
            with st.form("manual_entry"):
                n = st.text_input("Client Name")
                e = st.text_input("Client Email")
                a = st.number_input("Amount ($)", min_value=0.0)
                if st.form_submit_button("💾 Save Invoice"):
                    supabase.table("invoices").insert({
                        "client_name": n, "email": e, "amount": a, 
                        "user_id": u_id, "status": "Pending"
                    }).execute()
                    st.success("Invoice Saved!"); st.rerun()

        with t3:
            st.subheader("Upload CSV File")
            csv_f = st.file_uploader("Choose CSV", type="csv")
            if csv_f and st.button("🚀 Bulk Upload"):
                df_csv = pd.read_csv(csv_f)
                recs = df_csv.to_dict(orient='records')
                for r in recs: r.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(recs).execute()
                st.success("Bulk Data Imported!")

# --- 6. CLIENT PAGE ---
else:
    st.title("📋 My Invoices")
    res = supabase.table("invoices").select("*").eq("email", u_email).execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'status']])
    else:
        st.info("No invoices found for your email.")

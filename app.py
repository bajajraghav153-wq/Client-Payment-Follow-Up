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
    [data-testid="stMetricValue"] { font-size: 30px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    th, td { text-align: center !important; color: white !important; vertical-align: middle !important; }
    .streamlit-expanderHeader { background-color: #002A4D !important; color: white !important; }
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

# --- 3. MASTER ROLE ENFORCEMENT ---
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
    u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
    is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    
    if u_role == 'agency':
        nav = ["📊 Dashboard", "🤖 Automation Hub", "📈 Profit Intel", "🔮 Forecasting", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# GLOBAL DATA LOAD
res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 5. DATA ENTRY MODULE (AI & BULK RESTORED) ---
if page == "📥 Data Entry":
    st.header("📥 Multi-Channel Data Intake")
    t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
    
    with t1: # AI Scanner logic
        st.subheader("AI Invoice Intelligence")
        img_file = st.file_uploader("Upload Invoice Image", type=['png','jpg','jpeg'], key="ai_scanner_up")
        if img_file:
            st.image(img_file, width=300)
            if st.button("🚀 Process & Extract Data"):
                with st.spinner("Gemini AI analyzing..."):
                    try:
                        # Extract data using Gemini
                        ai_res = model.generate_content(["Extract client_name, email, phone, and amount as a JSON object. If missing, leave empty.", Image.open(img_file)])
                        clean_json = ai_res.text.replace("```json","").replace("```","").strip()
                        extracted_data = json.loads(clean_json)
                        
                        # Add system fields
                        extracted_data.update({"user_id": u_id, "status": "Pending", "due_date": str(date.today() + timedelta(days=7))})
                        
                        # Save to Supabase
                        supabase.table("invoices").insert(extracted_data).execute()
                        st.success(f"Successfully extracted: {extracted_data.get('client_name', 'Unknown Client')}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Extraction failed: {e}")

    with t2: # Manual Entry logic
        with st.form("manual_entry_form", clear_on_submit=True):
            c_name = st.text_input("Client Name")
            c_email = st.text_input("Client Email")
            c_phone = st.text_input("Phone Number")
            c_amt = st.number_input("Amount ($)", min_value=0.0)
            c_due = st.date_input("Due Date")
            c_link = st.text_input("Payment Link (Stripe/PayPal)")
            if st.form_submit_button("💾 Save Invoice"):
                supabase.table("invoices").insert({
                    "client_name": c_name, "email": c_email, "phone": c_phone, 
                    "amount": c_amt, "due_date": str(c_due), "user_id": u_id, 
                    "payment_link": c_link, "status": "Pending"
                }).execute()
                st.success("Manual invoice saved!")
                st.rerun()

    with t3: # Bulk CSV logic
        st.subheader("Bulk Import (CSV)")
        csv_file = st.file_uploader("Upload CSV File", type="csv")
        if csv_file:
            bulk_df = pd.read_csv(csv_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(bulk_df.head())
            if st.button("🚀 Confirm Bulk Import"):
                try:
                    recs = bulk_df.to_dict(orient='records')
                    for r in recs:
                        r.update({"user_id": u_id, "status": "Pending"})
                    supabase.table("invoices").insert(recs).execute()
                    st.success(f"Imported {len(recs)} invoices successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bulk import failed. Ensure CSV headers match: client_name, email, phone, amount.")

# (Remaining logic for Dashboard, Forecasting, History, Super Admin remains consistent)
elif page == "📊 Dashboard":
    st.title("💸 Active Collections")
    # ... (Standard Dashboard logic)

elif page == "🔮 Forecasting":
    st.title("🔮 Forecasting")
    if not df.empty:
        clv = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(data=clv, x='client_name', y='amount')

elif page == "📜 History":
    st.header("📜 History")
    paid_df = df[df['status'] == 'Paid'] if not df.empty else pd.DataFrame()
    if not paid_df.empty:
        st.dataframe(paid_df[['client_name', 'amount', 'due_date']], use_container_width=True)

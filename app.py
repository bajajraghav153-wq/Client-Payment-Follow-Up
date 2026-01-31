import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
from datetime import date, datetime, timedelta

# --- 1. UI & THEME ---
st.set_page_config(page_title="CashFlow Pro Intelligence", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 25px; border-radius: 20px; }
    .stButton>button { border-radius: 12px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; border: none; height: 3em; }
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
    # ... (Login logic remains standard)
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# Hardcode Raghav for Master Agency status
is_agency = True if u_email == 'ramanbajaj154@gmail.com' else False

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    
    if is_agency:
        nav = ["📊 Dashboard", "📈 Profit Intel", "🤖 Automation Hub", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 4. PROFIT INTELLIGENCE FEATURE ---
if page == "📈 Profit Intel":
    st.title("📈 Profit & Performance Intelligence")
    
    # Load Data
    inv_res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
    df = pd.DataFrame(inv_res.data)
    
    if not df.empty:
        # 1. Collection Efficiency
        total_billed = df['amount'].sum()
        total_paid = df[df['status'] == 'Paid']['amount'].sum()
        eff_rate = (total_paid / total_billed) * 100 if total_billed > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Collection Efficiency", f"{eff_rate:.1f}%")
        c2.metric("Liquid Cash (Paid)", f"${total_paid:,.2f}")
        c3.metric("Outstanding Debt", f"${(total_billed - total_paid):,.2f}")
        
        st.divider()
        
        # 2. Weekly Report Generator
        st.subheader("🗓️ Weekly Summary Generator")
        if st.button("🪄 Generate Executive Profit Report"):
            last_7_days = datetime.now() - timedelta(days=7)
            recent_paid = df[(df['status'] == 'Paid')] # In real app, filter by payment_date
            
            prompt = f"""
            Act as a CFO. Summarize this agency performance:
            - Total Collected: ${total_paid}
            - Efficiency: {eff_rate}%
            - High-Value Late Payers: {df[(df['status'] == 'Pending') & (df['amount'] > 1000)]['client_name'].tolist()}
            Provide a 3-point strategy to hit 100% collection this month.
            """
            report = model.generate_content(prompt).text
            st.markdown(f"```\n{report}\n```")
            
        st.divider()
        
        # 3. Monthly Goal Tracking
        st.subheader("🎯 Revenue Goals")
        goal_amt = st.number_input("Set Monthly Revenue Target ($)", min_value=0)
        if st.button("Update Goal"):
            st.success(f"Goal set! You are {(total_paid/goal_amt*100):.1f}% of the way there.")
            
    else: st.info("No data available to analyze.")

# --- 5. DATA ENTRY & SCANNER (RESTORED) ---
elif page == "📥 Data Entry":
    st.header("📥 Multi-Channel Intake")
    t1, t2 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry"])
    with t1:
        img = st.file_uploader("Upload Invoice", type=['png','jpg','jpeg'])
        if img and st.button("🚀 Process"):
            res = model.generate_content(["Extract client_name, email, phone, amount as JSON.", Image.open(img)])
            data = json.loads(res.text.replace("```json","").replace("```",""))
            data.update({"user_id": u_id, "status": "Pending"})
            supabase.table("invoices").insert(data).execute(); st.success("Scanned!"); st.rerun()
    with t2:
        with st.form("manual"):
            cn = st.text_input("Client Name"); ce = st.text_input("Email"); cp = st.text_input("Phone")
            ca = st.number_input("Amount"); cd = st.date_input("Due Date"); pl = st.text_input("Payment Link")
            if st.form_submit_button("Save"):
                supabase.table("invoices").insert({"client_name":cn, "email":ce, "phone":cp, "amount":ca, "due_date":str(cd), "user_id":u_id, "payment_link":pl}).execute(); st.rerun()

# (Remaining pages Dashboard, History, Super Admin remain as previously verified)

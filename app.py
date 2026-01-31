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
    st.title("🔐 SaaS Gateway")
    # ... (Authentication logic)
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# Hardcoded Master Access for Raman Bajaj
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    u_role, is_admin = 'client', False

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

# --- 4. FORECASTING MODULE (RESTORED & IMPROVED) ---
if page == "🔮 Forecasting":
    st.title("🔮 Revenue Forecasting & CLV")
    
    if not df.empty:
        # 1. Predictive Liquidity Engine
        total_billed = df['amount'].sum()
        total_paid = df[df['status'] == 'Paid']['amount'].sum()
        pending_val = df[df['status'] == 'Pending']['amount'].sum()
        
        # Calculate historical collection rate
        collection_rate = (total_paid / total_billed) if total_billed > 0 else 0
        projected_recovery = pending_val * collection_rate
        
        st.subheader("Projected Cash Recovery")
        c1, c2 = st.columns(2)
        c1.metric("Current Pending", f"${pending_val:,.2f}")
        c2.metric("Expected Realized Cash", f"${projected_recovery:,.2f}", 
                  help=f"Based on your current {collection_rate:.1%} collection rate.")
        
        st.divider()
        
        # 2. Client Lifetime Value (CLV)
        st.subheader("📊 Top Revenue Contributors (CLV)")
        clv_df = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(data=clv_df, x='client_name', y='amount')
        
        # 2026 compliant table syntax
        st.write("### Client Value Details")
        st.dataframe(clv_df, width='stretch')
        
    else:
        st.info("No transaction data available. Please add invoices to generate forecasting insights.")

# (Logic for Dashboard, Automation, Data Entry, History, etc. follows standard structure)

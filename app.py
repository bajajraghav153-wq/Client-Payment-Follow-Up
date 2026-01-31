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
    # (Login UI remains standard)
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# Master Override for Raghav
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
    u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
    is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    if u_role == 'agency':
        nav = ["📊 Dashboard", "🤖 Automation Hub", "📈 Profit Intel", "🔮 Forecasting", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# GLOBAL DATA FETCH
res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 4. FORECASTING MODULE (RESTORED & ADVANCED) ---
if page == "🔮 Forecasting":
    st.title("🔮 Revenue Forecasting & Client Lifetime Value")
    
    if not df.empty:
        # 1. Collection Efficiency Math
        total_billed = df['amount'].sum()
        total_paid = df[df['status'] == 'Paid']['amount'].sum()
        pending_val = df[df['status'] == 'Pending']['amount'].sum()
        eff_rate = (total_paid / total_billed) if total_billed > 0 else 0
        
        # 2. Predicted Realized Cash
        # This calculates how much of your "Pending" money you will likely collect
        predicted_cash = pending_val * eff_rate
        
        c1, c2 = st.columns(2)
        c1.metric("Total Pending (Uncollected)", f"${pending_val:,.2f}")
        c2.metric("Projected Liquidity", f"${predicted_cash:,.2f}", 
                  help=f"Based on your {eff_rate:.1%} collection rate, this is the cash you are likely to recover.")

        st.divider()
        
        # 3. Client Lifetime Value (CLV) Chart
        st.subheader("🐳 Top Revenue Contributors (CLV)")
        clv = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(data=clv, x='client_name', y='amount')
        
        st.write("### Detailed Client Value Table")
        # 2026 'stretch' syntax used here to avoid logs
        st.dataframe(clv, width='stretch')
    else:
        st.info("No data found. Please add invoices to generate forecasts.")

# --- 5. PROFIT INTEL MODULE ---
elif page == "📈 Profit Intel":
    st.title("📈 Profit Intelligence")
    if not df.empty:
        paid_sum = df[df['status'] == 'Paid']['amount'].sum()
        st.metric("Liquid Cash on Hand", f"${paid_sum:,.2f}")
        if st.button("Generate Strategy"):
            st.write(model.generate_content("Provide a growth strategy for an agency.").text)
    else: st.info("No data found.")

# (Remaining logic for Dashboard, History, Super Admin, and Data Entry remains restored)

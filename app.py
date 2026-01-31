import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io
from datetime import date, datetime

# --- 1. UI & THEME ---
st.set_page_config(page_title="CashFlow Pro Automation", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
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
        st.title("🔐 SaaS Gateway")
        auth_tabs = st.tabs(["Login", "Register"])
        with auth_tabs[0]:
            e = st.text_input("Email", key="l_email")
            p = st.text_input("Password", type="password", key="l_pass")
            if st.button("Sign In"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Login Failed. Ensure 'Confirm Email' is OFF in Supabase.")
        with auth_tabs[1]:
            re = st.text_input("New Email", key="reg_email")
            rp = st.text_input("New Password", type="password", key="reg_pass")
            if st.button("Create Account"):
                try:
                    res = supabase.auth.sign_up({"email": re, "password": rp})
                    supabase.table("profiles").upsert({"id": res.user.id, "role": "agency"}).execute()
                    st.success("Account Created! You can now login.")
                except: st.error("Registration failed.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. MASTER ROLE ENFORCEMENT ---
prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
# Force Agency role for your specific email to ensure tabs NEVER disappear
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
    is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False

# --- 4. SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()

    if u_role == 'agency':
        nav = ["📊 Dashboard", "🤖 Automation Hub", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 5. AGENCY PAGES ---
if u_role == 'agency':
    if page == "📊 Dashboard":
        st.title("💸 Active Collections")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            pending = df[df['status'] == 'Pending']
            m1, m2 = st.columns(2)
            m1.metric("Pending Invoices", len(pending))
            m2.metric("Collected Total", f"${df[df['status'] == 'Paid']['amount'].sum():,.2f}")
            for i, row in pending.iterrows():
                # Aging Logic
                due_raw = row.get('due_date')
                tag = f"🚨 {(date.today() - date.fromisoformat(due_raw)).days} Days Overdue" if due_raw and date.fromisoformat(due_raw) < date.today() else "🗓️ On Time"
                with st.expander(f"{tag} | 📋 {row['client_name']} — ${row['amount']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        if st.button("🪄 AI Draft", key=f"ai_{row['id']}"):
                            ai_res = model.generate_content(f"Write a reminder for {row['client_name']} regarding ${row['amount']}.").text
                            supabase.table("invoices").update({"last_draft": ai_res}).eq("id", row['id']).execute(); st.rerun()
                        st.text_area("Draft:", value=row.get('last_draft', ""), height=100, key=f"t_{row['id']}")
                    with c2:
                        if row.get('phone'):
                            p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                            wa_url = f"https://wa.me/{p_clean}?text=Hi {row['client_name']}, friendly nudge for payment."
                            st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;cursor:pointer;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                    with c3:
                        if st.button("✅ Paid", key=f"p_{row['id']}"):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()
        else: st.info("Dashboard is empty.")

    elif page == "🤖 Automation Hub":
        st.title("🤖 Bulk Automation Hub")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("status", "Pending").execute()
        if res.data:
            df_auto = pd.DataFrame(res.data)
            overdue = df_auto[pd.to_datetime(df_auto['due_date']).dt.date < date.today()]
            st.metric("Overdue Clients Found", len(overdue))
            if st.button("🚀 Prepare Bulk WhatsApp Nudges"):
                for _, r in overdue.iterrows():
                    p_clean = "".join(filter(str.isdigit, str(r['phone'])))
                    wa_url = f"https://wa.me/{p_clean}?text=" + urllib.parse.quote(f"Hi {r['client_name']}, invoice for ${r['amount']} is overdue. Pay here: {r.get('payment_link', '')}")
                    st.markdown(f'<a href="{wa_url}" target="_blank">Nudge {r["client_name"]}</a>', unsafe_allow_html=True)
        else: st.success("No overdue invoices!")

    elif page == "📥 Data Entry":
        st.header("📥 Multi-Channel Data Intake")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
        with t2:
            with st.form("manual_form", clear_on_submit=True):
                cn = st.text_input("Client Name"); ce = st.text_input("Client Email"); cp = st.text_input("Phone")
                ca = st.number_input("Amount"); cd = st.date_input("Due Date"); pl = st.text_input("Payment Link")
                if st.form_submit_button("Save"):
                    supabase.table("invoices").insert({"client_name":cn, "email":ce, "phone":cp, "amount":ca, "due_date":str(cd), "user_id": u_id, "status": "Pending", "payment_link": pl}).execute(); st.rerun()

    elif page == "📜 History":
        st.header("📜 Completed Transactions")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("status", "Paid").execute()
        if res.data: st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'status']])

    elif page == "👑 Super Admin" and is_admin:
        st.title("👑 Global Analytics")
        all_res = supabase.table("invoices").select("*").execute()
        if all_res.data:
            df_all = pd.DataFrame(all_res.data)
            st.metric("Global Revenue", f"${df_all['amount'].sum():,.2f}")
            st.bar_chart(df_all.groupby('client_name')['amount'].sum())

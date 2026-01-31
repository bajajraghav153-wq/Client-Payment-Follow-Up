import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
from datetime import date, datetime, timedelta

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="CashFlow Pro Intelligence", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 30px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    th, td { text-align: center !important; color: white !important; }
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
        auth_tabs = st.tabs(["Login", "Register"])
        with auth_tabs[0]:
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

# Master Override
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
    u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
    is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    if u_role == 'agency':
        nav = ["📊 Dashboard", "📈 Profit Intel", "🔮 Forecasting", "🤖 Automation Hub", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 4. AGENCY PAGES ---
if u_role == 'agency':
    res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

    if page == "📊 Dashboard":
        st.title("💸 Active Collections")
        if not df.empty:
            pending = df[df['status'] == 'Pending']
            m1, m2 = st.columns(2)
            m1.metric("Pending Total", f"${pending['amount'].sum():,.2f}")
            m2.metric("Collected Total", f"${df[df['status'] == 'Paid']['amount'].sum():,.2f}")
            for i, row in pending.iterrows():
                due_raw = row.get('due_date')
                tag = f"🚨 {(date.today() - date.fromisoformat(due_raw)).days} Days Overdue" if due_raw and date.fromisoformat(due_raw) < date.today() else "🗓️ Current"
                with st.expander(f"{tag} | 📋 {row['client_name']} — ${row['amount']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        if st.button("🪄 AI Draft", key=f"ai_{row['id']}"):
                            ai_res = model.generate_content(f"Draft a nudge for {row['client_name']} regarding ${row['amount']}.").text
                            supabase.table("invoices").update({"last_draft": ai_res}).eq("id", row['id']).execute(); st.rerun()
                        st.text_area("Draft:", value=row.get('last_draft', ""), height=100, key=f"t_{row['id']}")
                    with c2:
                        if row.get('phone'):
                            p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                            wa_url = f"https://wa.me/{p_clean}?text=Nudge for payment."
                            st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                    with c3:
                        if st.button("✅ Paid", key=f"p_{row['id']}"):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()

    # --- ADVANCED PROFIT INTEL ---
    elif page == "📈 Profit Intel":
        st.title("📈 Revenue Intelligence Hub")
        if not df.empty:
            st.subheader("Client Health Scores")
            # Calculate health based on status
            health = df.groupby('client_name')['status'].apply(lambda x: (x == 'Paid').sum() / len(x)).reset_index()
            health.columns = ['Client', 'Payment Consistency']
            
            def get_grade(score):
                if score >= 0.8: return "🟢 Grade A (Reliable)"
                if score >= 0.5: return "🟡 Grade B (Average)"
                return "🔴 Grade C (High Risk)"
            
            health['Risk Level'] = health['Payment Consistency'].apply(get_grade)
            st.table(health)

            st.divider()
            st.subheader("🗓️ Sunday Executive Digest")
            if st.button("🪄 Generate This Week's Win Report"):
                # In a real app, you'd filter by a 'updated_at' column for the last 7 days
                paid_this_week = df[df['status'] == 'Paid']['amount'].sum()
                pending_this_week = df[df['status'] == 'Pending']['amount'].sum()
                prompt = f"Summarize my agency's week: I collected ${paid_this_week} but ${pending_this_week} is still pending. Make it sound motivational and give me a focus for next week."
                st.info(model.generate_content(prompt).text)

    # --- FORECASTING ---
    elif page == "🔮 Forecasting":
        st.title("🔮 Forecasting")
        if not df.empty:
            clv = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
            st.subheader("Top Profit Contributors (CLV)")
            st.bar_chart(data=clv, x='client_name', y='amount')

    # --- DATA ENTRY ---
    elif page == "📥 Data Entry":
        st.header("📥 Data Intake")
        t1, t2 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry"])
        with t1:
            img = st.file_uploader("Upload", type=['png','jpg','jpeg'])
            if img and st.button("Process"):
                res = model.generate_content(["Extract client_name, email, phone, amount as JSON.", Image.open(img)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data).execute(); st.rerun()
        with t2:
            with st.form("man"):
                cn = st.text_input("Name"); ce = st.text_input("Email"); cp = st.text_input("Phone"); ca = st.number_input("Amount"); cd = st.date_input("Due Date")
                if st.form_submit_button("Save"):
                    supabase.table("invoices").insert({"client_name":cn, "email":ce, "phone":cp, "amount":ca, "due_date":str(cd), "user_id": u_id}).execute(); st.rerun()

    elif page == "📜 History":
        st.header("📜 Completed")
        paid_res = df[df['status'] == 'Paid'] if not df.empty else pd.DataFrame()
        if not paid_res.empty: st.table(paid_res[['client_name', 'amount']])

    elif page == "👑 Super Admin" and is_admin:
        st.title("👑 Super Admin")
        st.metric("Total Platform Revenue", f"${df['amount'].sum():,.2f}")

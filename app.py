import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io
from datetime import date, datetime, timedelta

# --- 1. CONFIG & THEME (2026 Compliant) ---
st.set_page_config(page_title="CashFlow Pro Elite", layout="wide", page_icon="🚀")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 25px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; height: 3em; }
    th, td { text-align: center !important; color: white !important; }
    .streamlit-expanderHeader { background-color: #002A4D !important; color: white !important; font-weight: bold !important; }
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
            except: st.error("Login Failed. Check Supabase 'Confirm Email' setting.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. HARD-CODED ROLE ENFORCEMENT ---
# This ensures Raman Bajaj always sees all features regardless of DB lag
if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True
else:
    u_role, is_admin = 'client', False

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 Revenue Master")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    nav = ["📊 Dashboard", "🤖 Automation Hub", "📈 Profit Intel", "🔮 Forecasting", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    page = st.radio("Navigation", nav)

# GLOBAL DATA FETCH
res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 5. PAGE MODULES ---

if page == "📊 Dashboard":
    st.title("💸 Active Ledger")
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
                        ai_res = model.generate_content(f"Nudge {row['client_name']} for ${row['amount']}.").text
                        supabase.table("invoices").update({"last_draft": ai_res}).eq("id", row['id']).execute(); st.rerun()
                    st.text_area("Draft:", value=row.get('last_draft', ""), height=100, key=f"t_{row['id']}")
                with c2:
                    if row.get('phone'):
                        p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                        wa_url = f"https://wa.me/{p_clean}?text=Payment nudge."
                        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                with c3:
                    if st.button("✅ Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()

elif page == "🤖 Automation Hub":
    st.title("🤖 Bulk Automation Hub")
    if not df.empty:
        df['due_date_dt'] = pd.to_datetime(df['due_date']).dt.date
        overdue = df[(df['status'] == 'Pending') & (df['due_date_dt'] < date.today())]
        st.metric("Targeted Overdue", len(overdue))
        if not overdue.empty:
            st.dataframe(overdue[['client_name', 'amount', 'due_date']], width='stretch')
            if st.button("🚀 Trigger Bulk Nudges"):
                for _, r in overdue.iterrows():
                    p_clean = "".join(filter(str.isdigit, str(r['phone'])))
                    msg = f"Hi {r['client_name']}, your invoice for ${r['amount']} is overdue. Pay here: {r.get('payment_link', '')}"
                    wa_url = f"https://wa.me/{p_clean}?text={urllib.parse.quote(msg)}"
                    st.markdown(f'<a href="{wa_url}" target="_blank">📲 Nudge {r["client_name"]}</a>', unsafe_allow_html=True)

elif page == "📈 Profit Intel":
    st.title("📈 Profit Intelligence")
    if not df.empty:
        billed = df['amount'].sum()
        paid = df[df['status'] == 'Paid']['amount'].sum()
        eff = (paid / billed) * 100 if billed > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Collection Efficiency", f"{eff:.1f}%")
        c2.metric("Liquid Cash", f"${paid:,.2f}")
        st.subheader("🗓️ Debt Aging")
        df['days_late'] = pd.to_datetime(df['due_date']).dt.date.apply(lambda x: (date.today() - x).days if x < date.today() else 0)
        st.dataframe(df[df['status'] == 'Pending'][['client_name', 'amount', 'days_late']], width='stretch')
        if st.button("Generate Strategy"):
            st.write(model.generate_content(f"Analyze ${paid} collected vs ${billed} billed.").text)

elif page == "🔮 Forecasting":
    st.title("🔮 Forecasting")
    if not df.empty:
        clv = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(data=clv, x='client_name', y='amount')
        st.dataframe(clv, width='stretch')

elif page == "📥 Data Entry":
    st.header("📥 Data Intake")
    t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
    with t1:
        img = st.file_uploader("Upload Image", type=['png','jpg','jpeg'], key="up_ai")
        if img and st.button("🚀 Process"):
            res_ai = model.generate_content(["Extract client_name, email, phone, amount as JSON.", Image.open(img)])
            data = json.loads(res_ai.text.replace("```json","").replace("```",""))
            data.update({"user_id": u_id, "status": "Pending", "due_date": str(date.today())})
            supabase.table("invoices").insert(data).execute(); st.rerun()
    with t2:
        with st.form("manual"):
            cn = st.text_input("Name"); ce = st.text_input("Email"); cp = st.text_input("Phone")
            ca = st.number_input("Amount"); cd = st.date_input("Due Date"); pl = st.text_input("Payment Link")
            if st.form_submit_button("Save"):
                supabase.table("invoices").insert({"client_name":cn, "email":ce, "phone":cp, "amount":ca, "due_date":str(cd), "user_id":u_id, "payment_link":pl, "status":"Pending"}).execute(); st.rerun()
    with t3:
        csv = st.file_uploader("Upload CSV", type="csv")
        if csv and st.button("Confirm Import"):
            df_c = pd.read_csv(csv)
            recs = df_c.to_dict(orient='records')
            for r in recs: r.update({"user_id": u_id, "status": "Pending"})
            supabase.table("invoices").insert(recs).execute(); st.rerun()

elif page == "📜 History":
    st.header("📜 Completed Transactions")
    paid_res = df[df['status'] == 'Paid'] if not df.empty else pd.DataFrame()
    if not paid_res.empty: st.dataframe(paid_res[['client_name', 'amount', 'due_date']], width='stretch')

elif page == "👑 Super Admin" and is_admin:
    st.title("👑 Global Analytics")
    all_r = supabase.table("invoices").select("*").execute()
    if all_r.data:
        df_all = pd.DataFrame(all_r.data)
        st.metric("Total Platform Revenue", f"${df_all['amount'].sum():,.2f}")
        st.bar_chart(df_all.groupby('client_name')['amount'].sum())

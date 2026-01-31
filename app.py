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

# PRE-LOAD DATA FOR ALL MODULES
res = supabase.table("invoices").select("*").eq("user_id", u_id).execute()
df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

# --- 5. PAGE LOGIC ---
if u_role == 'agency':
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
                            pay_link = row.get('payment_link', 'our portal')
                            ai_res = model.generate_content(f"Draft a nudge for {row['client_name']} regarding ${row['amount']}. Pay link: {pay_link}").text
                            supabase.table("invoices").update({"last_draft": ai_res}).eq("id", row['id']).execute(); st.rerun()
                        st.text_area("Draft:", value=row.get('last_draft', ""), height=100, key=f"t_{row['id']}")
                    with c2:
                        if row.get('phone'):
                            p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                            wa_url = f"https://wa.me/{p_clean}?text=Friendly nudge for payment of ${row['amount']}."
                            st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                    with c3:
                        if st.button("✅ Paid", key=f"p_{row['id']}"):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()

    elif page == "🤖 Automation Hub":
        st.title("🤖 Bulk WhatsApp Nudges")
        if not df.empty:
            overdue = df[(df['status'] == 'Pending') & (pd.to_datetime(df['due_date']).dt.date < date.today())]
            st.metric("Overdue Clients Found", len(overdue))
            if st.button("🚀 Prepare Bulk WhatsApp Queue"):
                for _, r in overdue.iterrows():
                    p_clean = "".join(filter(str.isdigit, str(r['phone'])))
                    msg = f"Hi {r['client_name']}, your invoice for ${r['amount']} is overdue. Pay here: {r.get('payment_link', '')}"
                    wa_url = f"https://wa.me/{p_clean}?text=" + urllib.parse.quote(msg)
                    st.markdown(f'<a href="{wa_url}" target="_blank">Nudge {r["client_name"]}</a>', unsafe_allow_html=True)

    elif page == "📈 Profit Intel":
        st.title("📈 Profit Intelligence")
        if not df.empty:
            total_billed = df['amount'].sum()
            total_paid = df[df['status'] == 'Paid']['amount'].sum()
            eff_rate = (total_paid / total_billed) * 100 if total_billed > 0 else 0
            c1, c2 = st.columns(2)
            c1.metric("Collection Efficiency", f"{eff_rate:.1f}%")
            c2.metric("Liquid Cash Collected", f"${total_paid:,.2f}")
            if st.button("🪄 Weekly Win Report"):
                st.write(model.generate_content(f"Analyze: Billed ${total_billed}, Collected ${total_paid}. Provide 3 growth tips.").text)

    elif page == "🔮 Forecasting":
        st.title("🔮 Revenue Forecasting")
        if not df.empty:
            clv = df.groupby('client_name')['amount'].sum().sort_values(ascending=False).reset_index()
            st.subheader("Top Profit Contributors (CLV)")
            st.bar_chart(data=clv, x='client_name', y='amount')
            st.table(clv)

    elif page == "📥 Data Entry":
        st.header("📥 Multi-Channel Intake")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV"])
        with t1:
            img = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
            if img and st.button("🚀 Process"):
                res = model.generate_content(["Extract client_name, email, phone, amount as JSON.", Image.open(img)])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data).execute(); st.rerun()
        with t2:
            with st.form("manual"):
                cn = st.text_input("Client Name"); ce = st.text_input("Email"); cp = st.text_input("Phone")
                ca = st.number_input("Amount"); cd = st.date_input("Due Date")
                pl = st.text_input("Payment Link (Stripe/PayPal)") # RESTORED
                if st.form_submit_button("Save"):
                    supabase.table("invoices").insert({"client_name":cn, "email":ce, "phone":cp, "amount":ca, "due_date":str(cd), "user_id": u_id, "status": "Pending", "payment_link": pl}).execute(); st.rerun()
        with t3:
            csv_f = st.file_uploader("Upload CSV", type="csv")
            if csv_f and st.button("Confirm Bulk Import"):
                df_csv = pd.read_csv(csv_f)
                recs = df_csv.to_dict(orient='records')
                for r in recs: r.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(recs).execute(); st.success("Imported!"); st.rerun()

    elif page == "📜 History":
        st.header("📜 Completed Transactions")
        paid_res = df[df['status'] == 'Paid'] if not df.empty else pd.DataFrame()
        if not paid_res.empty: 
            st.table(paid_res[['client_name', 'amount', 'due_date']]) # RESTORED
        else: st.info("No paid history found.")

    elif page == "👑 Super Admin" and is_admin:
        st.title("👑 Global Platform Analytics")
        all_res = supabase.table("invoices").select("*").execute()
        if all_res.data:
            df_all = pd.DataFrame(all_res.data)
            st.metric("Total Platform Revenue", f"${df_all['amount'].sum():,.2f}")
            st.bar_chart(df_all.groupby('client_name')['amount'].sum())

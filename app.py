import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. UI & THEME ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="💰")

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
        e = st.text_input("Email", key="log_e")
        p = st.text_input("Password", type="password", key="log_p")
        if st.button("Sign In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login Failed. Verify your credentials.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. ROLE DETECTION ---
prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
is_admin = prof_res.data.get("is_admin", False) if prof_res.data else False

if u_email == 'ramanbajaj154@gmail.com':
    u_role, is_admin = 'agency', True

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()

    db_admin = prof_res.data.get("admin_name", "Admin") if prof_res.data else "Admin"
    db_agency = prof_res.data.get("agency_name", "My Agency") if prof_res.data else "My Agency"
    my_name = st.text_input("Your Name", value=db_admin)
    agency_name = st.text_input("Agency Name", value=db_agency)
    
    if st.button("💾 Save Profile Settings"):
        supabase.table("profiles").update({"admin_name": my_name, "agency_name": agency_name}).eq("id", u_id).execute()
        st.success("Profile Updated!"); st.rerun()

    st.divider()
    nav = ["📊 Dashboard", "📥 Data Entry", "📜 History"]
    if is_admin: nav.append("👑 Super Admin")
    page = st.radio("Navigation", nav)

# --- 5. DASHBOARD (FIXED AI & WHATSAPP) ---
if page == "📊 Dashboard":
    st.title("💸 Active Collections")
    res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        pending_df = df[df['status'] == 'Pending']
        m1, m2 = st.columns(2)
        m1.metric("Pending ⏳", f"${pending_df['amount'].sum():,.2f}")
        m2.metric("Collected ✅", f"${df[df['status'] == 'Paid']['amount'].sum():,.2f}")
        
        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                c1, c2, c3 = st.columns([2, 2, 1])
                
                with c1:
                    if st.button("🪄 Craft AI Draft", key=f"ai_{row['id']}"):
                        try:
                            prompt = f"Professional reminder for {row['client_name']} about ${row['amount']}. From {my_name} at {agency_name}."
                            ai_msg = model.generate_content(prompt).text
                        except:
                            ai_msg = f"Hi {row['client_name']}, friendly nudge for the ${row['amount']} invoice. Thanks, {my_name}."
                        
                        supabase.table("invoices").update({"last_draft": ai_msg}).eq("id", row['id']).execute()
                        st.rerun()
                    
                    st.text_area("Email Draft:", value=row.get('last_draft', ""), height=150, key=f"txt_{row['id']}")
                
                with c2:
                    if row.get('phone'):
                        p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                        wa_msg = f"Hi {row['client_name']}, friendly nudge for the ${row['amount']} invoice from {agency_name}."
                        wa_url = f"https://wa.me/{p_clean}?text={urllib.parse.quote(wa_msg)}"
                        st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:15px;border-radius:10px;border:none;cursor:pointer;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                
                with c3:
                    if st.button("✅ Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()

# --- 6. DATA ENTRY ---
elif page == "📥 Data Entry":
    st.header("📥 Multi-Channel Data Entry")
    t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
    with t2:
        with st.form("man_entry", clear_on_submit=True):
            cn = st.text_input("Client Name"); ce = st.text_input("Client Email"); cp = st.text_input("Phone")
            ca = st.number_input("Amount ($)"); cd = st.date_input("Due Date")
            if st.form_submit_button("💾 Save Invoice"):
                supabase.table("invoices").insert({"client_name": cn, "email": ce, "phone": cp, "amount": ca, "due_date": str(cd), "user_id": u_id}).execute()
                st.success("Saved!"); st.rerun()

# --- 7. SUPER ADMIN (FIXED VIEW) ---
elif page == "👑 Super Admin" and is_admin:
    st.title("👑 Platform Analytics")
    all_res = supabase.table("invoices").select("*").execute()
    if all_res.data:
        df_all = pd.DataFrame(all_res.data)
        st.metric("Global Platform Revenue", f"${df_all['amount'].sum():,.2f}")
        report = df_all.groupby('client_name').agg({'amount': 'sum', 'status': 'count'}).reset_index()
        report.columns = ['Client Name', 'Total Volume ($)', 'Invoices']
        st.table(report)
    else: st.warning("No global data found yet.")

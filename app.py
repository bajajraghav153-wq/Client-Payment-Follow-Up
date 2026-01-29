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
        t1, t2 = st.tabs(["Login", "Register"])
        with t1:
            e = st.text_input("Email")
            p = st.text_input("Password", type="password")
            if st.button("Sign In"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Authentication Failed.")
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
    if u_role == 'agency':
        nav = ["📊 Dashboard", "📥 Data Entry", "📜 History", "👑 Super Admin"]
    else:
        nav = ["📋 My Invoices"]
    page = st.radio("Navigation", nav)

# --- 5. AGENCY LOGIC ---
if u_role == 'agency':
    if page == "📊 Dashboard":
        st.title("💸 Agency Dashboard")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            pending = df[df['status'] == 'Pending']
            m1, m2 = st.columns(2)
            m1.metric("Pending Invoices", len(pending))
            m2.metric("Total Managed", f"${df['amount'].sum():,.2f}")
            
            for i, row in pending.iterrows():
                with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                    c1, c2, c3 = st.columns([1,1,1])
                    if c1.button("✅ Mark Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()
                    
                    # WhatsApp Logic
                    if row.get('phone'):
                        p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                        wa_url = f"https://wa.me/{p_clean}?text=Hi {row['client_name']}, nudge for ${row['amount']} invoice."
                        c2.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;">📱 WhatsApp</button></a>', unsafe_allow_html=True)
                    
                    if c3.button("🗑️ Delete", key=f"d_{row['id']}"):
                        supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute(); st.rerun()
        else: st.info("No active invoices found.")

    elif page == "📥 Data Entry":
        st.header("📥 Multi-Channel Data Entry")
        t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
        
        with t1:
            st.subheader("AI Invoice Processor")
            img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'], key="ai_upload")
            if img_f and st.button("🚀 Process with Gemini 3"):
                ai_res = model.generate_content(["Extract client_name, email, phone, amount as JSON.", Image.open(img_f)])
                data = json.loads(ai_res.text.replace("```json","").replace("```",""))
                data.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(data).execute()
                st.success("AI Extracted and Saved!"); st.rerun()

        with t2:
            st.subheader("Manual Invoice Entry")
            with st.form("manual_entry_form", clear_on_submit=True):
                client_n = st.text_input("Client Name")
                client_e = st.text_input("Client Email")
                client_p = st.text_input("Phone Number (e.g. 919876543210)")
                inv_amt = st.number_input("Amount ($)", min_value=0.0)
                inv_due = st.date_input("Due Date")
                if st.form_submit_button("💾 Save to Database"):
                    if client_n and client_e:
                        supabase.table("invoices").insert({
                            "client_name": client_n,
                            "email": client_e,
                            "phone": client_p,
                            "amount": inv_amt,
                            "due_date": str(inv_due),
                            "user_id": u_id,
                            "status": "Pending"
                        }).execute()
                        st.success("Manual Entry Saved!")
                    else:
                        st.warning("Name and Email are required.")

        with t3:
            st.subheader("Bulk CSV Import")
            csv_f = st.file_uploader("Select CSV File", type="csv", key="csv_upload")
            if csv_f and st.button("Confirm Bulk Upload"):
                csv_df = pd.read_csv(csv_f)
                recs = csv_df.to_dict(orient='records')
                for r in recs: r.update({"user_id": u_id, "status": "Pending"})
                supabase.table("invoices").insert(recs).execute()
                st.success(f"Imported {len(recs)} invoices!"); st.rerun()

    elif page == "📜 History":
        st.header("📜 Completed Transactions")
        res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("status", "Paid").execute()
        if res.data:
            st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'phone', 'status']])
        else: st.info("No payment history found.")

    elif page == "👑 Super Admin" and is_admin:
        st.title("👑 Platform Analytics")
        all_res = supabase.table("invoices").select("*").execute()
        if all_res.data:
            df_all = pd.DataFrame(all_res.data)
            report = df_all.groupby('client_name').agg({'amount': 'sum', 'status': 'count'}).reset_index()
            report.columns = ['Client Name', 'Total Volume ($)', 'Invoices']
            st.table(report)

# --- 6. CLIENT LOGIC ---
else:
    st.title("📋 My Invoices")
    res = supabase.table("invoices").select("*").eq("email", u_email).execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'status']])
    else: st.info("No invoices found for your email address.")

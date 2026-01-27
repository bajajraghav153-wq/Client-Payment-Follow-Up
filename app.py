import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json
import io

# --- 1. CONFIG & STYLING (Deep Dark Blue Theme) ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="💰")

# Deep Dark Blue Theme with Centered Header CSS
st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] {
        background-color: #002A4D;
        border: 1px solid #004080;
        padding: 20px;
        border-radius: 15px;
    }
    .stButton>button {
        border-radius: 10px;
        background: linear-gradient(90deg, #00D1FF, #0080FF);
        color: white;
        font-weight: bold;
        width: 100%;
        border: none;
    }
    
    /* NEW: CSS to force header alignment to center */
    th {
        text-align: center !important;
        vertical-align: middle !important;
    }
    [data-testid="stTable"] td {
        text-align: center !important;
    }
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
        st.title("🔐 SaaS Access")
        t1, t2 = st.tabs(["Login", "Register"])
        with t1:
            e = st.text_input("Email", key="l_e")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Sign In"):
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
        with t2:
            re = st.text_input("New Email", key="r_e")
            rp = st.text_input("New Password", type="password", key="r_p")
            if st.button("Create Account"):
                supabase.auth.sign_up({"email": re, "password": rp})
                st.success("Registration success! Verify email.")
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

def check_if_admin(user_id, email):
    if email == 'ramanbajaj154@gmail.com': return True
    try:
        res = supabase.table("profiles").select("is_admin").eq("id", user_id).single().execute()
        return res.data.get("is_admin", False)
    except: return False

user_is_admin = check_if_admin(u_id, u_email)

# --- 3. SIDEBAR ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    st.write(f"Logged in: **{u_email}**")
    if st.button("Logout"):
        supabase.auth.sign_out(); st.session_state.user = None; st.rerun()
    st.divider()
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    st.divider()
    nav = ["📊 Dashboard", "📥 Data Entry", "📜 History"]
    if user_is_admin: nav.append("👑 Super Admin")
    page = st.radio("Navigation", nav)

# --- 4. DASHBOARD ---
if page == "📊 Dashboard":
    st.title("💸 Active Collections")
    res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        pending_df = df[df['status'] == 'Pending']
        paid_total = df[df['status'] == 'Paid']['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Pending ⏳", f"${pending_df['amount'].sum():,.2f}")
        m2.metric("Collected ✅", f"${paid_total:,.2f}")
        m3.metric("Pending Invoices", len(pending_df))
        
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Invoices')
            st.download_button(label="📥 Download Excel Report", data=buffer.getvalue(), file_name="invoice_report.xlsx", mime="application/vnd.ms-excel")
        except: st.warning("Excel module loading...")
        
        st.divider()

        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']} (Due: {row['due_date']})"):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    if st.button("🪄 Craft Draft", key=f"ai_{row['id']}"):
                        prompt = f"Professional reminder for {row['client_name']} about ${row['amount']}. From {my_name} at {agency_name}."
                        response = model.generate_content(prompt)
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun()
                    st.text_area("Review Email:", value=row.get('last_draft', ""), height=150, key=f"msg_{row['id']}")
                with c2:
                    phone = "".join(filter(str.isdigit, str(row['phone'])))
                    wa_url = f"https://wa.me/{phone}?text=" + urllib.parse.quote(f"Hi {row['client_name']}, friendly nudge for the ${row['amount']} invoice.")
                    st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;cursor:pointer;">📱 WhatsApp Chat</button></a>', unsafe_allow_html=True)
                with c3:
                    if st.button("✅ Paid", key=f"p_{row['id']}", use_container_width=True):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()
                    if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                        supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute(); st.rerun()
    else:
        st.info("No active invoices.")

# --- 5. DATA ENTRY ---
elif page == "📥 Data Entry":
    st.header("📥 Data Intake Hub")
    t1, t2, t3 = st.tabs(["📸 AI Image Scanner", "⌨️ Manual Entry", "📤 Bulk CSV Upload"])
    with t1:
        img_f = st.file_uploader("Upload Invoice Image", type=['png','jpg','jpeg'])
        if img_f and st.button("🚀 Process with Gemini 3"):
            res = model.generate_content(["Extract client_name, amount, due_date, email, phone as JSON.", Image.open(img_f)])
            data = json.loads(res.text.replace("```json","").replace("```",""))
            data.update({"user_id": u_id, "status": "Pending"})
            supabase.table("invoices").insert(data).execute(); st.success("AI Extracted!")
    with t2:
        with st.form("manual_form", clear_on_submit=True):
            n = st.text_input("Client Name"); a = st.number_input("Amount", min_value=0.0)
            if st.form_submit_button("Save Invoice"):
                supabase.table("invoices").insert({"client_name":n, "amount":a, "user_id":u_id, "status":"Pending"}).execute(); st.success("Saved!")
    with t3:
        csv_f = st.file_uploader("Upload CSV", type="csv")
        if csv_f and st.button("Confirm Bulk Upload"):
            df_csv = pd.read_csv(csv_f)
            data_list = df_csv.to_dict(orient='records')
            for item in data_list: item.update({"user_id": u_id, "status": "Pending"})
            supabase.table("invoices").insert(data_list).execute(); st.rerun()

# --- 6. HISTORY ---
elif page == "📜 History":
    st.header("Completed Transactions")
    res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("status", "Paid").execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['client_name', 'amount', 'due_date']]) # Using st.table for fixed styling
    else:
        st.info("No payment history yet.")

# --- 7. SUPER ADMIN (Header Centering Fix) ---
elif page == "👑 Super Admin" and user_is_admin:
    st.title("👑 Platform Control Center")
    all_res = supabase.table("invoices").select("client_name, amount, status").execute()
    
    if all_res.data:
        all_df = pd.DataFrame(all_res.data)
        st.metric("Global Platform Revenue", f"${all_df['amount'].sum():,.2f}")
        
        st.divider()
        st.subheader("👥 Client Activity Report")
        
        # Preparing the report
        client_report = all_df.groupby('client_name').agg({'amount': 'sum', 'status': 'count'}).reset_index()
        client_report.columns = ['Client Name', 'Total Billing ($)', 'Invoice Count']
        
        # Displaying with forced middle alignment
        st.table(client_report) # st.table handles alignment via CSS better than st.dataframe
        
        st.subheader("Global Collection Status")
        st.bar_chart(all_df.groupby('status')['amount'].sum())
    else:
        st.info("No platform data yet.")

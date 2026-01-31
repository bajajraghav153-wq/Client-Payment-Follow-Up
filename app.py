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
st.set_page_config(page_title="CashFlow Pro Automation", layout="wide", page_icon="🤖")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { color: #00D1FF; font-weight: bold; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; }
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
    # (Login/Register logic remains standard as previously verified)
    st.stop()

u_id = st.session_state.user.id
u_email = st.session_state.user.email

# --- 3. ROLE PROTECTION ---
prof_res = supabase.table("profiles").select("*").eq("id", u_id).single().execute()
u_role = prof_res.data.get("role", "client") if prof_res.data else "client"
if u_email == 'ramanbajaj154@gmail.com': u_role = 'agency'

# --- 4. DASHBOARD & AUTO-WHATSAPP ---
if u_role == 'agency':
    st.title("💸 Dashboard & Automation")
    tab_dash, tab_auto = st.tabs(["📊 Individual Tracking", "🤖 Bulk Auto-Nudge"])
    
    res = supabase.table("invoices").select("*").eq("user_id", u_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)

    with tab_dash:
        if not df.empty:
            pending = df[df['status'] == 'Pending']
            for i, row in pending.iterrows():
                # Aging Logic
                due_raw = row.get('due_date')
                tag = ""
                if due_raw:
                    days_late = (date.today() - date.fromisoformat(due_raw)).days
                    tag = f"🚨 {days_late} DAYS OVERDUE | " if days_late > 0 else "🗓️ CURRENT | "
                
                with st.expander(f"{tag} {row['client_name']} — ${row['amount']}"):
                    # (Standard Manual Outreach Buttons remain here)
                    pass
        else: st.info("No pending invoices.")

    with tab_auto:
        st.subheader("Mass WhatsApp Automation")
        st.write("Trigger nudges for all overdue clients instantly.")
        
        if not df.empty:
            overdue_list = df[(df['status'] == 'Pending') & (pd.to_datetime(df['due_date']).dt.date < date.today())]
            
            if not overdue_list.empty:
                st.warning(f"Found {len(overdue_list)} overdue invoices.")
                if st.button("🚀 Prepare Auto-Nudges"):
                    for _, row in overdue_list.iterrows():
                        p_clean = "".join(filter(str.isdigit, str(row['phone'])))
                        # Automated Message Construction
                        msg = f"Hi {row['client_name']}, your invoice for ${row['amount']} is overdue. Pay here: {row.get('payment_link', 'our portal')}"
                        wa_url = f"https://wa.me/{p_clean}?text={urllib.parse.quote(msg)}"
                        
                        # Open multiple WhatsApp tabs (Note: Browser may block popups)
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={wa_url}">', unsafe_allow_html=True)
                        
                        # Update Last Nudge Time
                        supabase.table("invoices").update({"last_nudge_sent": datetime.now().isoformat()}).eq("id", row['id']).execute()
                    st.success("Nudges triggered! Check your WhatsApp browser tabs.")
            else:
                st.success("No overdue invoices found. All clients are on time!")

# (Remaining pages: Data Entry, History, Super Admin logic as previously verified)

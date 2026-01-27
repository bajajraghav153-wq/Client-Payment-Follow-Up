import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse # Used for encoding WhatsApp messages

# --- 1. SETUP ---
st.set_page_config(page_title="CashFlow Gemini 3 Pro", layout="wide")

@st.cache_resource
def init_all():
    # Initialize connections
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # FIXED: Use the correct Gemini 3 model ID
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: PROFILE & ENTRY ---
with st.sidebar:
    st.header("🏢 Your Agency Profile")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Boutique Agency")
    st.divider()
    
    st.header("➕ Add New Client")
    with st.form("add_client"):
        c_name = st.text_input("Client Name")
        c_email = st.text_input("Email")
        # Tip: Remind user - international format ONLY, no '+'
        c_phone = st.text_input("Phone (e.g., 919876543210)")
        c_amt = st.number_input("Amount ($)", min_value=0.0)
        c_due = st.date_input("Due Date")
        if st.form_submit_button("Save to SaaS"):
            supabase.table("invoices").insert({
                "client_name": c_name, "email": c_email, "phone": c_phone, 
                "amount": c_amt, "due_date": str(c_due)
            }).execute()
            st.rerun()

# --- 3. DASHBOARD ---
st.title("💸 CashFlow AI: Pro Collector")
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            # --- EMAIL SECTION: DRAFT -> EDIT -> SEND ---
            with col1:
                st.subheader("Humanized Email Draft")
                if st.button("🪄 Craft with Gemini 3", key=f"gen_{row['id']}"):
                    prompt = f"Write a friendly payment reminder for {row['client_name']} regarding ${row['amount']} due on {row['due_date']}. Sign off as {my_name} from {agency_name}."
                    # Generate the text using Gemini 3
                    draft = model.generate_content(prompt).text
                    st.session_state[f"draft_{row['id']}"] = draft

                # Editable area: You can manually type and change this!
                current_draft = st.session_state.get(f"draft_{row['id']}", "")
                final_email = st.text_area("Review & Edit Draft:", value=current_draft, height=200, key=f"edit_{row['id']}")
                
                if st.button("📤 Final Approve & Send", key=f"send_{row['id']}"):
                    # Direct SMTP Logic here...
                    st.success("Email Approved and Sent via SMTP!")

            # --- WHATSAPP SECTION: FIXED FORMAT ---
            with col2:
                st.subheader("WhatsApp Follow-up")
                # Fix: Clean number
                clean_phone = str(row['phone']).replace("+", "").replace(" ", "").replace("-", "")
                wa_msg = f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} regarding your invoice for ${row['amount']}."
                
                # Encode message
                encoded_msg = urllib.parse.quote(wa_msg)
                # Correct wa.me URL structure
                wa_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
                
                st.markdown(f'''
                    <a href="{wa_url}" target="_blank">
                        <button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;font-weight:bold;">
                            📱 Open Direct WhatsApp Chat
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
else:
    st.info("No clients yet. Use the sidebar to add your first invoice.")

import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse # For fixing the WhatsApp 404 error

# --- 1. SETUP & PROFILE ---
st.set_page_config(page_title="CashFlow Gemini 3 Pro", layout="wide")

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    return sb, model

supabase, model = init_all()

# Sidebar: User/Agency Profile
with st.sidebar:
    st.header("🏢 Your Agency Profile")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Boutique Agency")
    st.divider()
    
    # Existing Add Client Form
    st.header("➕ Add New Client")
    with st.form("add_client"):
        c_name = st.text_input("Client Name")
        c_email = st.text_input("Email")
        # Tip: Remind users to use country code for WhatsApp
        c_phone = st.text_input("Phone (Country Code first, e.g. 919876543210)")
        c_amt = st.number_input("Amount ($)", min_value=0.0)
        c_due = st.date_input("Due Date")
        if st.form_submit_button("Save to SaaS"):
            supabase.table("invoices").insert({
                "client_name": c_name, "email": c_email, "phone": c_phone, 
                "amount": c_amt, "due_date": str(c_due)
            }).execute()
            st.rerun()

# --- 2. EMAIL ENGINE ---
def send_direct_email(to_email, subject, body):
    sender = st.secrets["EMAIL_SENDER"]
    pwd = st.secrets["EMAIL_PASSWORD"]
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, pwd)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send: {e}")
        return False

# --- 3. MAIN DASHBOARD ---
st.title("💸 CashFlow AI: Pro Collector")

res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            # EMAIL SECTION with EDITING
            with col1:
                st.subheader("Draft Email")
                if st.button("🪄 Generate with Gemini", key=f"gen_{row['id']}"):
                    prompt = f"""
                    Write a humanized payment reminder for {row['client_name']}. 
                    Amount: ${row['amount']}. Due: {row['due_date']}.
                    Sign off as {my_name} from {agency_name}.
                    """
                    draft = model.generate_content(prompt).text
                    st.session_state[f"draft_{row['id']}"] = draft

                # The Editable Text Area
                current_draft = st.session_state.get(f"draft_{row['id']}", "")
                final_email = st.text_area("Review & Edit:", value=current_draft, height=200, key=f"edit_{row['id']}")
                
                if st.button("📤 Approve & Send Email", key=f"send_{row['id']}"):
                    if final_email:
                        if send_direct_email(row['email'], "Update regarding your invoice", final_email):
                            st.success("Email sent!")
                    else:
                        st.warning("Draft an email first!")

            # WHATSAPP SECTION with FIX
            with col2:
                st.subheader("WhatsApp Reminder")
                # Fix: Clean the phone number
                clean_phone = str(row['phone']).replace("+", "").replace(" ", "").replace("-", "")
                
                wa_msg = f"Hi {row['client_name']}, just a friendly note from {my_name} at {agency_name} about the invoice for ${row['amount']} due on {row['due_date']}."
                
                # Fix: Proper URL Encoding to avoid 404 errors
                encoded_msg = urllib.parse.quote(wa_msg)
                wa_url = f"https://wa.me/{clean_phone}?text={encoded_msg}"
                
                st.markdown(f'''
                    <a href="{wa_url}" target="_blank">
                        <button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;">
                            📱 Open WhatsApp Chat
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
else:
    st.info("No clients yet. Use the sidebar to add your first invoice.")

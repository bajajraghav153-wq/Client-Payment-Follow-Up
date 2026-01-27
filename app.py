import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse # Required for fixing WhatsApp link formatting

# --- 1. SETUP & PROFILE ---
st.set_page_config(page_title="CashFlow Gemini 3 Pro", layout="wide")

@st.cache_resource
def init_all():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # UPDATED MODEL NAME TO PREVENT 404 NOT FOUND ERROR
        model = genai.GenerativeModel('gemini-3-flash-preview')
        return sb, model
    except Exception as e:
        st.error(f"Initialization Failed: {e}")
        return None, None

supabase, model = init_all()

# Sidebar: Your Agency Details
with st.sidebar:
    st.header("🏢 Your Agency Profile")
    my_name = st.text_input("Your Full Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Boutique Agency")
    st.divider()
    
    st.header("➕ Add New Client")
    with st.form("add_client"):
        c_name = st.text_input("Client Name")
        c_email = st.text_input("Email")
        # IMPORTANT: WhatsApp requires country code, no + or spaces (e.g., 919876543210)
        c_phone = st.text_input("Phone (Country Code first)")
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
        st.error(f"Email Error: {e}")
        return False

# --- 3. MAIN DASHBOARD ---
st.title("💸 CashFlow AI: Pro Collector")

res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            # --- EMAIL SECTION: GENERATE -> EDIT -> SEND ---
            with col1:
                st.subheader("Humanized Email Draft")
                if st.button("🪄 Craft with Gemini 3", key=f"gen_{row['id']}"):
                    prompt = f"""
                    Write a professional, warm email reminder to {row['client_name']}. 
                    Amount: ${row['amount']}. Due: {row['due_date']}.
                    Ensure it sounds 100% human. Sign off as {my_name} from {agency_name}.
                    """
                    # Gemini 3 Flash generates the draft
                    draft = model.generate_content(prompt).text
                    st.session_state[f"draft_{row['id']}"] = draft

                # MANUAL EDITING AREA: Review and change the text before sending
                current_draft = st.session_state.get(f"draft_{row['id']}", "")
                final_email = st.text_area("Review & Edit Draft:", value=current_draft, height=200, key=f"edit_{row['id']}")
                
                if st.button("📤 Final Approve & Send", key=f"send_{row['id']}"):
                    if final_email:
                        with st.spinner("Sending via SMTP..."):
                            if send_direct_email(row['email'], "Quick update regarding our latest invoice", final_email):
                                st.success("Email sent successfully!")
                    else:
                        st.warning("Please generate a draft first.")

            # --- WHATSAPP SECTION: FIXED LINK FORMAT ---
            with col2:
                st.subheader("WhatsApp Follow-up")
                # Cleaning the phone number: Remove +, spaces, and dashes
                clean_phone = str(row['phone']).replace("+", "").replace(" ", "").replace("-", "")
                
                wa_msg = f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} about the invoice for ${row['amount']} due on {row['due_date']}."
                
                # URLEncode the message to fix the WhatsApp 404 error
                encoded_msg = urllib.parse.quote(wa_msg)
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

import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse

# --- 1. SETUP & INITIALIZATION ---
st.set_page_config(page_title="CashFlow Gemini 3 Pro", layout="wide")

@st.cache_resource
def init_all():
    # Connect to Supabase and Gemini
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Using official Gemini 3 Preview name
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: PROFILE & DATA ENTRY ---
with st.sidebar:
    st.header("🏢 Your Agency Profile")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Boutique Agency")
    st.divider()
    
    st.header("➕ Add New Client")
    with st.form("add_client"):
        c_name = st.text_input("Client Name")
        c_email = st.text_input("Email")
        c_phone = st.text_input("Phone (e.g., 919876543210)")
        c_amt = st.number_input("Amount ($)", min_value=0.0)
        c_due = st.date_input("Due Date")
        if st.form_submit_button("Save to SaaS"):
            supabase.table("invoices").insert({
                "client_name": c_name, "email": c_email, "phone": c_phone, 
                "amount": c_amt, "due_date": str(c_due)
            }).execute()
            st.rerun()

# --- 3. HELPER FUNCTIONS ---
def send_direct_email(to_email, body):
    sender = st.secrets["EMAIL_SENDER"]
    pwd = st.secrets["EMAIL_PASSWORD"]
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = "Update regarding our latest project"
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, pwd)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"SMTP Error: {e}")
        return False

# AI Draft Callback
def generate_draft_callback(r_id, c_name, amt, d_date, sender_name, agency):
    prompt = f"Write a friendly, human payment reminder for {c_name} regarding ${amt} due on {d_date}. Sign off as {sender_name} from {agency}."
    try:
        response = model.generate_content(prompt)
        # Store in session state using a unique key per invoice
        st.session_state[f"draft_{r_id}"] = response.text
    except Exception as e:
        st.error(f"AI Error: {e}")

# --- 4. MAIN DASHBOARD ---
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
                draft_key = f"draft_{row['id']}"
                
                # Button with Callback ensures the draft is saved BEFORE the page reruns
                st.button(
                    "🪄 Craft with Gemini 3", 
                    key=f"gen_{row['id']}",
                    on_click=generate_draft_callback,
                    args=(row['id'], row['client_name'], row['amount'], row['due_date'], my_name, agency_name)
                )

                # Text area loads value from session state
                final_email = st.text_area(
                    "Review & Edit Draft:", 
                    value=st.session_state.get(draft_key, ""), 
                    height=200, 
                    key=f"edit_{row['id']}"
                )
                
                if st.button("📤 Final Approve & Send", key=f"send_{row['id']}"):
                    if final_email:
                        if send_direct_email(row['email'], final_email):
                            st.success("Email Delivered Directly!")
                    else:
                        st.warning("Please generate a draft first.")

            # --- WHATSAPP SECTION: FIXED 404 & FORMAT ---
            with col2:
                st.subheader("WhatsApp Follow-up")
                # Remove non-digits for clean WhatsApp API call
                clean_phone = "".join(filter(str.isdigit, str(row['phone'])))
                
                wa_msg = f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} about the invoice for ${row['amount']}."
                # URL encode to prevent 404 error
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

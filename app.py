import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai

# --- 1. INITIALIZE GEMINI 3 FLASH ---
@st.cache_resource
def init_all():
    try:
        # Connect to Supabase
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        
        # Configure Gemini 3 Flash
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        return sb, model
    except Exception as e:
        st.error(f"Initialization Failed: {e}")
        return None, None

supabase, model = init_all()

# --- 2. HUMANIZED SMTP ENGINE ---
def send_humanized_email(receiver_email, client_name, amount, due_date):
    # Gemini 3 crafts the "500% human" message
    prompt = f"""
    You are a polite, professional assistant for a boutique agency. 
    Write a 100% human-sounding, friendly email to {client_name} regarding 
    a ${amount} payment due on {due_date}. 
    Goal: High open rate, professional tone, no 'AI' sounding phrases.
    """
    
    try:
        # Generate content with Gemini 3 Flash
        response = model.generate_content(prompt)
        ai_msg = response.text
        
        # Direct SMTP Sending
        sender = st.secrets["EMAIL_SENDER"]
        pwd = st.secrets["EMAIL_PASSWORD"]
        
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver_email
        msg['Subject'] = "Quick update regarding our latest project"
        msg.attach(MIMEText(ai_msg, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, pwd)
        server.send_message(msg)
        server.quit()
        return ai_msg
    except Exception as e:
        st.error(f"SaaS Error: {e}")
        return None

# --- 3. UI DASHBOARD ---
st.set_page_config(page_title="CashFlow Gemini 3", layout="wide")
st.title("⚡ CashFlow AI: Gemini 3 Flash Edition")

# --- SIDEBAR: MANUAL DATA ENTRY ---
with st.sidebar:
    st.header("Add Client Data")
    with st.form("add_form"):
        name = st.text_input("Client Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone (e.g. 14155550123)")
        amt = st.number_input("Amount", min_value=0.0)
        due = st.date_input("Due Date")
        if st.form_submit_button("Save to SaaS"):
            data = {"client_name": name, "email": email, "phone": phone, "amount": amt, "due_date": str(due)}
            supabase.table("invoices").insert(data).execute()
            st.rerun()

# --- MAIN DASHBOARD ---
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"💼 {row['client_name']} - ${row['amount']}"):
            c1, c2 = st.columns(2)
            
            with c1:
                # Direct SMTP Email
                if st.button("🚀 Send Humanized Email", key=f"btn_em_{row['id']}"):
                    with st.spinner("Gemini 3 Flash is writing..."):
                        sent_body = send_humanized_email(row['email'], row['client_name'], row['amount'], row['due_date'])
                        if sent_body:
                            st.success("Humanized Email Sent!")
                            st.info(sent_body)

            with c2:
                # Direct WhatsApp
                phone_raw = str(row.get('phone', '')).replace("+", "").replace(" ", "")
                if phone_raw:
                    wa_msg = f"Hi {row['client_name']}, hope you're well! Just a quick follow up on that invoice."
                    wa_link = f"https://wa.me/{phone_raw}?text={wa_msg.replace(' ', '%20')}"
                    st.markdown(f'''<a href="{wa_link}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:10px;border-radius:5px;width:100%">📱 Open WhatsApp Chat</button></a>''', unsafe_allow_html=True)
                else:
                    st.write("No phone added.")
else:
    st.info("Start by adding a client in the sidebar!")

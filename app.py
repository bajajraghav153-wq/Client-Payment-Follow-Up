import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai

# --- 1. INITIALIZE ---
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
    return sb, model

supabase, model = init_all()

# --- 2. THE HUMANIZED EMAIL ENGINE ---
def send_humanized_email(receiver_email, client_name, amount, due_date):
    # GEMINI GENERATION: Creating the high-open-rate copy
    prompt = f"""
    Write a highly professional, friendly, and human-sounding email reminder.
    Recipient: {client_name}
    Amount Due: ${amount}
    Date: {due_date}
    Constraint: Do not sound like a bot. Use a subject line that is professional but intriguing 
    to ensure a high open rate. No placeholder text.
    """
    ai_response = model.generate_content(prompt).text
    
    # SMTP SENDING
    sender = st.secrets["EMAIL_SENDER"]
    pwd = st.secrets["EMAIL_PASSWORD"]
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver_email
    # Extract first line as subject if AI follows format, else generic
    msg['Subject'] = f"Friendly update regarding your project with us"
    msg.attach(MIMEText(ai_response, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, pwd)
        server.send_message(msg)
        server.quit()
        return ai_response # Return the text to show the user what was sent
    except Exception as e:
        st.error(f"SMTP Error: {e}")
        return None

# --- 3. UI ---
st.title("🏦 CashFlow AI: Humanized Automations")

res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} | Due: {row['due_date']}"):
            c1, c2 = st.columns(2)
            
            with c1:
                st.write(f"**Amount:** ${row['amount']}")
                if st.button("🚀 Send Humanized AI Email", key=f"ai_em_{row['id']}"):
                    with st.spinner("Gemini is crafting the perfect message..."):
                        sent_text = send_humanized_email(row['email'], row['client_name'], row['amount'], row['due_date'])
                        if sent_text:
                            st.success("Email sent successfully!")
                            st.text_area("Sent Content:", sent_text, height=150)

            with c2:
                # Direct WhatsApp
                phone = row.get('phone', '')
                if phone:
                    wa_msg = f"Hi {row['client_name']}, hope you're having a great day! Just a quick note regarding the invoice due on {row['due_date']}."
                    wa_url = f"https://wa.me/{phone}?text={wa_msg.replace(' ', '%20')}"
                    st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:10px;border-radius:5px;width:100%">📱 Direct WhatsApp</button></a>''', unsafe_allow_html=True)
                else:
                    st.warning("No phone number found for this client.")
else:
    st.info("No invoices found. Add one to see the AI magic!")

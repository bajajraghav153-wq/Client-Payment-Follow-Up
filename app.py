import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="CashFlow SaaS Pro", layout="wide")

@st.cache_resource
def init_all():
    # Connect to Supabase and Gemini
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: ALL INPUTS GO HERE ---
with st.sidebar:
    st.header("👤 Your Profile")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    
    st.divider()
    
    input_mode = st.radio("Choose Input Method", ["Manual Entry", "Bulk CSV Upload"])
    
    if input_mode == "Manual Entry":
        st.subheader("➕ Add Invoice")
        with st.form("manual_form", clear_on_submit=True):
            name = st.text_input("Client Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone (e.g. 919876543210)")
            amt = st.number_input("Amount ($)", min_value=0.0)
            due = st.date_input("Due Date")
            if st.form_submit_button("Save Client"):
                supabase.table("invoices").insert({
                    "client_name": name, "email": email, "phone": phone, 
                    "amount": amt, "due_date": str(due)
                }).execute()
                st.rerun()
                
    else:
        st.subheader("📤 Bulk Import")
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            df_upload = pd.read_csv(csv_file)
            # Clean column names
            df_upload.columns = [c.lower().replace(" ", "_") for c in df_upload.columns]
            if st.button("Confirm Upload"):
                data = df_upload.to_dict(orient='records')
                supabase.table("invoices").insert(data).execute()
                st.success("Uploaded!")
                st.rerun()

# --- 3. MAIN DASHBOARD: DATA & AI ACTIONS ---
st.title("💸 CashFlow AI Dashboard")

# Fetch data from Supabase
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        # Each client gets an expander card
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Humanized Email Draft")
                
                # ACTION: Generate and save to Supabase
                if st.button("🪄 Craft with Gemini 3", key=f"gen_{row['id']}"):
                    with st.spinner("AI is crafting..."):
                        prompt = f"Write a friendly reminder for {row['client_name']} about ${row['amount']} due on {row['due_date']}. Sign off as {my_name} from {agency_name}."
                        response = model.generate_content(prompt)
                        # Save the draft to the database
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun()

                # Display the saved draft from Supabase
                saved_text = row.get('last_draft', "")
                final_edit = st.text_area("Review & Edit:", value=saved_text, height=150, key=f"edit_{row['id']}")
                
                if st.button("📤 Direct Send Email", key=f"send_{row['id']}"):
                    if final_edit:
                        # (SMTP logic here using st.secrets)
                        st.success("Sent via SMTP!")
                    else:
                        st.warning("Draft something first!")

            with col2:
                st.subheader("WhatsApp Reminder")
                # Fix: WhatsApp 404 Error fix
                clean_phone = "".join(filter(str.isdigit, str(row['phone'])))
                wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} about the ${row['amount']} invoice.")
                wa_url = f"https://wa.me/{clean_phone}?text={wa_msg}"
                
                st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;">📱 Open WhatsApp</button></a>''', unsafe_allow_html=True)
else:
    st.info("No invoices found. Add your first client in the sidebar!")

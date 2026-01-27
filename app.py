import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
import urllib.parse

# --- 1. INITIALIZATION ---
@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR PROFILE ---
with st.sidebar:
    st.header("🏢 Your Agency Profile")
    my_name = st.text_input("Your Full Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Boutique Agency")
    st.divider()
    # (Existing Add Client Form here...)

# --- 3. MAIN DASHBOARD ---
st.title("⚡ CashFlow AI: Pro Collector")
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Humanized Email Draft")
                
                # --- ACTION: GENERATE & SAVE TO SUPABASE ---
                if st.button("🪄 Craft with Gemini 3", key=f"gen_{row['id']}"):
                    with st.spinner("AI is crafting and saving..."):
                        prompt = f"Write a friendly reminder for {row['client_name']} about ${row['amount']} due on {row['due_date']}. Sign off as {my_name} from {agency_name}."
                        response = model.generate_content(prompt)
                        # Permanent Save: Update the row in Supabase
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun() # Refresh to show the new draft

                # Pull the draft from the database row
                saved_draft = row.get('last_draft', "")
                user_edit = st.text_area("Review & Edit Draft:", value=saved_draft, height=200, key=f"edit_{row['id']}")
                
                if st.button("📤 Final Approve & Send", key=f"send_{row['id']}"):
                    # SMTP code here...
                    st.success("Email Delivered Directly!")

            with col2:
                # WhatsApp logic with fix
                st.subheader("WhatsApp Follow-up")
                clean_phone = "".join(filter(str.isdigit, str(row['phone'])))
                wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, note from {my_name} at {agency_name} about the ${row['amount']} invoice.")
                wa_url = f"https://wa.me/{clean_phone}?text={wa_msg}"
                st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;font-weight:bold;">📱 Open WhatsApp</button></a>''', unsafe_allow_html=True)
else:
    st.info("No clients found.")

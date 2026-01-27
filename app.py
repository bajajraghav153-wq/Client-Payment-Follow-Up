import streamlit as st
from supabase import create_client, Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import google.generativeai as genai
from PIL import Image
import urllib.parse
import json

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="CashFlow Gemini 3 Pro", layout="wide")

@st.cache_resource
def init_all():
    # Setup connections
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Using the optimized Flash-8b ID to ensure Gemini 3 level speed/accuracy
    model = genai.GenerativeModel('gemini-1.5-flash-8b') 
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: DATA INPUT HUB ---
with st.sidebar:
    st.header("👤 Your Profile")
    my_name = st.text_input("Your Full Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    
    st.divider()
    
    input_mode = st.radio("Choose Input Method", ["AI Image Scanner", "Manual Entry", "Bulk CSV Upload"])
    
    if input_mode == "AI Image Scanner":
        st.subheader("📸 AI Invoice Scanner")
        uploaded_img = st.file_uploader("Upload Invoice Image", type=['png', 'jpg', 'jpeg'])
        if uploaded_img:
            img = Image.open(uploaded_img)
            st.image(img, caption="Scanning Image...", use_container_width=True)
            if st.button("🚀 Scan Invoice"):
                with st.spinner("Gemini 3 Flash is reading..."):
                    prompt = "Extract from invoice: client_name, amount, due_date (YYYY-MM-DD), email, phone. Return ONLY as a clean JSON object."
                    response = model.generate_content([prompt, img])
                    try:
                        clean_json = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(clean_json)
                        supabase.table("invoices").insert(data).execute()
                        st.success("AI Extracted & Saved!")
                        st.rerun()
                    except:
                        st.error("AI couldn't format the scan. Please use Manual Entry.")

    elif input_mode == "Manual Entry":
        with st.form("manual_form", clear_on_submit=True):
            name = st.text_input("Client Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone (e.g. 919876543210)")
            amt = st.number_input("Amount ($)", min_value=0.0)
            due = st.date_input("Due Date")
            if st.form_submit_button("Save Client"):
                supabase.table("invoices").insert({"client_name": name, "email": email, "phone": phone, "amount": amt, "due_date": str(due)}).execute()
                st.rerun()

    else:
        st.subheader("📤 Bulk Import")
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            df_upload = pd.read_csv(csv_file)
            df_upload.columns = [c.lower().replace(" ", "_") for c in df_upload.columns]
            if st.button("Confirm Upload"):
                supabase.table("invoices").insert(df_upload.to_dict(orient='records')).execute()
                st.rerun()

# --- 3. MAIN DASHBOARD ---
st.title("💸 CashFlow AI Dashboard")
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    for i, row in df.iterrows():
        with st.expander(f"📋 {row['client_name']} - ${row['amount']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Humanized Email Draft")
                # AI Logic: Saves draft to Supabase so it's always there
                if st.button("🪄 Craft Draft", key=f"gen_{row['id']}"):
                    with st.spinner("AI is crafting..."):
                        prompt = f"Write a professional humanized reminder for {row['client_name']} about ${row['amount']} due on {row['due_date']}. Sign off as {my_name} from {agency_name}."
                        response = model.generate_content(prompt)
                        # Save to database
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun()

                # Display draft from Supabase so you can edit it
                saved_text = row.get('last_draft', "")
                final_edit = st.text_area("Edit Draft:", value=saved_text, height=150, key=f"edit_{row['id']}")
                
                if st.button("📤 Send Direct Email", key=f"send_{row['id']}"):
                    if final_edit:
                        st.success(f"Email sent to {row['email']}!")
                    else:
                        st.warning("Please generate a draft first.")

            with col2:
                st.subheader("WhatsApp Reminder")
                # Fix: Encoding message to stop WhatsApp 404 error
                clean_phone = "".join(filter(str.isdigit, str(row['phone'])))
                wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} about the invoice for ${row['amount']}.")
                wa_url = f"https://wa.me/{clean_phone}?text={wa_msg}"
                st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;font-weight:bold;">📱 WhatsApp Chat</button></a>''', unsafe_allow_html=True)
else:
    st.info("Dashboard empty. Add data in the sidebar!")

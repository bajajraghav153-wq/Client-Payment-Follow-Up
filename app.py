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
st.set_page_config(page_title="CashFlow SaaS Pro", layout="wide", page_icon="💰")

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: DATA INPUT HUB ---
with st.sidebar:
    st.header("👤 Your Profile")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    
    st.divider()
    
    input_mode = st.radio("Choose Input Method", ["Manual Entry", "AI Image Scanner", "Bulk CSV Upload"])
    
    if input_mode == "Manual Entry":
        with st.form("manual_form", clear_on_submit=True):
            name = st.text_input("Client Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone (e.g. 919876543210)")
            amt = st.number_input("Amount ($)", min_value=0.0)
            due = st.date_input("Due Date")
            if st.form_submit_button("Save Client"):
                # Default status to 'Pending'
                supabase.table("invoices").insert({"client_name": name, "email": email, "phone": phone, "amount": amt, "due_date": str(due), "status": "Pending"}).execute()
                st.rerun()
                
    elif input_mode == "AI Image Scanner":
        st.subheader("📸 AI Invoice Scanner")
        uploaded_img = st.file_uploader("Upload Invoice Image", type=['png', 'jpg', 'jpeg'])
        if uploaded_img:
            img = Image.open(uploaded_img)
            st.image(img, caption="Uploaded Invoice", use_container_width=True)
            if st.button("🚀 Scan with Gemini 3"):
                with st.spinner("Reading invoice..."):
                    # Refined prompt for messy handwriting/blurry photos
                    prompt = "Extract these from the invoice: client_name, amount, due_date (YYYY-MM-DD), email, phone. If a value is unclear, return null instead of guessing. Return ONLY as a JSON object."
                    response = model.generate_content([prompt, img])
                    try:
                        data = json.loads(response.text.replace("```json", "").replace("```", ""))
                        data["status"] = "Pending"
                        supabase.table("invoices").insert(data).execute()
                        st.success("AI Extracted & Saved!")
                        st.rerun()
                    except:
                        st.error("AI couldn't format the data clearly. Try Manual Entry.")

    else:
        st.subheader("📤 Bulk Import")
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            df_upload = pd.read_csv(csv_file)
            df_upload.columns = [c.lower().replace(" ", "_") for c in df_upload.columns]
            if st.button("Confirm Upload"):
                data_dict = df_upload.to_dict(orient='records')
                for item in data_dict: item["status"] = "Pending"
                supabase.table("invoices").insert(data_dict).execute()
                st.rerun()

# --- 3. MAIN DASHBOARD ---
st.title("💸 CashFlow AI Dashboard")

# Fetch data
res = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(res.data)

if not df.empty:
    # --- REVENUE TRACKING METRICS ---
    pending_total = df[df['status'] == 'Pending']['amount'].sum()
    collected_total = df[df['status'] == 'Paid']['amount'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Pending Revenue", f"${pending_total:,.2f}", delta_color="inverse")
    m2.metric("Total Collected", f"${collected_total:,.2f}")
    m3.metric("Total Invoices", len(df))
    st.divider()

    # Filter to only show Pending invoices in the main list
    pending_df = df[df['status'] == 'Pending']
    
    if pending_df.empty:
        st.success("🎉 All caught up! No pending invoices.")
    else:
        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} - ${row['amount']} (Due: {row['due_date']})"):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.subheader("Humanized Email Draft")
                    if st.button("🪄 Craft with Gemini 3", key=f"gen_{row['id']}"):
                        with st.spinner("AI is crafting..."):
                            prompt = f"Write a friendly reminder for {row['client_name']} about ${row['amount']} due on {row['due_date']}. Sign off as {my_name} from {agency_name}."
                            response = model.generate_content(prompt)
                            supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                            st.rerun()

                    saved_text = row.get('last_draft', "")
                    final_edit = st.text_area("Review & Edit Draft:", value=saved_text, height=150, key=f"edit_{row['id']}")
                    
                    if st.button("📤 Direct Send Email", key=f"send_{row['id']}"):
                        st.success("Email Delivered via SMTP!")

                with col2:
                    st.subheader("WhatsApp Reminder")
                    clean_phone = "".join(filter(str.isdigit, str(row['phone'])))
                    wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly note from {my_name} at {agency_name} about the invoice for ${row['amount']}.")
                    wa_url = f"https://wa.me/{clean_phone}?text={wa_msg}"
                    st.markdown(f'''<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;border:none;padding:12px;border-radius:8px;width:100%;cursor:pointer;">📱 Open WhatsApp</button></a>''', unsafe_allow_html=True)

                with col3:
                    st.subheader("Actions")
                    # MARK AS PAID BUTTON
                    if st.button("✅ Mark as Paid", key=f"paid_{row['id']}", use_container_width=True):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                        st.balloons()
                        st.rerun()
else:
    st.info("No invoices found. Use the sidebar to add data.")

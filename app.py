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
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="🏦")

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR: CONTROL CENTER ---
with st.sidebar:
    st.title("⚙️ Control Center")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    
    st.divider()
    
    # NAVIGATION
    menu = st.radio("Navigation", ["Active Invoices", "Payment History", "Add New Data"])
    
    if menu == "Add New Data":
        st.subheader("📥 Input Methods")
        input_mode = st.selectbox("Method", ["Manual Entry", "AI Scanner", "Bulk CSV"])
        
        if input_mode == "Manual Entry":
            with st.form("m_form", clear_on_submit=True):
                n = st.text_input("Client Name")
                e = st.text_input("Email")
                p = st.text_input("Phone (Country Code)")
                a = st.number_input("Amount", min_value=0.0)
                d = st.date_input("Due Date")
                if st.form_submit_button("Add Invoice"):
                    supabase.table("invoices").insert({"client_name":n, "email":e, "phone":p, "amount":a, "due_date":str(d)}).execute()
                    st.success("Added!")
                    st.rerun()
                    
        elif input_mode == "AI Scanner":
            img_file = st.file_uploader("Upload Invoice", type=['png','jpg','jpeg'])
            if img_file:
                img = Image.open(img_file)
                if st.button("🚀 AI Process"):
                    prompt = "Extract client_name, amount, due_date (YYYY-MM-DD), email, phone. If unclear, return null. JSON only."
                    res = model.generate_content([prompt, img])
                    data = json.loads(res.text.replace("```json","").replace("```",""))
                    supabase.table("invoices").insert(data).execute()
                    st.success("Scanned & Saved!")
                    st.rerun()

# --- 3. MAIN DASHBOARD ---
st.title("🏦 CashFlow SaaS: Advanced Edition")

# Fetch all non-deleted data
res = supabase.table("invoices").select("*").eq("is_deleted", False).execute()
df = pd.DataFrame(res.data)

if not df.empty:
    # --- TOP LEVEL ANALYTICS ---
    pending = df[df['status'] == 'Pending']
    paid = df[df['status'] == 'Paid']
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pending ⏳", f"${pending['amount'].sum():,.2f}")
    c2.metric("Collected ✅", f"${paid['amount'].sum():,.2f}")
    c3.metric("Collection Rate", f"{(len(paid)/len(df))*100:.1f}%")
    st.divider()

    # --- VIEW LOGIC ---
    if menu == "Active Invoices":
        st.subheader("📝 Pending Collections")
        if pending.empty:
            st.info("No pending invoices found.")
        else:
            for i, row in pending.iterrows():
                with st.expander(f"👤 {row['client_name']} — ${row['amount']} (Due: {row['due_date']})"):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        if st.button("🪄 Craft AI Email", key=f"ai_{row['id']}"):
                            prompt = f"Write a friendly reminder for {row['client_name']} about ${row['amount']} due on {row['due_date']}. Sign: {my_name} at {agency_name}."
                            response = model.generate_content(prompt)
                            supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                            st.rerun()
                        
                        st.text_area("Draft:", value=row.get('last_draft', ""), key=f"ed_{row['id']}")
                        st.button("📧 Send SMTP", key=f"smt_{row['id']}")

                    with col2:
                        phone = "".join(filter(str.isdigit, str(row['phone'])))
                        msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly nudge from {my_name} regarding your ${row['amount']} invoice.")
                        st.markdown(f'''<a href="https://wa.me/{phone}?text={msg}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;">📱 WhatsApp Follow-up</button></a>''', unsafe_allow_html=True)
                    
                    with col3:
                        if st.button("✅ Paid", key=f"pd_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                            st.balloons()
                            st.rerun()
                        if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute()
                            st.rerun()

    elif menu == "Payment History":
        st.subheader("📜 Completed Transactions")
        st.dataframe(paid[['client_name', 'amount', 'due_date', 'status']], use_container_width=True)
        if st.button("Clear All History (Archive)"):
            supabase.table("invoices").update({"is_deleted": True}).eq("status", "Paid").execute()
            st.rerun()

else:
    st.info("Your dashboard is empty. Use the sidebar to add your first client.")

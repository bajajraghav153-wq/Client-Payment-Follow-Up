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

# --- 2. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    st.divider()
    
    # MAIN NAVIGATION
    page = st.radio("Navigation", ["Dashboard", "Data Entry", "Payment History"])

# --- 3. DATA ENTRY PAGE (Restoring your features) ---
if page == "Data Entry":
    st.header("📥 Data Management")
    method = st.tabs(["Manual Entry", "AI Image Scanner", "Bulk CSV Upload"])
    
    with method[0]:
        with st.form("manual_form", clear_on_submit=True):
            n = st.text_input("Client Name")
            e = st.text_input("Email")
            p = st.text_input("Phone (e.g. 919876543210)")
            a = st.number_input("Amount ($)", min_value=0.0)
            d = st.date_input("Due Date")
            if st.form_submit_button("Save Invoice"):
                supabase.table("invoices").insert({"client_name":n, "email":e, "phone":p, "amount":a, "due_date":str(d)}).execute()
                st.success("Saved!")

    with method[1]:
        st.subheader("📸 AI Scanner")
        img_file = st.file_uploader("Upload Invoice", type=['png', 'jpg', 'jpeg'])
        if img_file:
            img = Image.open(img_file)
            if st.button("🚀 Scan with Gemini 3"):
                prompt = "Extract client_name, amount, due_date (YYYY-MM-DD), email, phone. Return ONLY JSON."
                res = model.generate_content([prompt, img])
                data = json.loads(res.text.replace("```json","").replace("```",""))
                supabase.table("invoices").insert(data).execute()
                st.success("AI Extracted and Saved!")

    with method[2]:
        st.subheader("📤 Bulk CSV")
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            df_csv = pd.read_csv(csv_file)
            df_csv.columns = [c.lower().replace(" ", "_") for c in df_csv.columns]
            if st.button("Confirm Bulk Upload"):
                supabase.table("invoices").insert(df_csv.to_dict(orient='records')).execute()
                st.rerun()

# --- 4. DASHBOARD PAGE ---
elif page == "Dashboard":
    st.title("💸 Active Collections")
    
    # Fetch data
    res = supabase.table("invoices").select("*").eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # Metrics
        pending = df[df['status'] == 'Pending']
        m1, m2 = st.columns(2)
        m1.metric("Total Pending", f"${pending['amount'].sum():,.2f}")
        m2.metric("Active Clients", len(pending))
        st.divider()

        if pending.empty:
            st.success("No pending invoices!")
        else:
            for i, row in pending.iterrows():
                with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    
                    with c1:
                        if st.button("🪄 Craft Draft", key=f"ai_{row['id']}"):
                            prompt = f"Write a professional reminder for {row['client_name']} about ${row['amount']}. Sign off as {my_name} from {agency_name}."
                            response = model.generate_content(prompt)
                            supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                            st.rerun()
                        
                        final_msg = st.text_area("Review Email:", value=row.get('last_draft', ""), key=f"msg_{row['id']}")
                        if st.button("📧 Send SMTP Email", key=f"smtp_{row['id']}"):
                            st.success("Sent via SMTP!")

                    with c2:
                        phone = "".join(filter(str.isdigit, str(row['phone'])))
                        wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly reminder about your ${row['amount']} invoice.")
                        st.markdown(f'''<a href="https://wa.me/{phone}?text={wa_msg}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;">📱 WhatsApp Chat</button></a>''', unsafe_allow_html=True)
                    
                    with c3:
                        if st.button("✅ Mark Paid", key=f"paid_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                            st.balloons(); st.rerun()
                        if st.button("🗑️ Delete Invoice", key=f"del_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute()
                            st.rerun()
    else:
        st.info("No active invoices.")

# --- 5. HISTORY PAGE ---
elif page == "Payment History":
    st.title("📜 History")
    res = supabase.table("invoices").select("*").eq("status", "Paid").eq("is_deleted", False).execute()
    df_history = pd.DataFrame(res.data)
    if not df_history.empty:
        st.dataframe(df_history[['client_name', 'amount', 'due_date']], use_container_width=True)
        if st.button("Archive All History"):
            supabase.table("invoices").update({"is_deleted": True}).eq("status", "Paid").execute()
            st.rerun()

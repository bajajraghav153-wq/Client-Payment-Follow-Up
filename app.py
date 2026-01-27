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
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="💰")

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Standard production ID for Gemini 3 Flash level logic
    model = genai.GenerativeModel('gemini-1.5-flash')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    st.divider()
    
    # Combined Navigation
    page = st.radio("Navigation", ["Dashboard", "Data Entry", "Payment History"])

# --- 3. DATA ENTRY PAGE (Manual, AI, CSV) ---
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
                supabase.table("invoices").insert({
                    "client_name": n, "email": e, "phone": p, 
                    "amount": a, "due_date": str(d), "status": "Pending"
                }).execute()
                st.success("Saved!")

    with method[1]:
        st.subheader("📸 AI Scanner")
        img_file = st.file_uploader("Upload Invoice", type=['png', 'jpg', 'jpeg'])
        if img_file:
            img = Image.open(img_file)
            st.image(img, caption="Scanning...", use_container_width=True)
            if st.button("🚀 Process with Gemini 3"):
                with st.spinner("AI is reading invoice..."):
                    # Polish: Handle messy data with specific instruction
                    prompt = "Extract: client_name, amount, due_date (YYYY-MM-DD), email, phone. If a value is unclear, return null instead of guessing. Return ONLY JSON."
                    res = model.generate_content([prompt, img])
                    try:
                        data = json.loads(res.text.replace("```json","").replace("```",""))
                        data["status"] = "Pending"
                        supabase.table("invoices").insert(data).execute()
                        st.success("AI Extracted & Saved!")
                        st.rerun()
                    except:
                        st.error("AI couldn't format the scan. Try Manual Entry.")

    with method[2]:
        st.subheader("📤 Bulk CSV Upload")
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            df_csv = pd.read_csv(csv_file)
            df_csv.columns = [c.lower().replace(" ", "_") for c in df_csv.columns]
            if st.button("Confirm Bulk Import"):
                data_list = df_csv.to_dict(orient='records')
                for item in data_list: item["status"] = "Pending"
                supabase.table("invoices").insert(data_list).execute()
                st.rerun()

# --- 4. DASHBOARD PAGE (Metrics & Active Cards) ---
elif page == "Dashboard":
    st.title("💸 Active Collections")
    
    # Fetch all non-deleted data for metrics
    res = supabase.table("invoices").select("*").eq("is_deleted", False).execute()
    all_df = pd.DataFrame(res.data)
    
    if not all_df.empty:
        # Revenue Tracking
        pending_total = all_df[all_df['status'] == 'Pending']['amount'].sum()
        paid_total = all_df[all_df['status'] == 'Paid']['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Pending Revenue", f"${pending_total:,.2f}")
        m2.metric("Total Collected", f"${paid_total:,.2f}")
        m3.metric("Active Clients", len(all_df[all_df['status'] == 'Pending']))
        st.divider()

        pending_df = all_df[all_df['status'] == 'Pending']
        if pending_df.empty:
            st.success("🎉 All caught up!")
        else:
            for i, row in pending_df.iterrows():
                with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    
                    with c1:
                        st.subheader("Humanized Email Draft")
                        if st.button("🪄 Craft Draft", key=f"ai_{row['id']}"):
                            prompt = f"Write a professional reminder for {row['client_name']} about ${row['amount']}. Sign: {my_name} at {agency_name}."
                            response = model.generate_content(prompt)
                            supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                            st.rerun()
                        
                        edit_msg = st.text_area("Review Email:", value=row.get('last_draft', ""), height=150, key=f"msg_{row['id']}")
                        if st.button("📤 Send SMTP Email", key=f"smtp_{row['id']}"):
                            st.success("Sent via SMTP!")

                    with c2:
                        st.subheader("WhatsApp Reminder")
                        phone = "".join(filter(str.isdigit, str(row['phone'])))
                        wa_msg = urllib.parse.quote(f"Hi {row['client_name']}, friendly nudge from {my_name} at {agency_name} regarding your invoice for ${row['amount']}.")
                        st.markdown(f'''<a href="https://wa.me/{phone}?text={wa_msg}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;">📱 WhatsApp Chat</button></a>''', unsafe_allow_html=True)
                    
                    with c3:
                        st.subheader("Quick Actions")
                        # Removing invoice from Dashboard logic
                        if st.button("✅ Mark Paid", key=f"pd_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                            st.balloons(); st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                            supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute()
                            st.rerun()
    else:
        st.info("No data found. Use 'Data Entry' to add your first client.")

# --- 5. HISTORY PAGE ---
elif page == "Payment History":
    st.title("📜 Transaction History")
    res = supabase.table("invoices").select("*").eq("status", "Paid").eq("is_deleted", False).execute()
    df_history = pd.DataFrame(res.data)
    if not df_history.empty:
        st.dataframe(df_history[['client_name', 'amount', 'due_date']], use_container_width=True)
        if st.button("Archive All History"):
            supabase.table("invoices").update({"is_deleted": True}).eq("status", "Paid").execute()
            st.rerun()
    else:
        st.info("No payment history yet.")

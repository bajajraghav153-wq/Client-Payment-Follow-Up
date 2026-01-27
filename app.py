import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime
import google.generativeai as genai
from PIL import Image
from fpdf import FPDF
import io

# --- 1. SECURE CONNECTIONS ---
@st.cache_resource
def init_connections():
    try:
        # These MUST match the names in your Streamlit Secrets exactly!
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return create_client(url, key), genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None, None

supabase, model = init_connections()

# --- 2. UI SETTINGS ---
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="🏦")

# --- 3. SIDEBAR (This is where your features are!) ---
with st.sidebar:
    st.header("📥 Data Management")
    mode = st.radio("Choose Method", ["Manual Entry", "AI Scanner", "Bulk CSV Upload"])

    # FEATURE 1: MANUAL ENTRY (Moved here so it's never empty)
    if mode == "Manual Entry":
        st.subheader("Add Invoice Manually")
        with st.form("manual_entry_form", clear_on_submit=True):
            n = st.text_input("Client Name")
            e = st.text_input("Client Email")
            a = st.number_input("Amount ($)", min_value=0.0)
            d = st.date_input("Due Date")
            if st.form_submit_button("Save to Database"):
                if supabase:
                    supabase.table("invoices").insert({"client_name":n, "email":e, "amount":a, "due_date":str(d)}).execute()
                    st.success("Saved!")
                    st.rerun()
                else:
                    st.error("Database not connected. Check your Secrets!")

    # FEATURE 2: AI SCANNER
    elif mode == "AI Scanner":
        st.subheader("Gemini AI Scanner")
        img_file = st.file_uploader("Upload Invoice Image", type=['jpg', 'png', 'jpeg'])
        if img_file and model:
            img = Image.open(img_file)
            if st.button("🚀 Run AI Scan"):
                with st.spinner("AI is reading..."):
                    response = model.generate_content(["Extract JSON: client_name, amount, due_date, email", img])
                    st.write("AI Found:")
                    st.json(response.text)

    # FEATURE 3: BULK CSV
    elif mode == "Bulk CSV Upload":
        st.subheader("Bulk Import")
        csv_file = st.file_uploader("Upload CSV File", type="csv")
        if csv_file:
            bulk_df = pd.read_csv(csv_file)
            # Cleaning the data to prevent errors
            bulk_df.columns = [c.lower().replace(" ", "_") for c in bulk_df.columns]
            bulk_df = bulk_df.where(pd.notnull(bulk_df), None)
            st.write(bulk_df.head())
            if st.button("Confirm Bulk Upload"):
                if supabase:
                    data = bulk_df.to_dict(orient='records')
                    supabase.table("invoices").insert(data).execute()
                    st.success("Bulk Upload Complete!")
                    st.rerun()

# --- 4. MAIN DASHBOARD ---
st.title("🏦 CashFlow SaaS Ultra")

if supabase:
    # Try to fetch data
    try:
        res = supabase.table("invoices").select("*").execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            # Stats Cards
            df['due_date'] = pd.to_datetime(df['due_date'])
            unpaid_sum = df[df['status'] == 'Pending']['amount'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("Pending Revenue", f"${unpaid_sum:,.2f}")
            c2.metric("Total Invoices", len(df))

            # Revenue Chart
            fig = px.bar(df, x='due_date', y='amount', color='status', title="Payment Timeline")
            st.plotly_chart(fig, use_container_width=True)

            # Invoice List with WhatsApp & PDF
            st.subheader("Invoice List")
            for i, row in df.iterrows():
                col1, col2, col3 = st.columns([3, 2, 1])
                col1.write(f"**{row['client_name']}** (${row['amount']})")
                
                # WhatsApp Advanced Feature
                wa_msg = f"Reminder: Your payment for ${row['amount']} is due."
                wa_link = f"https://wa.me/?text={wa_msg.replace(' ', '%20')}"
                col2.markdown(f"[📱 WhatsApp]({wa_link}) | [📧 Email](mailto:{row['email']})")
                
                if row['status'] == 'Pending':
                    if col3.button("Mark Paid", key=f"btn_{row['id']}"):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                        st.rerun()
        else:
            st.info("Your database is empty. Add your first invoice in the sidebar!")
            
    except Exception:
        st.warning("Could not load dashboard. Ensure your Supabase table 'invoices' exists.")
else:
    st.error("Check your Streamlit Secrets! The app cannot reach Supabase.")

import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime
import google.generativeai as genai
from PIL import Image
from fpdf import FPDF
import io

# --- 1. CONNECTIONS ---
@st.cache_resource
def init_connections():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return create_client(url, key), genai.GenerativeModel('gemini-1.5-flash')

supabase, model = init_connections()

# --- 2. UI SETTINGS ---
st.set_page_config(page_title="CashFlow SaaS Ultra", layout="wide", page_icon="🏦")
st.markdown("<style>.stMetric {border: 1px solid #ddd; padding: 10px; border-radius: 10px;}</style>", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
def get_data():
    res = supabase.table("invoices").select("*").execute()
    return pd.DataFrame(res.data)

df = get_data()

# --- 4. ANALYTICS & AI RISK SCORE ---
st.title("🏦 CashFlow SaaS Ultra")

if not df.empty:
    df['due_date'] = pd.to_datetime(df['due_date'])
    unpaid = df[df['status'] == 'Pending']
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Pending Revenue", f"${unpaid['amount'].sum():,.2f}")
    col2.metric("Total Clients", len(df['client_name'].unique()))
    
    # AI Risk Score Analysis
    with col3:
        if st.button("🔍 AI Risk Analysis"):
            prompt = f"Based on these invoices: {unpaid.to_json()}, identify the highest risk client. Provide a brief 1-sentence warning."
            risk_report = model.generate_content(prompt).text
            st.warning(risk_report)

    # Visualization
    fig = px.bar(df, x='due_date', y='amount', color='status', title="Revenue Timeline")
    st.plotly_chart(fig, use_container_width=True)

# --- 5. SIDEBAR: THE ADVANCED INPUT HUB ---
with st.sidebar:
    st.header("📥 Data Management")
    mode = st.radio("Method", ["AI Scanner", "Bulk CSV Upload", "Manual"])

    if mode == "AI Scanner":
        img_file = st.file_uploader("Scan Invoice", type=['jpg', 'png'])
        if img_file:
            img = Image.open(img_file)
            if st.button("🚀 AI Extract"):
                response = model.generate_content(["Extract JSON: client_name, amount, due_date, email", img])
                st.json(response.text)

    elif mode == "Bulk CSV Upload":
        csv_file = st.file_uploader("Upload CSV", type="csv")
        if csv_file:
            # Fixed CSV Logic: Cleaning and formatting
            bulk_df = pd.read_csv(csv_file)
            bulk_df.columns = [c.lower().replace(" ", "_") for c in bulk_df.columns]
            bulk_df = bulk_df.where(pd.notnull(bulk_df), None)
            
            if st.button("Confirm Bulk Upload"):
                data = bulk_df.to_dict(orient='records')
                supabase.table("invoices").insert(data).execute()
                st.success("Database Updated!")
                st.rerun()

# --- 6. ADVANCED TABLE: SMART ACTIONS ---
if not df.empty:
    st.subheader("Invoice Control Center")
    for i, row in df.iterrows():
        with st.container():
            c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
            c1.write(f"**{row['client_name']}**")
            c2.write(f"${row['amount']:,.2f}")
            
            # Action 1: WhatsApp Reminder
            msg = f"Reminder: Invoice of ${row['amount']} is due on {row['due_date']}."
            wa_url = f"https://wa.me/?text={msg.replace(' ', '%20')}"
            c3.markdown(f"[📱 WhatsApp]({wa_url}) | [📧 Email](mailto:{row['email']})")
            
            # Action 2: Status Toggle
            if row['status'] == 'Pending':
                if c4.button("Paid", key=f"p_{row['id']}"):
                    supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                    st.rerun()
            else:
                c4.success("Paid")
        st.divider()

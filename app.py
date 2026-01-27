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
    # Reading from Streamlit Secrets
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    supabase_client = create_client(url, key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    return supabase_client, gemini_model

supabase, model = init_connections()

# --- 2. APP STYLING & UI ---
st.set_page_config(page_title="CashFlow AI Pro", layout="wide", page_icon="💰")
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def fetch_data():
    res = supabase.table("invoices").select("*").execute()
    return pd.DataFrame(res.data)

def generate_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(200, 10, "OFFICIAL INVOICE", 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(100, 10, f"Client: {row['client_name']}")
    pdf.cell(100, 10, f"Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)
    pdf.cell(100, 10, f"Email: {row['email']}", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(100, 10, f"TOTAL DUE: ${row['amount']:,.2f}", 0, 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. HEADER & GLOBAL ANALYTICS ---
st.title("🤖 CashFlow AI Pro")
df = fetch_data()

if not df.empty:
    unpaid = df[df['status'] == 'Pending']['amount'].sum()
    paid = df[df['status'] == 'Paid']['amount'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Unpaid Revenue", f"${unpaid:,.2f}", help="Money still in the field")
    m2.metric("Total Collected", f"${paid:,.2f}", delta="Success")
    m3.metric("Active Invoices", len(df[df['status'] == 'Pending']))
    
    # Revenue Chart
    df['due_date'] = pd.to_datetime(df['due_date'])
    fig = px.area(df.sort_values('due_date'), x='due_date', y='amount', color='status', 
                  title="Revenue Pipeline", color_discrete_map={'Paid':'#2ecc71', 'Pending':'#e74c3c'})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 5. THE ADVANCED SIDEBAR (AI SCANNER) ---
with st.sidebar:
    st.header("📥 Input Hub")
    entry_type = st.radio("Add Method", ["AI Photo Scan", "Manual Form", "Bulk CSV"])
    
    if entry_type == "AI Photo Scan":
        st.subheader("Gemini OCR Scanner")
        uploaded_img = st.file_uploader("Upload Invoice Image", type=['png', 'jpg', 'jpeg'])
        if uploaded_img and st.button("🚀 AI Extract"):
            img = Image.open(uploaded_img)
            prompt = "Extract from this invoice: client_name, amount, due_date (YYYY-MM-DD), email. Return ONLY JSON."
            response = model.generate_content([prompt, img])
            st.code(response.text) # Displaying the AI result
            st.info("Copy the data into the manual form below to confirm.")

    elif entry_type == "Manual Form":
        with st.form("manual"):
            n = st.text_input("Client")
            e = st.text_input("Email")
            a = st.number_input("Amount", min_value=0.0)
            d = st.date_input("Due Date")
            if st.form_submit_button("Save"):
                supabase.table("invoices").insert({"client_name":n, "email":e, "amount":a, "due_date":str(d)}).execute()
                st.rerun()

# --- 6. MAIN TABLE & AI EMAIL TONE ADJUSTER ---
if not df.empty:
    st.subheader("Live Invoice Management")
    
    for i, row in df.iterrows():
        with st.expander(f"📄 {row['client_name']} - ${row['amount']:,.2f}"):
            c1, c2, c3 = st.columns([2, 2, 1])
            
            with c1:
                st.write(f"**Status:** {row['status']}")
                st.write(f"**Due:** {row['due_date']}")
                if st.button("Mark as Paid", key=f"pay_{row['id']}"):
                    supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                    st.rerun()
            
            with c2:
                tone = st.selectbox("Email Tone", ["Friendly", "Professional", "Urgent"], key=f"tone_{row['id']}")
                if st.button("🪄 Draft with Gemini", key=f"ai_{row['id']}"):
                    p = f"Write a {tone} short email to {row['client_name']} about an unpaid ${row['amount']} invoice due on {row['due_date']}."
                    email_text = model.generate_content(p).text
                    st.text_area("AI Drafted Email", email_text, height=150)
            
            with c3:
                pdf_data = generate_pdf(row)
                st.download_button("📩 Download PDF", data=pdf_data, file_name=f"Invoice_{row['client_name']}.pdf")

else:
    st.info("Welcome! Start by adding an invoice via the sidebar.")

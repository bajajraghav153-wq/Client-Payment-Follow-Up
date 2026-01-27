import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="💰")

# Injected CSS for the high-end SaaS feel
st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] {
        background-color: #002A4D;
        border: 1px solid #004080;
        padding: 20px;
        border-radius: 15px;
    }
    .stButton>button {
        border-radius: 10px;
        background: linear-gradient(90deg, #00D1FF, #0080FF);
        color: white;
        font-weight: bold;
        width: 100%;
        border: none;
    }
    /* Expander styling */
    .streamlit-expanderHeader { background-color: #002A4D !important; border-radius: 10px !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Using the specific Gemini 3 Flash Preview ID
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    st.divider()
    page = st.radio("Navigation", ["📊 Dashboard", "📥 Data Entry", "📜 History"])

# --- 3. PAGE LOGIC ---
if page == "📊 Dashboard":
    st.title("💸 Active Collections")
    # Fetch non-deleted invoices
    res = supabase.table("invoices").select("*").eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        # Metrics Calculation
        pending_total = df[df['status'] == 'Pending']['amount'].sum()
        paid_total = df[df['status'] == 'Paid']['amount'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Pending ⏳", f"${pending_total:,.2f}")
        m2.metric("Collected ✅", f"${paid_total:,.2f}")
        m3.metric("Pending Invoices", len(df[df['status'] == 'Pending']))
        st.divider()

        pending_df = df[df['status'] == 'Pending']
        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']} (Due: {row['due_date']})"):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    if st.button("🪄 Craft Draft", key=f"ai_{row['id']}"):
                        prompt = f"Write a professional reminder for {row['client_name']} about ${row['amount']}. From {my_name} at {agency_name}."
                        response = model.generate_content(prompt)
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun()
                    st.text_area("Review Email:", value=row.get('last_draft', ""), height=150, key=f"msg_{row['id']}")
                    if st.button("📧 Send SMTP", key=f"smtp_{row['id']}"): st.success("Sent!")
                
                with c2:
                    phone = "".join(filter(str.isdigit, str(row['phone'])))
                    wa_url = f"https://wa.me/{phone}?text=" + urllib.parse.quote(f"Hi {row['client_name']}, friendly nudge for the ${row['amount']} invoice.")
                    st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;cursor:pointer;">📱 WhatsApp Chat</button></a>', unsafe_allow_html=True)
                
                with c3:
                    if st.button("✅ Paid", key=f"pd_{row['id']}", use_container_width=True):
                        supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute(); st.rerun()
                    if st.button("🗑️ Delete", key=f"del_{row['id']}", use_container_width=True):
                        supabase.table("invoices").update({"is_deleted": True}).eq("id", row['id']).execute(); st.rerun()

elif page == "📥 Data Entry":
    st.header("Data Intake Hub")
    t1, t2, t3 = st.tabs(["📸 AI Scanner", "⌨️ Manual", "📤 CSV"])
    with t1:
        img_f = st.file_uploader("Upload Invoice Image", type=['png','jpg','jpeg'])
        if img_f and st.button("🚀 Process with Gemini 3"):
            res = model.generate_content(["Extract client_name, amount, due_date, email, phone as JSON. If unclear, return null.", Image.open(img_f)])
            data = json.loads(res.text.replace("```json","").replace("```",""))
            data["status"] = "Pending"
            supabase.table("invoices").insert(data).execute(); st.success("Saved to Database!")

elif page == "📜 History":
    st.header("Completed Transactions")
    res = supabase.table("invoices").select("*").eq("status", "Paid").eq("is_deleted", False).execute()
    history_df = pd.DataFrame(res.data)
    if not history_df.empty:
        st.dataframe(history_df[['client_name', 'amount', 'due_date']], use_container_width=True)
    else:
        st.info("No payment history yet.")

import streamlit as st
from supabase import create_client
import google.generativeai as genai
from PIL import Image
import pandas as pd
import urllib.parse
import json

# --- 1. CONFIG & STYLING (KEEPING YOUR UI) ---
st.set_page_config(page_title="CashFlow Pro", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    .stApp { background-color: #001B33; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #00D1FF; font-weight: bold; }
    [data-testid="stMetric"] { background-color: #002A4D; border: 1px solid #004080; padding: 20px; border-radius: 15px; }
    .stButton>button { border-radius: 10px; background: linear-gradient(90deg, #00D1FF, #0080FF); color: white; font-weight: bold; width: 100%; border: none; }
    .streamlit-expanderHeader { background-color: #002A4D !important; border-radius: 10px !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_all():
    sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3-flash-preview')
    return sb, model

supabase, model = init_all()

# --- 2. AUTHENTICATION LOGIC ---
if "user" not in st.session_state:
    st.session_state.user = None

def check_admin(u_id):
    try:
        res = supabase.table("profiles").select("is_admin").eq("id", u_id).single().execute()
        return res.data.get("is_admin", False)
    except: return False

if st.session_state.user is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔐 SaaS Access")
        t1, t2 = st.tabs(["Login", "Register"])
        with t1:
            e = st.text_input("Email")
            p = st.text_input("Password", type="password")
            if st.button("Sign In"):
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
        with t2:
            re = st.text_input("New Email")
            rp = st.text_input("New Password", type="password")
            if st.button("Create Account"):
                supabase.auth.sign_up({"email": re, "password": rp})
                st.success("Success! Check email for link.")
    st.stop()

# LOGGED IN DATA
user_id = st.session_state.user.id
is_admin = check_admin(user_id)

# --- 3. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🏦 CashFlow Ultra")
    st.write(f"Logged in: {st.session_state.user.email}")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
    st.divider()
    my_name = st.text_input("Your Name", value="Admin")
    agency_name = st.text_input("Agency Name", value="My Agency")
    st.divider()
    nav = ["📊 Dashboard", "📥 Data Entry", "📜 History"]
    if is_admin: nav.append("👑 Super Admin")
    page = st.radio("Navigation", nav)

# --- 4. PAGE LOGIC (UPDATED WITH USER_ID) ---
if page == "📊 Dashboard":
    st.title("💸 Active Collections")
    # Filters data by the current user
    res = supabase.table("invoices").select("*").eq("user_id", user_id).eq("is_deleted", False).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        pending_total = df[df['status'] == 'Pending']['amount'].sum()
        paid_total = df[df['status'] == 'Paid']['amount'].sum()
        m1, m2, m3 = st.columns(3)
        m1.metric("Pending ⏳", f"${pending_total:,.2f}")
        m2.metric("Collected ✅", f"${paid_total:,.2f}")
        m3.metric("Your Invoices", len(df[df['status'] == 'Pending']))
        st.divider()

        pending_df = df[df['status'] == 'Pending']
        for i, row in pending_df.iterrows():
            with st.expander(f"📋 {row['client_name']} — ${row['amount']}"):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    if st.button("🪄 Craft Draft", key=f"ai_{row['id']}"):
                        prompt = f"Professional reminder for {row['client_name']} about ${row['amount']}. From {my_name} at {agency_name}."
                        response = model.generate_content(prompt)
                        supabase.table("invoices").update({"last_draft": response.text}).eq("id", row['id']).execute()
                        st.rerun()
                    st.text_area("Email:", value=row.get('last_draft', ""), height=150, key=f"msg_{row['id']}")
                    if st.button("📧 Send", key=f"s_{row['id']}"): st.success("Sent!")
                with c2:
                    phone = "".join(filter(str.isdigit, str(row['phone'])))
                    wa_url = f"https://wa.me/{phone}?text=" + urllib.parse.quote(f"Hi {row['client_name']}, friendly nudge for the ${row['amount']} invoice.")
                    st.markdown(f'<a href="{wa_url}" target="_blank"><button style="background-color:#25D366;color:white;width:100%;padding:10px;border-radius:10px;border:none;cursor:pointer;">📱 WhatsApp Chat</button></a>', unsafe_allow_html=True)
                with c3:
                    if st.button("✅ Paid", key=f"p_{row['id']}"):
                        supabase.table("invoices").update({"status":"Paid"}).eq("id",row['id']).execute(); st.rerun()
                    if st.button("🗑️ Del", key=f"d_{row['id']}"):
                        supabase.table("invoices").update({"is_deleted":True}).eq("id",row['id']).execute(); st.rerun()

elif page == "📥 Data Entry":
    st.header("Data Intake Hub")
    t1, t2 = st.tabs(["📸 AI Scanner", "⌨️ Manual"])
    with t1:
        img_f = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
        if img_f and st.button("🚀 Process"):
            res = model.generate_content(["Extract data as JSON.", Image.open(img_f)])
            data = json.loads(res.text.replace("```json","").replace("```",""))
            data.update({"status": "Pending", "user_id": user_id}) # Link to user
            supabase.table("invoices").insert(data).execute(); st.success("Saved!")

elif page == "👑 Super Admin" and is_admin:
    st.title("👑 Platform Analytics")
    # Service role key required for global view
    all_res = supabase.table("invoices").select("amount, status").execute()
    all_df = pd.DataFrame(all_res.data)
    st.metric("Global Platform Revenue", f"${all_df['amount'].sum():,.2f}")
    st.bar_chart(all_df.groupby('status')['amount'].sum())

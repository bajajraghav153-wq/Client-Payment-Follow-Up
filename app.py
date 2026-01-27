import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# 1. SETUP - Replace these with your actual Supabase details
URL = "YOUR_SUPABASE_URL"
KEY = "YOUR_SUPABASE_KEY"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="CashFlow Sentinel", layout="wide")

st.title("💸 Client Payment Tracker")
st.markdown("Track invoices and generate reminder emails instantly.")

# --- SIDEBAR: ADD NEW INVOICE ---
with st.sidebar:
    st.header("Add New Invoice")
    with st.form("invoice_form"):
        c_name = st.text_input("Client Name")
        c_email = st.text_input("Client Email")
        amt = st.number_input("Amount ($)", min_value=0.0)
        d_date = st.date_input("Due Date")
        submit = st.form_submit_button("Save Invoice")

        if submit:
            data = {
                "client_name": c_name,
                "email": c_email,
                "amount": amt,
                "due_date": str(d_date),
                "status": "Pending"
            }
            supabase.table("invoices").insert(data).execute()
            st.success("Invoice Saved!")
            st.rerun()

# --- MAIN DASHBOARD ---
st.subheader("Your Invoices")
response = supabase.table("invoices").select("*").execute()
df = pd.DataFrame(response.data)

if not df.empty:
    # Formatting for display
    df = df[['client_name', 'amount', 'due_date', 'email', 'status', 'id']]
    
    # Display Table
    for index, row in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 2, 1])
        with col1: st.write(f"**{row['client_name']}**")
        with col2: st.write(f"${row['amount']}")
        with col3: st.write(row['due_date'])
        with col4: 
            # Logic for automated email text
            subject = f"Follow up: Invoice for {row['client_name']}"
            body = f"Hi {row['client_name']}, hope you are well. Just a friendly reminder that your invoice for ${row['amount']} is due on {row['due_date']}. Thanks!"
            mail_link = f"mailto:{row['email']}?subject={subject}&body={body}"
            st.markdown(f"[Generate Reminder Email]({mail_link})")
        with col5:
            if st.button("Mark Paid", key=row['id']):
                supabase.table("invoices").update({"status": "Paid"}).eq("id", row['id']).execute()
                st.rerun()
else:
    st.info("No invoices found. Add one in the sidebar!")
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Finedata Order Manager", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Fetch existing data
df = conn.read()

st.title("🚀 Finedata Production Dashboard")

# --- TOP METRICS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Orders", len(df))
with col2:
    pending = len(df[df['Status'] == 'Pending'])
    st.metric("Pending Production", pending)
with col3:
    total_profit = len(df) * 800
    st.metric("Total Net Profit (ETB)", f"{total_profit:,}")

# --- ADD NEW ORDER ---
with st.expander("➕ Add New Order"):
    with st.form("order_form", clear_on_submit=True):
        name = st.text_input("Customer Name")
        contact = st.text_input("Phone Number")
        qty = st.number_input("Quantity", min_value=1, value=1)
        payment = st.selectbox("Payment Status", ["Unpaid", "Paid"])
        
        if st.form_submit_button("Log Order"):
            new_data = pd.DataFrame([{
                "Name": name,
                "Contact": contact,
                "Quantity": qty,
                "Status": "Pending",
                "Payment": payment
            }])
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(data=updated_df)
            st.success(f"Order for {name} saved to Cloud!")
            st.rerun()

# --- ORDER TABLE ---
st.subheader("📋 Order List")
st.dataframe(df, use_container_width=True)

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Page Configuration
st.set_page_config(page_title="Finedata Manager", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. Fetch Data with Safety Check
try:
    df = conn.read(ttl=0)
    # If the sheet is empty or columns are missing, initialize them
    required_cols = ["Name", "Contact", "Qty", "Payment", "Status", "Total"]
    if df is None or df.empty or not set(required_cols).issubset(df.columns):
        df = pd.DataFrame(columns=required_cols)
except Exception as e:
    df = pd.DataFrame(columns=["Name", "Contact", "Qty", "Payment", "Status", "Total"])

st.title("🛡️ Finedata Production & Order Manager")

# --- 📊 ANALYTICS SECTION ---
st.subheader("Business Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Orders", len(df))
with col2:
    # Safe count for Pending
    pending_count = len(df[df['Status'] == 'Pending']) if 'Status' in df.columns else 0
    st.metric("Pending Production", pending_count)
with col3:
    # Safe count for Paid
    paid_count = len(df[df['Payment'] == 'Paid']) if 'Payment' in df.columns else 0
    st.metric("Paid Orders", paid_count)
with col4:
    # Based on your 800 ETB net profit per card
    net_profit = len(df) * 800
    st.metric("Estimated Net Profit (ETB)", f"{net_profit:,}")

st.divider()

# --- ➕ SIDEBAR: ADD NEW ORDER ---
with st.sidebar:
    st.header("Add New Order")
    with st.form("add_form", clear_on_submit=True):
        new_name = st.text_input("Customer Name")
        new_phone = st.text_input("Phone Number")
        new_qty = st.number_input("Quantity", min_value=1, value=1)
        new_pay = st.selectbox("Payment", ["Paid", "Unpaid"])
        new_status = st.selectbox("Status", ["Pending", "Printing", "Ready", "Delivered"])
        
        if st.form_submit_button("Save Order"):
            if new_name and new_phone:
                new_row = pd.DataFrame([{
                    "Name": new_name,
                    "Contact": new_phone,
                    "Qty": new_qty,
                    "Payment": new_pay,
                    "Status": new_status,
                    "Total": new_qty * 1200 # Assuming 1200 is sale price
                }])
                # Combine and Update
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"Order for {new_name} saved!")
                st.rerun()
            else:
                st.error("Please enter Name and Phone.")

# --- 🔍 SEARCH & UPDATE SECTION ---
st.subheader("Current Order Pipeline")

# Search Functionality
search_query = st.text_input("🔍 Search by Name or Phone")
if search_query:
    display_df = df[df.apply(lambda row: search_query.lower() in str(row).lower(), axis=1)]
else:
    display_df = df

# Interactive Data Editor
if not display_df.empty:
    st.info("💡 You can edit cells directly. Click 'Save Changes' below to update the cloud.")
    edited_df = st.data_editor(
        display_df, 
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Production Status",
                options=["Pending", "Printing", "Ready", "Delivered"],
                required=True,
            ),
            "Payment": st.column_config.SelectboxColumn(
                "Money Status",
                options=["Paid", "Unpaid"],
                required=True,
            ),
            "Contact": st.column_config.TextColumn("Phone Number")
        }
    )

    if st.button("💾 Save Changes to Cloud"):
        # We update the full dataframe based on the edits
        # Note: In a production app with huge data, we'd update only changed rows.
        # But for your current scale, this is the most reliable 'Bam' method.
        conn.update(data=edited_df)
        st.success("Cloud Database Updated!")
        st.rerun()
else:
    st.warning("No orders found in the database.")

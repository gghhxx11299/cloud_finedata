import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Page Config
st.set_page_config(page_title="Finedata Manager", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. Fetch Data (ttl=0 ensures we see changes immediately)
try:
    df = conn.read(ttl=0)
except:
    # If sheet is empty, create a placeholder
    df = pd.DataFrame(columns=["Name", "Contact", "Qty", "Payment", "Status", "Total"])

st.title("🛡️ Finedata Production & Order Manager")
st.markdown(f"**Connected to:** `{st.secrets['connections']['gsheets']['spreadsheet']}`")

# --- 📊 ANALYTICS SECTION ---
st.subheader("Business Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Orders", len(df))
with col2:
    pending = len(df[df['Status'] == 'Pending'])
    st.metric("Pending Production", pending, delta_color="inverse")
with col3:
    paid_orders = len(df[df['Payment'] == 'Paid'])
    st.metric("Paid Orders", paid_orders)
with col4:
    # Assuming 1200 ETB price and 800 ETB profit
    net_profit = len(df) * 800
    st.metric("Net Profit (ETB)", f"{net_profit:,}")

st.divider()

# --- ➕ ADD NEW ORDER ---
with st.sidebar:
    st.header("Add New Order")
    with st.form("add_form", clear_on_submit=True):
        new_name = st.text_input("Customer Name")
        new_phone = st.text_input("Phone Number")
        new_qty = st.number_input("Quantity", min_value=1, value=1)
        new_pay = st.selectbox("Payment", ["Paid", "Unpaid"])
        new_status = st.selectbox("Status", ["Pending", "Printing", "Ready", "Delivered"])
        
        if st.form_submit_button("Save Order"):
            new_row = pd.DataFrame([{
                "Name": new_name,
                "Contact": new_phone,
                "Qty": new_qty,
                "Payment": new_pay,
                "Status": new_status,
                "Total": new_qty * 1200
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.toast("Order Added Successfully!")
            st.rerun()

# --- 🔍 SEARCH & UPDATE SECTION ---
st.subheader("Current Order Pipeline")

# Search bar
search_query = st.text_input("🔍 Search by Name or Phone")
if search_query:
    display_df = df[df.apply(lambda row: search_query.lower() in str(row).lower(), axis=1)]
else:
    display_df = df

# Display Interactive Table
if not display_df.empty:
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
            )
        }
    )

    if st.button("💾 Save Changes to Cloud"):
        conn.update(data=edited_df)
        st.success("Cloud Database Updated!")
        st.rerun()
else:
    st.info("No orders found. Add your first order from the sidebar!")

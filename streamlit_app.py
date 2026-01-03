import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="FINEDA HQ", layout="wide", page_icon="📈")

# --- 1. AUTHENTICATION ---
if "password_correct" not in st.session_state:
    st.title("🛡️ FineData HQ Login")
    pwd = st.text_input("Admin Password", type="password")
    if st.button("Access"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.session_state["user"] = "admin"
            st.rerun()
        else:
            st.error("Access Denied")
    st.stop()

# --- 2. DATA CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Read Main Orders Sheet
df = conn.read(ttl=0).astype(str)

# Ensure essential columns exist (in case of blank sheet)
essential_cols = [
    'Name', 'Contact', 'Qty', 'Stage', 'Total', 'Biker',
    'Order Time', 'Order_ID', 'Paid', 'Called', 'Exported',
    'Called_At', 'Image_front', 'Image_back'
]
for col in essential_cols:
    if col not in df.columns:
        if col in ['Image_front', 'Image_back']:
            df[col] = "None"
        elif col in ['Paid', 'Called', 'Exported']:
            df[col] = "No"
        elif col == 'Called_At':
            df[col] = ""
        else:
            df[col] = ""

# Read Expenses Sheet
try:
    expenses_df = conn.read(worksheet="Expenses", ttl=0).astype(str)
    if "Category" not in expenses_df.columns:
        expenses_df["Category"] = "General"
except:
    expenses_df = pd.DataFrame(columns=["Date", "Amount", "Recipient", "Note", "Category"])

# --- 3. DATA CLEANING & CALCULATIONS ---
df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)

# Supplier debt logic (400 ETB/unit for Printing/Ready/Delivered)
produced_df = df[df['Stage'].isin(['Printing', 'Ready', 'Delivered'])]
total_production_cost = produced_df['Qty_num'].sum() * 400
total_paid_to_supplier = pd.to_numeric(
    expenses_df[expenses_df['Category'] == 'Supplier']['Amount'], errors='coerce'
).sum()
current_debt = total_production_cost - total_paid_to_supplier

# Inventory estimate (optional)
initial_stock = 10_000
fulfilled_qty = df[df['Stage'] == 'Delivered']['Qty_num'].sum()
estimated_stock = max(0, initial_stock - fulfilled_qty)

now = datetime.now()

# --- Helper Functions ---
def save_main_df(df_to_save):
    # Keep ONLY columns that exist in your sheet (avoid adding unwanted ones)
    cols_to_keep = [
        'Name', 'Contact', 'Qty', 'money', 'Stage', 'Total', 'Biker',
        'Order Time', 'Order_ID', 'Paid', 'Called', 'Exported',
        'Called_At', 'Image_front', 'Image_back'
    ]
    # Preserve 'money' even if unused (to avoid breaking your sheet)
    output_df = df_to_save[cols_to_keep].copy()
    conn.update(data=output_df)

def save_expenses_df(edf):
    conn.update(worksheet="Expenses", data=edf)

# --- 4. NAVIGATION ---
page = st.sidebar.radio("Navigation", [
    "📊 Dashboard",
    "📜 Order Logs",
    "👥 Customer CRM",
    "🎨 Design Vault",
    "📤 Supplier Export",
    "💸 Financial Tracker",
    "📝 New Entry",
    "🔄 Bulk Actions"
])

# --- PAGE: DASHBOARD ---
if page == "📊 Dashboard":
    st.header("Business Intelligence")
    cash = df[df['Paid'] == 'Yes']['Total_num'].sum()
    receivables = df[df['Paid'] != 'Yes']['Total_num'].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Cash on Hand", f"{cash:,.0f} ETB")
    c2.metric("⏳ Receivables", f"{receivables:,.0f} ETB")
    c3.metric("🏭 Supplier Debt", f"{current_debt:,.0f} ETB")
    c4.metric("📦 Est. Inventory", f"{int(estimated_stock)} units")

    st.subheader("Order Status Breakdown")
    status_counts = df['Stage'].value_counts()
    st.bar_chart(status_counts)

# --- PAGE: ORDER LOGS ---
elif page == "📜 Order Logs":
    st.header("Order Management")
    search = st.text_input("🔍 Search (Name, Contact, Order_ID)")
    if search:
        filtered = df[
            df['Name'].str.contains(search, case=False, na=False) |
            df['Contact'].str.contains(search, case=False, na=False) |
            df['Order_ID'].str.contains(search, case=False, na=False)
        ]
    else:
        filtered = df.copy()

    st.dataframe(
        filtered[[
            'Order_ID', 'Name', 'Contact', 'Qty', 'Total',
            'Paid', 'Stage', 'Called', 'Biker'
        ]].sort_values('Stage'),
        use_container_width=True,
        hide_index=True
    )

    st.divider()
    selected_id = st.selectbox("Select Order to Update", [""] + list(filtered['Order_ID'].unique()))
    if selected_id:
        row = df[df['Order_ID'] == selected_id].iloc[0]
        new_stage = st.selectbox(
            "Update Stage",
            ["Pending", "Printing", "Ready", "Delivered"],
            index=["Pending", "Printing", "Ready", "Delivered"].index(row['Stage'])
        )
        if st.button("🔄 Update Stage"):
            df.loc[df['Order_ID'] == selected_id, 'Stage'] = new_stage
            save_main_df(df)
            st.success("Stage updated!")
            st.rerun()

        if st.button("📞 Mark as Called"):
            df.loc[df['Order_ID'] == selected_id, 'Called'] = "Yes"
            df.loc[df['Order_ID'] == selected_id, 'Called_At'] = now.strftime("%Y-%m-%d %H:%M")
            save_main_df(df)
            st.success("Call logged!")
            st.rerun()

        v1, v2 = st.columns(2)
        if row['Image_front'] != "None":
            v1.link_button("👁️ Front", row['Image_front'])
        if row['Image_back'] != "None":
            v2.link_button("👁️ Back", row['Image_back'])

# --- PAGE: CUSTOMER CRM ---
elif page == "👥 Customer CRM":
    st.header("Customer Relationship Manager")
    customer = st.selectbox("Select Customer", sorted(df['Name'].dropna().unique()))
    if customer:
        cust_orders = df[df['Name'] == customer].sort_values('Order Time', ascending=False)
        st.write(f"**{len(cust_orders)} orders** from {customer}")
        st.dataframe(
            cust_orders[[
                'Order_ID', 'Contact', 'Qty', 'Total', 'Stage', 'Paid'
            ]],
            use_container_width=True,
            hide_index=True
        )

# --- PAGE: DESIGN VAULT ---
elif page == "🎨 Design Vault":
    st.header("Design Link Manager")
    target_id = st.selectbox("Select Order ID", [""] + list(df['Order_ID'].unique()))
    if target_id:
        idx = df[df['Order_ID'] == target_id].index[0]
        st.info(f"Filename hint: **{target_id}-image-front.jpg**")
        f_link = st.text_input("Front Link", value=df.at[idx, 'Image_front'])
        b_link = st.text_input("Back Link", value=df.at[idx, 'Image_back'])
        if st.button("💾 Save"):
            df.at[idx, 'Image_front'] = f_link or "None"
            df.at[idx, 'Image_back'] = b_link or "None"
            save_main_df(df)
            st.success("Saved!")
            st.rerun()

# --- PAGE: SUPPLIER EXPORT ---
elif page == "📤 Supplier Export":
    st.header("📤 Export New Orders (Stage = Pending & Not Exported)")
    mask = (df['Exported'] == "No") & (df['Stage'] == "Pending")
    to_export = df[mask].copy()

    if not to_export.empty:
        st.write(f"📦 {len(to_export)} orders ready for supplier")
        st.dataframe(to_export[['Order_ID', 'Name', 'Qty', 'Total']], use_container_width=True, hide_index=True)
        csv = to_export.to_csv(index=False).encode('utf-8')
        filename = f"supplier_batch_{now.strftime('%Y%m%d_%H%M')}.csv"
        if st.download_button("📥 Download & Mark Exported", data=csv, file_name=filename, mime="text/csv"):
            df.loc[mask, 'Exported'] = "Yes"
            save_main_df(df)
            st.success("Exported and marked!")
            st.rerun()
    else:
        st.success("✅ No new orders to export.")

# --- PAGE: FINANCIAL TRACKER ---
elif page == "💸 Financial Tracker":
    st.header("Financial Operations")
    tab1, tab2 = st.tabs(["💰 Add Expense", "📈 Reports"])

    with tab1:
        st.metric("🏭 Supplier Debt", f"{current_debt:,.0f} ETB")
        with st.form("payout_form"):
            cols = st.columns(2)
            amt = cols[0].number_input("Amount (ETB)", min_value=0)
            cat = cols[1].selectbox("Category", ["Supplier", "Delivery", "Marketing", "Misc"])
            note = st.text_input("Reference/Note")
            if st.form_submit_button("➕ Add Expense"):
                new_exp = pd.DataFrame([{
                    "Date": now.strftime("%Y-%m-%d"),
                    "Amount": str(amt),
                    "Recipient": "N/A",
                    "Note": note,
                    "Category": cat
                }])
                expenses_df = pd.concat([expenses_df, new_exp], ignore_index=True)
                save_expenses_df(expenses_df)
                st.success("Recorded!")
                st.rerun()

    with tab2:
        if not expenses_df.empty:
            expenses_df['Amount_num'] = pd.to_numeric(expenses_df['Amount'], errors='coerce')
            summary = expenses_df.groupby('Category')['Amount_num'].sum()
            st.subheader("Expense by Category")
            st.bar_chart(summary)
            st.dataframe(
                expenses_df[['Date', 'Category', 'Amount', 'Note']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No expenses recorded yet.")

# --- PAGE: NEW ENTRY ---
elif page == "📝 New Entry":
    st.header("➕ Add New Order")
    with st.form("new_order"):
        oid = st.text_input("Order ID", value=f"FD-{len(df) + 1}")
        name = st.text_input("Customer Name")
        contact = st.text_input("Contact (Phone/Email)")
        qty = st.number_input("Quantity", min_value=1, value=1)
        total = st.number_input("Total (ETB)", min_value=0.0, value=0.0, step=10.0)
        biker = st.text_input("Biker (Optional)")

        if st.form_submit_button("✅ Add Order"):
            new_row = pd.DataFrame([{
                'Name': name,
                'Contact': contact,
                'Qty': str(int(qty)),
                'money': "",  # keep blank or copy Total if needed
                'Stage': "Pending",
                'Total': str(total),
                'Biker': biker,
                'Order Time': now.strftime("%Y-%m-%d %H:%M"),
                'Order_ID': oid,
                'Paid': "No",
                'Called': "No",
                'Exported': "No",
                'Called_At': "",
                'Image_front': "None",
                'Image_back': "None"
            }])
            final_df = pd.concat([df, new_row], ignore_index=True)
            save_main_df(final_df)
            st.success(f"✅ Order {oid} added!")
            st.rerun()

# --- PAGE: BULK ACTIONS ---
elif page == "🔄 Bulk Actions":
    st.header("🔄 Bulk Operations")
    selected_ids = st.multiselect("Choose Order IDs", df['Order_ID'].tolist())
    if selected_ids:
        action = st.radio("Action", ["Mark as Paid", "Mark as Exported", "Set Stage"])
        confirm = False
        if action == "Set Stage":
            new_stage = st.selectbox("Stage", ["Pending", "Printing", "Ready", "Delivered"])
            confirm = st.button("🚀 Apply to Selected")
        else:
            confirm = st.button(f"🚀 {action}")

        if confirm:
            mask = df['Order_ID'].isin(selected_ids)
            if action == "Mark as Paid":
                df.loc[mask, 'Paid'] = "Yes"
            elif action == "Mark as Exported":
                df.loc[mask, 'Exported'] = "Yes"
            elif action == "Set Stage":
                df.loc[mask, 'Stage'] = new_stage
            save_main_df(df)
            st.success(f"Updated {len(selected_ids)} orders!")
            st.rerun()

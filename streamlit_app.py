import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="FINEDA HQ", layout="wide")

# Authentication
if "password_correct" not in st.session_state:
    st.title("🛡️ FineData HQ Login")
    pwd = st.text_input("Admin Password", type="password")
    if st.button("Access"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Denied")
    st.stop()

# Connection
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0).astype(str)

# Ensure new columns exist
for col in ['Exported', 'Called']:
    if col not in df.columns:
        df[col] = "No"

try:
    expenses_df = conn.read(worksheet="Expenses", ttl=0).astype(str)
except:
    expenses_df = pd.DataFrame(columns=["Date", "Amount", "Recipient", "Note"])

# Data Processing
df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
# Convert to datetime for logic, but we keep the string format for saving
df['Order Time DT'] = pd.to_datetime(df['Order Time'], errors='coerce')
exp_total = pd.to_numeric(expenses_df['Amount'], errors='coerce').sum()
now = datetime.now()

# Sidebar Navigation
page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs", "📤 Supplier Export", "💸 Supplier Payouts", "📝 New Entry"])

if page == "📊 Dashboard":
    st.header("Business Intelligence")
    
    cash_on_hand = df[df['Paid'] == 'Yes']['Total_num'].sum()
    receivables = df[df['Paid'] != 'Yes']['Total_num'].sum()
    produced_qty = df[df['Stage'].isin(['Printing', 'Ready', 'Delivered'])]['Qty_num'].sum()
    gross_debt = produced_qty * 400
    current_debt = gross_debt - exp_total

    f1, f2, f3 = st.columns(3)
    f1.metric("💵 Cash on Hand", f"{cash_on_hand:,} ETB")
    f2.metric("⏳ To be Collected", f"{receivables:,} ETB")
    f3.metric("🏭 Supplier Debt", f"{current_debt:,} ETB", delta=f"Paid: {exp_total:,}")

elif page == "📜 Order Logs":
    st.header("Order Management")
    search = st.text_input("🔍 Search")
    filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
    st.dataframe(filtered.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore'), use_container_width=True, hide_index=True)
    
    st.divider()
    order_id = st.selectbox("Select Order ID to Edit", ["Select..."] + list(df['Order_ID'].unique()))
    if order_id != "Select...":
        idx = df[df['Order_ID'] == order_id].index[0]
        curr = df.loc[idx]
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            u_stage = c1.selectbox("Stage", ["Pending", "Printing", "Ready", "Delivered", "Hold"], index=["Pending", "Printing", "Ready", "Delivered", "Hold"].index(curr['Stage']) if curr['Stage'] in ["Pending", "Printing", "Ready", "Delivered", "Hold"] else 0)
            u_paid = c2.selectbox("Paid", ["No", "Yes", "Partial"], index=["No", "Yes", "Partial"].index(curr['Paid']) if curr['Paid'] in ["No", "Yes", "Partial"] else 0)
            u_called = c3.selectbox("Called Customer?", ["No", "Yes"], index=1 if curr.get('Called') == 'Yes' else 0)
            
            d_conf = c1.selectbox("Design Confirmed?", ["No", "Yes"], index=1 if curr.get('Design_confirmed') == 'Yes' else 0)
            d_fin = c2.selectbox("Design Finished?", ["No", "Yes"], index=1 if curr.get('Designer_finished') == 'Yes' else 0)
            u_biker = c3.text_input("Biker", value=curr['Biker'])
            
            if st.form_submit_button("💾 Save Changes"):
                df.at[idx, 'Stage'] = u_stage
                df.at[idx, 'Paid'] = u_paid
                df.at[idx, 'Called'] = u_called
                df.at[idx, 'Design_confirmed'] = d_conf
                df.at[idx, 'Designer_finished'] = d_fin
                df.at[idx, 'Biker'] = u_biker
                
                save_df = df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore')
                conn.update(data=save_df)
                st.success("Updated!")
                st.rerun()

elif page == "📤 Supplier Export":
    st.header("Supplier CSV Export")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", value=now - timedelta(days=7))
    end_date = col2.date_input("End Date", value=now)
    
    mask = (df['Order Time DT'].dt.date >= start_date) & (df['Order Time DT'].dt.date <= end_date) & (df['Exported'] == "No")
    to_export = df[mask].copy()
    
    if not to_export.empty:
        st.write(f"Found **{len(to_export)}** new orders.")
        st.dataframe(to_export[['Order_ID', 'Name', 'Qty', 'Order Time']], use_container_width=True)
        csv = to_export.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore').to_csv(index=False).encode('utf-8')
        
        if st.download_button("📥 Download Supplier CSV", data=csv, file_name=f"supplier_batch_{now.strftime('%Y%m%d')}.csv", mime="text/csv"):
            df.loc[mask, 'Exported'] = "Yes"
            save_df = df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore')
            conn.update(data=save_df)
            st.success("Orders marked as Exported!")
            st.rerun()
    else:
        st.info("No new orders for this range.")

elif page == "💸 Supplier Payouts":
    st.header("Supplier Payouts")
    with st.form("exp"):
        amount = st.number_input("Amount (ETB)", min_value=0)
        recp = st.text_input("Recipient")
        note = st.text_area("Note")
        if st.form_submit_button("Confirm Payout"):
            new_exp = pd.DataFrame([{"Date": now.strftime("%Y-%m-%d %H:%M"), "Amount": str(amount), "Recipient": recp, "Note": note}])
            conn.update(worksheet="Expenses", data=pd.concat([expenses_df, new_exp], ignore_index=True))
            st.rerun()
    st.dataframe(expenses_df, use_container_width=True)

elif page == "📝 New Entry":
    st.header("New Order")
    with st.form("new"):
        c1, c2 = st.columns(2)
        n_id = c1.text_input("Order_ID")
        n_name = c2.text_input("Name")
        n_phone = c1.text_input("Contact")
        n_qty = c2.number_input("Qty", min_value=1, value=1)
        n_conn = st.checkbox("Needs Designer")
        if st.form_submit_button("Submit"):
            price = n_qty * 1200
            new_row = pd.DataFrame([{
                "Order Time": now.strftime("%Y-%m-%d %H:%M"), 
                "Order_ID": n_id if n_id else f"MAN-{now.strftime('%M%S')}",
                "Name": n_name, "Contact": n_phone, "Qty": str(n_qty), "money": str(price), "Paid": "No",
                "Stage": "Pending", "Total": str(price), "Biker": "Unassigned", "Design_confirmed": "No",
                "Is_connected_designer": "Yes" if n_conn else "No", "Designer_finished": "No", "Exported": "No", "Called": "No"
            }])
            save_df = pd.concat([df.drop(columns=['Qty_num','Total_num', 'Order Time DT'], errors='ignore'), new_row], ignore_index=True)
            conn.update(data=save_df)
            st.rerun()

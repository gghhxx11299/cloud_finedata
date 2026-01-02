import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="FINEDA HQ", layout="wide")

if "password_correct" not in st.session_state:
    st.title("🛡️ FineData HQ Login")
    pwd = st.text_input("Admin Password", type="password")
    if st.button("Access"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Denied")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0).astype(str)

try:
    expenses_df = conn.read(worksheet="Expenses", ttl=0).astype(str)
except:
    expenses_df = pd.DataFrame(columns=["Date", "Amount", "Recipient", "Note"])

df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
df['Order Time'] = pd.to_datetime(df['Order Time'], errors='coerce')
exp_total = pd.to_numeric(expenses_df['Amount'], errors='coerce').sum()
now = datetime.now()

page = st.sidebar.radio("Go To:", ["📊 Dashboard", "📜 Order Logs", "💸 Supplier Payouts", "📝 New Entry"])

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

    st.divider()

    m1, m2, m3 = st.columns(3)
    m1.metric("Ready (Not Delivered)", len(df[(df['Stage'] == 'Ready') & (df['Paid'] == 'Yes')]))
    m2.metric("Delivered", len(df[df['Stage'] == 'Delivered']))
    m3.metric("Prod/Design Done", len(df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'Yes')]))
    
    m4, m5, m6 = st.columns(3)
    m4.metric("Design Pending", len(df[(df['Stage'] != 'Ready') & (df['Designer_finished'] == 'No')]))
    m5.metric("Total Queue", len(df))
    m6.metric("VIP (>3)", len(df[df['Qty_num'] > 3]))

    st.divider()
    st.subheader("💎 VIP Priority Queue")
    vips = df[df['Qty_num'] > 3]
    if not vips.empty:
        st.dataframe(vips[['Order_ID', 'Name', 'Qty', 'Stage']], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("⏳ Active Deadlines")
    def get_status(row):
        if pd.isna(row['Order Time']): return "⚪ No Date", "⚪ No Date"
        p_rem = ((row['Order Time'] + timedelta(days=4)) - now).days
        d_rem = ((row['Order Time'] + timedelta(days=7)) - now).days
        p_f = f"🔴 LATE" if p_rem < 0 else (f"🟡 URGENT" if p_rem <= 1 else f"🟢 {p_rem}d")
        d_f = f"🔴 LATE" if d_rem < 0 else (f"🟡 URGENT" if d_rem <= 1 else f"🟢 {d_rem}d")
        return p_f, d_f

    df['Production Status'], df['Delivery Status'] = zip(*df.apply(get_status, axis=1))
    st.table(df[['Order_ID', 'Name', 'Stage', 'Production Status', 'Delivery Status']].sort_values('Order_ID'))

elif page == "📜 Order Logs":
    st.header("Order Management")
    search = st.text_input("🔍 Search")
    filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
    st.dataframe(filtered.drop(columns=['Qty_num', 'Total_num'], errors='ignore'), use_container_width=True, hide_index=True)
    
    st.divider()
    order_id = st.selectbox("Select Order ID to Edit", ["Select..."] + list(df['Order_ID'].unique()))
    if order_id != "Select...":
        idx = df[df['Order_ID'] == order_id].index[0]
        curr = df.loc[idx]
        with st.form("edit_form"):
            c1, c2, c3 = st.columns(3)
            d_conf = c1.selectbox("Design Confirmed?", ["No", "Yes"], index=1 if curr.get('Design_confirmed') == 'Yes' else 0)
            d_conn = c2.selectbox("Needs Designer?", ["No", "Yes"], index=1 if curr.get('Is_connected_designer') == 'Yes' else 0)
            d_fin = c3.selectbox("Design Finished?", ["No", "Yes"], index=1 if curr.get('Designer_finished') == 'Yes' else 0)
            u_stage = c1.selectbox("Stage", ["Pending", "Printing", "Ready", "Delivered", "Hold"])
            u_paid = c2.selectbox("Paid", ["No", "Yes", "Partial"])
            u_biker = c3.text_input("Biker", value=curr['Biker'])
            
            save_col, del_col = st.columns([5,1])
            if save_col.form_submit_button("💾 Save"):
                df.at[idx, 'Design_confirmed'] = d_conf
                df.at[idx, 'Is_connected_designer'] = d_conn
                df.at[idx, 'Designer_finished'] = d_fin
                df.at[idx, 'Stage'] = u_stage
                df.at[idx, 'Paid'] = u_paid
                df.at[idx, 'Biker'] = u_biker
                conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Production Status', 'Delivery Status'], errors='ignore'))
                st.rerun()
            if del_col.form_submit_button("🗑️ DELETE"):
                df = df.drop(idx)
                conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Production Status', 'Delivery Status'], errors='ignore'))
                st.rerun()

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
                "Order Time": now.strftime("%Y-%m-%d %H:%M"), "Order_ID": n_id if n_id else f"MAN-{now.strftime('%M%S')}",
                "Name": n_name, "Contact": n_phone, "Qty": str(n_qty), "money": str(price), "Paid": "No",
                "Stage": "Pending", "Total": str(price), "Biker": "Unassigned", "Design_confirmed": "No",
                "Is_connected_designer": "Yes" if n_conn else "No", "Designer_finished": "No"
            }])
            conn.update(data=pd.concat([df.drop(columns=['Qty_num','Total_num','Production Status','Delivery Status'], errors='ignore'), new_row]))
            st.rerun()

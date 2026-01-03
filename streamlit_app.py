import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# ... (Keep existing Auth and Connection code) ...

# Data Processing for Debt Calculation
df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
# We count debt for any card that has hit the production phase
produced_df = df[df['Stage'].isin(['Printing', 'Ready', 'Delivered'])]
total_production_cost = produced_df['Qty_num'].sum() * 400

# Calculate Total Paid from Expenses Sheet
if not expenses_df.empty:
    total_paid_to_supplier = pd.to_numeric(expenses_df['Amount'], errors='coerce').sum()
else:
    total_paid_to_supplier = 0

current_debt = total_production_cost - total_paid_to_supplier

# Dashboard Page Logic
if page == "📊 Dashboard":
    st.header("Business Intelligence")
    
    cash_on_hand = df[df['Paid'] == 'Yes']['Total_num'].sum()
    receivables = df[df['Paid'] != 'Yes']['Total_num'].sum()

    f1, f2, f3 = st.columns(3)
    f1.metric("💵 Cash on Hand", f"{cash_on_hand:,} ETB")
    f2.metric("⏳ To be Collected", f"{receivables:,} ETB")
    # This shows your actual debt based on your formula
    f3.metric("🏭 Supplier Debt", f"{current_debt:,} ETB", delta=f"Total Paid: {total_paid_to_supplier:,}")

# Supplier Payouts Page Logic
elif page == "💸 Supplier Payouts":
    st.header("Supplier Payouts")
    
    # Financial Overview for Supplier
    c1, c2 = st.columns(2)
    c1.info(f"**Total Production Cost:** {total_production_cost:,} ETB")
    c2.warning(f"**Outstanding Debt:** {current_debt:,} ETB")
    
    with st.form("exp"):
        amount = st.number_input("Amount (ETB)", min_value=0)
        recp = st.text_input("Recipient (e.g., Supplier Name)")
        note = st.text_area("Note (e.g., Batch Jan 1-5)")
        if st.form_submit_button("Confirm Payout"):
            new_exp = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                "Amount": str(amount), 
                "Recipient": recp, 
                "Note": note
            }])
            conn.update(worksheet="Expenses", data=pd.concat([expenses_df, new_exp], ignore_index=True))
            st.success("Payout Recorded!")
            st.rerun()
            
    st.subheader("Payout History")
    st.dataframe(expenses_df, use_container_width=True, hide_index=True)

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. THE BRAIN: PRICING & LOGIC (From your Bot) ---
def get_unit_price(qty):
    if qty >= 10: return 1000
    if qty >= 5: return 1100
    return 1200

# --- 2. AUTHENTICATION (The Gabe135. Gate) ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else: st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData HQ")
        st.text_input("Admin Password", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    st.set_page_config(page_title="FineData Command", layout="wide")
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0)

    # Convert logic-heavy columns
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
    
    # --- 3. INTELLIGENT ALERTS (Making life easier) ---
    st.title("🦅 Operational Oversight")
    
    # Alert Logic: No contact within 1 hour (as promised in your bot)
    now = datetime.now()
    critical_followup = df[(df['Status'] == 'Pending') & (df['Date'] < (now - timedelta(hours=1)))]
    
    a1, a2, a3 = st.columns(3)
    with a1:
        if not critical_followup.empty:
            st.error(f"⚠️ {len(critical_followup)} MISSING 1HR CONTACT PROMISE")
    with a2:
        payment_due = df[df['Payment'] == 'Unpaid']
        st.warning(f"💸 {len(payment_due)} ORDERS UNPAID")
    with a3:
        # Calculate daily revenue from bot orders
        today_rev = (df[df['Date'].dt.date == now.date()]['Qty'] * 1200).sum()
        st.metric("Today's Revenue", f"{today_rev:,} ETB")

    st.divider()

    # --- 4. THE COMMAND CENTER (Bilingual Tabs) ---
    tab_manage, tab_finance, tab_bot_sync = st.tabs(["🚀 Production", "💰 Financials", "🤖 Bot Sync"])

    with tab_manage:
        st.subheader("Active Pipeline (Amharic & English)")
        # Use Data Editor for easy status flips
        edited_df = st.data_editor(
            df,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Workflow", 
                    options=["Pending", "Design Proof Sent", "Printing", "Ready", "Delivered", "Hold"]
                ),
                "Payment": st.column_config.SelectboxColumn("Cash", options=["Paid", "Unpaid", "Telebirr Pending"]),
                "Biker": st.column_config.TextColumn("Delivery Info"),
            },
            hide_index=True, use_container_width=True
        )
        if st.button("Push Changes to Global Sheet"):
            conn.update(data=edited_df)
            st.balloons()

    with tab_finance:
        st.subheader("Net Profit Forensics")
        # Automatic calculation using your business math (800 ETB profit per card)
        total_cards = df['Qty'].sum()
        net_profit = total_cards * 800
        delivery_costs = len(df) * 200 # Based on your 200 ETB delivery fee logic
        
        f1, f2, f3 = st.columns(3)
        f1.metric("Net Profit", f"{net_profit:,} ETB")
        f2.metric("Delivery Liabilities", f"{delivery_costs:,} ETB")
        f3.metric("Avg Order Size", f"{df['Qty'].mean():.1f} Cards")

    with tab_bot_sync:
        st.info("Copy the Order ID from your Telegram bot and search it here to instantly find designs.")
        search_id = st.text_input("🔍 Search Order ID (e.g., FD-2025...)")
        if search_id:
            result = df[df['Order_ID'] == search_id]
            st.write(result)

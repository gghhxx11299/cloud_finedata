import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Page Configuration
st.set_page_config(page_title="Finedata Manager", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Ethiopia timezone
ET_TIMEZONE = pytz.timezone("Africa/Addis_Ababa")


def now_et():
    return datetime.now(ET_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


# Initialize or fetch data
def initialize_dataframe():
    required_cols = [
        "Name", "Contact", "Qty", "Payment", "Status",
        "Total", "created_at", "status_updated_at", "audit_log"
    ]
    try:
        df = conn.read(ttl=0)
        if df is None or df.empty or not set(required_cols).issubset(df.columns):
            df = pd.DataFrame(columns=required_cols)
    except Exception as e:
        df = pd.DataFrame(columns=required_cols)
    return df


df = initialize_dataframe()

st.title("🛡️ Finedata Production & Order Manager")

# --- 📊 COMMAND CENTER DASHBOARD ---
st.subheader("🚦 Command Center")

# Ensure datetime columns are parsed
df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
df["status_updated_at"] = pd.to_datetime(df["status_updated_at"], errors="coerce")

# Backlog: Pending > 48h (Status == "Verified")
now = datetime.now(ET_TIMEZONE)
pending_48h_mask = (
    (df["Status"] == "Verified") &
    (df["status_updated_at"].notna()) &
    ((now - df["status_updated_at"]) > timedelta(hours=48))
)
backlog_count = pending_48h_mask.sum()

# Daily cards processed (Status in ["Processing", "Quality Check", "Out for Delivery"])
today = now.date()
daily_cards = df[
    (df["status_updated_at"].notna()) &
    (pd.to_datetime(df["status_updated_at"]).dt.date == today) &
    (df["Status"].isin(["Processing", "Quality Check", "Out for Delivery"]))
]["Qty"].sum()

# Cash Flow
cash_in_hand = df[df["Payment"] == "Paid"]["Total"].sum() if "Total" in df.columns else 0
expected_cash = df[df["Payment"] != "Paid"]["Total"].sum() if "Total" in df.columns else 0

# Metrics Row
col1, col2, col3 = st.columns(3)

with col1:
    if backlog_count > 0:
        st.metric("🚨 Backlog (>48h)", backlog_count, delta="Urgent!", delta_color="inverse")
    else:
        st.metric("✅ Backlog (>48h)", 0)

with col2:
    daily_target = 80
    progress = min(daily_cards / daily_target, 1.0)
    st.metric("🎯 Daily Target", f"{daily_cards}/{daily_target}")
    st.progress(progress)

with col3:
    st.metric("💰 Cash in Hand", f"{cash_in_hand:,.0f} ETB")
    st.metric("💸 Expected Cash", f"{expected_cash:,.0f} ETB")

st.divider()

# --- NAVIGATION TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📋 Main View", "🖨️ Printer Mode", "🚴 Biker Dispatch", "🔍 CRM Search"])

# === TAB 1: MAIN VIEW (Order Entry + Full Pipeline) ===
with tab1:
    # Sidebar: Add New Order
    with st.sidebar:
        st.header("➕ Add New Order")
        with st.form("add_form", clear_on_submit=True):
            new_name = st.text_input("Customer Name")
            new_phone = st.text_input("Phone Number")
            new_qty = st.number_input("Quantity", min_value=1, value=1)
            new_pay = st.selectbox("Payment", ["Paid", "Unpaid"])
            # Stage 1 = Verified
            new_status = "Verified"
            
            if st.form_submit_button("✅ Save Order"):
                if new_name.strip() and new_phone.strip():
                    new_row = pd.DataFrame([{
                        "Name": new_name,
                        "Contact": new_phone,
                        "Qty": new_qty,
                        "Payment": new_pay,
                        "Status": new_status,
                        "Total": new_qty * 1200,
                        "created_at": now_et(),
                        "status_updated_at": now_et(),
                        "audit_log": f"Created as '{new_status}' at {now_et()}"
                    }])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    conn.update(data=updated_df)
                    st.success(f"✅ Order for {new_name} saved!")
                    st.rerun()
                else:
                    st.error("⚠️ Name and Phone required.")

    # Full Pipeline View
    st.subheader("📦 Full Order Pipeline")
    if not df.empty:
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Stage",
                    options=["Verified", "Processing", "Quality Check", "Out for Delivery", "Delivered"],
                    required=True,
                ),
                "Payment": st.column_config.SelectboxColumn(
                    "Payment Status",
                    options=["Paid", "Unpaid"],
                    required=True,
                ),
                "Contact": st.column_config.TextColumn("📱 Phone"),
                "Qty": st.column_config.NumberColumn("🔢 Qty", min_value=1),
                "Total": st.column_config.NumberColumn("💰 Total (ETB)", disabled=True),
            },
            key="main_editor"
        )

        # Detect changes in Status or Payment
        if not edited_df.equals(df):
            # Update timestamps and logs only for changed rows
            for idx, row in edited_df.iterrows():
                orig_row = df.iloc[idx] if idx < len(df) else None
                changed = False
                log_entries = []

                if orig_row is not None:
                    if row["Status"] != orig_row["Status"]:
                        log_entries.append(f"Status: '{orig_row['Status']}' → '{row['Status']}' at {now_et()}")
                        edited_df.at[idx, "status_updated_at"] = now_et()
                        changed = True
                    if row["Payment"] != orig_row["Payment"]:
                        log_entries.append(f"Payment: '{orig_row['Payment']}' → '{row['Payment']}' at {now_et()}")
                        changed = True
                else:
                    # New row
                    edited_df.at[idx, "created_at"] = now_et()
                    edited_df.at[idx, "status_updated_at"] = now_et()
                    edited_df.at[idx, "audit_log"] = f"Created as '{row['Status']}' at {now_et()}"
                    changed = True

                if log_entries:
                    old_log = str(orig_row["audit_log"]) if orig_row is not None and pd.notna(orig_row["audit_log"]) else ""
                    edited_df.at[idx, "audit_log"] = (old_log + "; " + "; ".join(log_entries)).strip("; ")

            if changed:
                conn.update(data=edited_df)
                st.success("✅ Cloud updated with audit trail!")
                st.rerun()
    else:
        st.info("📭 No orders yet. Add one from the sidebar!")

# === TAB 2: PRINTER MODE ===
with tab2:
    st.subheader("🖨️ Printer Mode – Today’s Jobs")
    st.caption("Orders in 'Processing' stage only")
    printer_df = df[df["Status"] == "Processing"].copy()
    if not printer_df.empty:
        st.dataframe(
            printer_df[["Name", "Contact", "Qty", "Total"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.success("✅ Nothing to print right now!")

# === TAB 3: BIKER DISPATCH ===
with tab3:
    st.subheader("🚴 Biker Dispatch Board")
    st.caption("Mark as 'Out for Delivery' → appears here automatically")
    delivery_df = df[df["Status"] == "Out for Delivery"].copy()
    if not delivery_df.empty:
        delivery_display = delivery_df[["Name", "Contact", "Qty", "Total"]].reset_index(drop=True)
        st.dataframe(delivery_display, use_container_width=True, hide_index=True)
    else:
        st.info("📭 No deliveries pending.")

# === TAB 4: CRM SEARCH ===
with tab4:
    st.subheader("🔍 Customer Lookup & History")
    search = st.text_input("Enter name or phone number")
    
    if search:
        matches = df[
            df["Name"].str.contains(search, case=False, na=False) |
            df["Contact"].str.contains(search, case=False, na=False)
        ]
        if not matches.empty:
            st.write(f"Found {len(matches)} order(s):")
            for _, row in matches.iterrows():
                st.markdown(f"""
                - **{row['Name']}** ({row['Contact']})  
                  📦 {row['Qty']} cards | 💰 {row['Total']} ETB | {row['Status']} | {row['Payment']}
                """)
            # Repeat customer logic
            unique_customers = matches["Contact"].nunique()
            total_orders = len(matches)
            if total_orders >= 5:
                st.success(f"🌟 Loyal customer! {total_orders} orders – consider a discount!")
            elif total_orders >= 3:
                st.info(f"👍 Returning customer ({total_orders} orders)")
        else:
            st.warning("No customer found.")

# --- MOBILE OPTIMIZATION NOTE ---
st.markdown("""
<style>
    /* Ensure mobile responsiveness */
    @media (max-width: 768px) {
        .stMetric { text-align: center; }
        section[data-testid="stSidebar"] { display: none; }
    }
</style>
""", unsafe_allow_html=True)

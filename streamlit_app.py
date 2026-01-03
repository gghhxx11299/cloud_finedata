import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Page Config
st.set_page_config(page_title="FINEDA HQ", layout="wide", page_icon="📈")

# --- 1. AUTHENTICATION ---
if "password_correct" not in st.session_state:
    st.title("🛡️ FineData HQ Login")
    pwd = st.text_input("Admin Password", type="password")
    if st.button("Access"):
        if pwd == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Access Denied")
    st.stop()

# --- 2. DRIVE UPLOAD HELPER ---
def upload_to_drive(file_obj, filename):
    try:
        # Use the same credentials as GSheets
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build('drive', 'v3', credentials=creds)
        
        # Your specific Folder ID
        folder_id = "1yko-zxABjpZT6kiEEgX0luLktODbxJGJ" 
        
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_obj.getvalue()), mimetype=file_obj.type)
        
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True
    except Exception as e:
        st.error(f"Drive Error: {e}")
        return False

# --- 3. DATA CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0).astype(str)

# Ensure required columns exist
for col in ['Exported', 'Called', 'Stage', 'Paid', 'Biker', 'Total', 'Qty']:
    if col not in df.columns:
        df[col] = "Pending" if col == 'Stage' else "No" if col in ['Exported', 'Called', 'Paid'] else "0"

try:
    expenses_df = conn.read(worksheet="Expenses", ttl=0).astype(str)
except:
    expenses_df = pd.DataFrame(columns=["Date", "Amount", "Recipient", "Note"])

# --- 4. BUSINESS CALCULATIONS ---
df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
df['Order Time DT'] = pd.to_datetime(df['Order Time'], errors='coerce')

# Supplier Math (Debt)
produced_df = df[df['Stage'].isin(['Printing', 'Ready', 'Delivered'])]
total_production_cost = produced_df['Qty_num'].sum() * 400
total_paid_to_supplier = pd.to_numeric(expenses_df['Amount'], errors='coerce').sum() if not expenses_df.empty else 0
current_debt = total_production_cost - total_paid_to_supplier
now = datetime.now()

# --- 5. NAVIGATION ---
page = st.sidebar.radio("Navigation", ["📊 Dashboard", "📜 Order Logs", "🎨 Design Vault", "📤 Supplier Export", "💸 Supplier Payouts", "📝 New Entry"])

# --- PAGE: DASHBOARD ---
if page == "📊 Dashboard":
    st.header("Business Intelligence")
    cash = df[df['Paid'] == 'Yes']['Total_num'].sum()
    receivables = df[df['Paid'] != 'Yes']['Total_num'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("💵 Cash on Hand", f"{cash:,} ETB")
    c2.metric("⏳ To be Collected", f"{receivables:,} ETB")
    c3.metric("🏭 Supplier Debt", f"{current_debt:,} ETB")

# --- PAGE: ORDER LOGS ---
elif page == "📜 Order Logs":
    st.header("Order Management")
    search = st.text_input("🔍 Search Orders")
    filtered = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
    st.dataframe(filtered.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore'), use_container_width=True, hide_index=True)

# --- PAGE: DESIGN VAULT (IMAGE UPLOAD) ---
elif page == "🎨 Design Vault":
    st.header("Design Upload Center")
    target_id = st.selectbox("Select Order ID", ["Select..."] + list(df['Order_ID'].unique()))
    
    if target_id != "Select...":
        st.write(f"Uploading for: **{target_id}**")
        col1, col2 = st.columns(2)
        
        with col1:
            f_img = st.file_uploader("Front Design", type=['jpg','png','jpeg'], key="f")
            if f_img and f_img.size > 10*1024*1024:
                st.error("Front image exceeds 10MB limit")
        
        with col2:
            b_img = st.file_uploader("Back Design", type=['jpg','png','jpeg'], key="b")
            if b_img and b_img.size > 10*1024*1024:
                st.error("Back image exceeds 10MB limit")

        if st.button("🚀 Finalize & Upload to Drive"):
            with st.spinner("Uploading to Google Drive..."):
                if f_img and f_img.size <= 10*1024*1024:
                    upload_to_drive(f_img, f"{target_id}-image-front")
                if b_img and b_img.size <= 10*1024*1024:
                    upload_to_drive(b_img, f"{target_id}-image-back")
                st.success(f"Designs for {target_id} successfully saved to Drive!")

# --- PAGE: SUPPLIER EXPORT ---
elif page == "📤 Supplier Export":
    st.header("CSV Export")
    mask = (df['Exported'] == "No")
    to_export = df[mask].copy()
    if not to_export.empty:
        csv = to_export.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore').to_csv(index=False).encode('utf-8')
        if st.download_button("📥 Download & Mark Exported", data=csv, file_name=f"batch_{now.strftime('%Y%m%d')}.csv"):
            df.loc[mask, 'Exported'] = "Yes"
            conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore'))
            st.rerun()

# --- PAGE: SUPPLIER PAYOUTS ---
elif page == "💸 Supplier Payouts":
    st.header("Supplier Payouts")
    with st.form("payout_form"):
        amt = st.number_input("Amount (ETB)", min_value=0)
        note = st.text_input("Note")
        if st.form_submit_button("Confirm Payout"):
            new_payout = pd.DataFrame([{"Date": now.strftime("%Y-%m-%d"), "Amount": str(amt), "Recipient": "Supplier", "Note": note}])
            conn.update(worksheet="Expenses", data=pd.concat([expenses_df, new_payout], ignore_index=True))
            st.rerun()

# --- PAGE: NEW ENTRY ---
elif page == "📝 New Entry":
    st.header("Manual Entry")
    with st.form("manual_entry"):
        oid = st.text_input("Order_ID")
        name = st.text_input("Customer Name")
        contact = st.text_input("Phone")
        qty = st.number_input("Quantity", min_value=1)
        if st.form_submit_button("Submit Order"):
            new_row = pd.DataFrame([{
                "Order Time": now.strftime("%Y-%m-%d %H:%M"), "Order_ID": oid, "Name": name, 
                "Contact": contact, "Qty": str(qty), "Paid": "No", "Stage": "Pending", 
                "Total": str(qty*1200), "Exported": "No", "Called": "No"
            }])
            conn.update(data=pd.concat([df.drop(columns=['Qty_num','Total_num', 'Order Time DT'], errors='ignore'), new_row], ignore_index=True))
            st.rerun()

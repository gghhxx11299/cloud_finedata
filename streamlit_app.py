import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# Page Configuration
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

# --- 2. DRIVE UPLOAD WITH OWNERSHIP TRANSFER ---
def upload_to_drive(file_obj, filename):
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        admin_email = st.secrets["admin"]["email"]
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build('drive', 'v3', credentials=creds)
        
        folder_id = "1yko-zxABjpZT6kiEEgX0luLktODbxJGJ" 
        
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_obj.getvalue()), mimetype=file_obj.type)
        
        # Upload file
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()
        
        file_id = file.get('id')

        # Transfer ownership to utilize your 2TB quota
        service.permissions().create(
            fileId=file_id,
            body={'type': 'user', 'role': 'owner', 'emailAddress': admin_email},
            transferOwnership=True,
            fields='id'
        ).execute()
        
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Upload Error: {e}")
        return None

# --- 3. DATA CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl=0).astype(str)

# Ensure essential columns exist
for col in ['Exported', 'Called', 'Stage', 'Paid', 'Biker', 'Total', 'Qty', 'Image_front', 'Image_back']:
    if col not in df.columns:
        df[col] = "None" if "Image" in col else "No" if col in ['Exported', 'Called', 'Paid'] else "0"

try:
    expenses_df = conn.read(worksheet="Expenses", ttl=0).astype(str)
except:
    expenses_df = pd.DataFrame(columns=["Date", "Amount", "Recipient", "Note"])

# --- 4. CALCULATIONS ---
df['Qty_num'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
df['Total_num'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0)
df['Order Time DT'] = pd.to_datetime(df['Order Time'], errors='coerce')

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
    
    st.divider()
    order_id = st.selectbox("Select Order to View Designs", ["Select..."] + list(df['Order_ID'].unique()))
    if order_id != "Select...":
        row = df[df['Order_ID'] == order_id].iloc[0]
        v1, v2 = st.columns(2)
        if row['Image_front'] != "None": v1.link_button("👁️ Front Design", row['Image_front'])
        if row['Image_back'] != "None": v2.link_button("👁️ Back Design", row['Image_back'])

# --- PAGE: DESIGN VAULT ---
elif page == "🎨 Design Vault":
    st.header("Design Upload Center (Ownership Transfer Mode)")
    target_id = st.selectbox("Select Order ID", ["Select..."] + list(df['Order_ID'].unique()))
    
    if target_id != "Select...":
        idx = df[df['Order_ID'] == target_id].index[0]
        c1, c2 = st.columns(2)
        f_img = c1.file_uploader("Front Design", type=['jpg','png','jpeg'], key="f")
        b_img = c2.file_uploader("Back Design", type=['jpg','png','jpeg'], key="b")

        if st.button("🚀 Upload & Transfer Ownership"):
            with st.spinner("Processing upload to your personal quota..."):
                updated = False
                if f_img and f_img.size <= 10*1024*1024:
                    link = upload_to_drive(f_img, f"{target_id}-front")
                    if link: df.at[idx, 'Image_front'], updated = link, True
                if b_img and b_img.size <= 10*1024*1024:
                    link = upload_to_drive(b_img, f"{target_id}-back")
                    if link: df.at[idx, 'Image_back'], updated = link, True
                
                if updated:
                    conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore'))
                    st.success("Successfully uploaded to your 2TB storage!")
                    st.rerun()

# --- PAGE: SUPPLIER EXPORT ---
elif page == "📤 Supplier Export":
    st.header("CSV Export")
    mask = (df['Exported'] == "No")
    to_export = df[mask].copy()
    if not to_export.empty:
        csv = to_export.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore').to_csv(index=False).encode('utf-8')
        if st.download_button("📥 Download & Mark", data=csv, file_name=f"batch_{now.strftime('%Y%m%d')}.csv"):
            df.loc[mask, 'Exported'] = "Yes"
            conn.update(data=df.drop(columns=['Qty_num', 'Total_num', 'Order Time DT'], errors='ignore'))
            st.rerun()

# --- PAGE: SUPPLIER PAYOUTS ---
elif page == "💸 Supplier Payouts":
    st.header("Payouts")
    with st.form("p"):
        amt = st.number_input("Amount", min_value=0)
        if st.form_submit_button("Confirm"):
            new = pd.DataFrame([{"Date": now.strftime("%Y-%m-%d"), "Amount": str(amt), "Recipient": "Supplier", "Note": "Payout"}])
            conn.update(worksheet="Expenses", data=pd.concat([expenses_df, new], ignore_index=True))
            st.rerun()

# --- PAGE: NEW ENTRY ---
elif page == "📝 New Entry":
    st.header("Manual Entry")
    with st.form("n"):
        oid = st.text_input("Order_ID")
        name = st.text_input("Name")
        if st.form_submit_button("Submit"):
            new = pd.DataFrame([{
                "Order Time": now.strftime("%Y-%m-%d %H:%M"), "Order_ID": oid, "Name": name, 
                "Qty": "1", "Paid": "No", "Stage": "Pending", "Total": "1200", 
                "Exported": "No", "Called": "No", "Image_front": "None", "Image_back": "None"
            }])
            conn.update(data=pd.concat([df.drop(columns=['Qty_num','Total_num', 'Order Time DT'], errors='ignore'), new], ignore_index=True))
            st.rerun()

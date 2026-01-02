import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta

# --- 1. SETTINGS & AUTH ---
st.set_page_config(page_title="FINEDA HQ", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛡️ FineData Secure Gate")
        pwd = st.text_input("Admin Password", type="password")
        if st.button("Unlock"):
            if pwd == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else: st.error("Wrong Password")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl=0).astype(str) # Force string to avoid type errors
    
    # --- 2. THE DASHBOARD ---
    st.title("🦅 Finedata Command Center")
    
    # Net Profit Logic
    qty_sum = pd.to_numeric(df['Qty'], errors='coerce').sum()
    st.metric("Total Net Profit (800/unit)", f"{(qty_sum * 800):,.0f} ETB")
    st.divider()

    # --- 3. THE OPERATIONS HUB ---
    tab1, tab2 = st.tabs(["🏗️ Production & Workflow", "📝 Manual Order Entry"])

    with tab1:
        col_list, col_edit = st.columns([2, 1]) # 2/3 for table, 1/3 for edit form

        with col_list:
            st.subheader("Current Orders")
            search = st.text_input("🔍 Search Name/ID/Phone")
            display_df = df[df.apply(lambda r: search.lower() in str(r).lower(), axis=1)] if search else df
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        with col_edit:
            st.subheader("⚙️ Quick Edit Row")
            # Select which order to edit
            order_to_edit = st.selectbox("Select Order ID to Update", options=df['Order_ID'].unique())
            
            if order_to_edit:
                # Get current data for that row
                row_data = df[df['Order_ID'] == order_to_edit].iloc[0]
                
                with st.form("edit_form"):
                    new_stage = st.selectbox("Update Stage", 
                                           options=["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"],
                                           index=["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"].index(row_data['Stage']) if row_data['Stage'] in ["Pending", "Design Proof", "Printing", "Ready", "Delivered", "Hold"] else 0)
                    
                    new_paid = st.selectbox("Update Paid", 
                                          options=["No", "Yes", "Partial"],
                                          index=["No", "Yes", "Partial"].index(row_data['Paid']) if row_data['Paid'] in ["No", "Yes", "Partial"] else 0)
                    
                    new_biker = st.text_input("Assign Biker", value=row_data['Biker'])
                    new_qty = st.number_input("Update Qty", value=int(pd.to_numeric(row_data['Qty'], errors='coerce') or 1))
                    
                    if st.form_submit_button("Save Changes"):
                        # Find the index and update
                        idx = df[df['Order_ID'] == order_to_edit].index[0]
                        df.at[idx, 'Stage'] = new_stage
                        df.at[idx, 'Paid'] = new_paid
                        df.at[idx, 'Biker'] = new_biker
                        df.at[idx, 'Qty'] = str(new_qty)
                        df.at[idx, 'money'] = str(new_qty * 1200)
                        df.at[idx, 'Total'] = str(new_qty * 1200)
                        
                        conn.update(data=df)
                        st.success(f"Order {order_to_edit} Updated!")
                        st.rerun()

    with tab2:
        with st.form("manual_order", clear_on_submit=True):
            st.subheader("Manual Registration")
            c1, c2 = st.columns(2)
            m_id = c1.text_input("Order_ID")
            name = c2.text_input("Customer Name")
            phone = c1.text_input("Contact")
            qty = c2.number_input("Quantity", min_value=1, value=1)
            
            if st.form_submit_button("Register Order"):
                new_id = m_id if m_id else f"MAN-{datetime.now().strftime('%M%S')}"
                price = qty * 1200
                new_row = pd.DataFrame([{
                    "Order Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Order_ID": new_id, "Name": name, "Contact": phone, "Qty": str(qty),
                    "money": str(price), "Paid": "No", "Stage": "Pending", "Total": str(price), "Biker": "Unassigned"
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                conn.update(data=df)
                st.success("Added!")
                st.rerun()

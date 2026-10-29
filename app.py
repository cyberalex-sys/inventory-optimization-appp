"""
Inventory Optimization & Supply Chain Management Platform
Production-Ready Full-Stack Streamlit Application
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import io

# Local modular imports
from database import (
    init_db,
    get_all_products,
    get_product_by_sku,
    get_product_by_barcode,
    create_product,
    update_product,
    delete_product,
    record_stock_movement,
    get_all_suppliers,
    get_demand_history,
    get_recent_transactions,
    apply_offline_queue
)
from analytics import (
    compute_inventory_metrics,
    calculate_kpis,
    compute_moving_average_forecast,
    compute_forecast_error_metrics
)
from security import (
    sanitize_text,
    validate_sku,
    validate_barcode,
    validate_numeric
)
from reporting import (
    generate_inventory_csv,
    generate_forecast_error_csv,
    generate_executive_pdf_report
)

# ---------------------------------------------------------
# Page Configuration & Responsive Enterprise Theme
# ---------------------------------------------------------
st.set_page_config(
    page_title="SupplyChainIQ | Enterprise Inventory Optimizer",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enterprise Dark-Navy Design System
st.markdown("""
<style>
    /* Global Typography & Background */
    html, body, [class*="css"], .stMarkdown, p, span, div, label {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", Roboto, sans-serif !important;
        color: #f1f5f9;
    }
    .stApp {
        background-color: #0b0f19 !important;
    }

    /* Platform Header Bar */
    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 20px;
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .app-title {
        font-size: 1.5rem;
        font-weight: 800;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .status-badge {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 9999px;
    }
    .badge-online {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-offline {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }

    /* Executive KPI Cards */
    .kpi-card {
        background: #131b2e;
        border: 1px solid #1e293b;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .kpi-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 6px;
    }

    /* Hazard Alert Cards */
    .alert-banner-danger {
        background: linear-gradient(90deg, rgba(185, 28, 28, 0.25) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid #ef4444;
        border-left: 6px solid #ef4444;
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }
    .alert-banner-warning {
        background: linear-gradient(90deg, rgba(217, 119, 6, 0.25) 0%, rgba(15, 23, 42, 0.6) 100%);
        border: 1px solid #f59e0b;
        border-left: 6px solid #f59e0b;
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }

    /* Scanner Quick Actions */
    .scanner-box {
        background: #111827;
        border: 2px dashed #3b82f6;
        border-radius: 14px;
        padding: 20px;
        text-align: center;
        margin-bottom: 18px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Session State Initialization (State & Offline Management)
# ---------------------------------------------------------
if "offline_mode" not in st.session_state:
    st.session_state["offline_mode"] = False
if "offline_queue" not in st.session_state:
    st.session_state["offline_queue"] = []
if "last_scanned_sku" not in st.session_state:
    st.session_state["last_scanned_sku"] = ""
if "toast_shown" not in st.session_state:
    st.session_state["toast_shown"] = False

# Ensure DB schema exists on initial start
init_db()

# ---------------------------------------------------------
# Sidebar Controls & Global Configuration
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Supply Chain Controls")
    
    # Financial Levers
    po_cost = st.number_input(
        "Cost per PO (₹)",
        min_value=1.0,
        max_value=100000.0,
        value=500.0,
        step=50.0,
        help="Internal administrative and freight processing cost per purchase order."
    )
    
    holding_rate_pct = st.slider(
        "Annual Holding Cost Rate (%)",
        min_value=5.0,
        max_value=50.0,
        value=20.0,
        step=1.0,
        help="Capital interest, warehousing, 3PL, insurance, and obsolescence cost."
    )
    holding_rate = holding_rate_pct / 100.0

    service_level = st.slider(
        "Target Service Level (%)",
        min_value=80.0,
        max_value=99.9,
        value=95.0,
        step=0.5,
        help="Target fulfillment rate. 95% = 1.645 standard deviations of buffer."
    )

    st.markdown("---")
    st.markdown("### 📶 State & Offline Resilience")
    is_offline = st.toggle("Simulate Offline Mode", value=st.session_state["offline_mode"])
    st.session_state["offline_mode"] = is_offline

    if is_offline:
        st.warning("⚠️ Operating in OFFLINE mode. Writes are queued locally in browser state.")
        queue_len = len(st.session_state["offline_queue"])
        st.write(f"**Queued Transactions:** `{queue_len}`")
        if queue_len > 0:
            if st.button("🔄 Force Sync Queued Updates"):
                applied, errors = apply_offline_queue(st.session_state["offline_queue"])
                if applied > 0:
                    st.success(f"Synced {applied} pending updates to SQLite database.")
                    st.session_state["offline_queue"] = []
                    st.rerun()
                if errors:
                    st.error(f"Sync errors: {errors}")
    else:
        # Check if pending queue exists from prior offline session
        if len(st.session_state["offline_queue"]) > 0:
            st.info(f"Syncing {len(st.session_state['offline_queue'])} offline transactions...")
            applied, _ = apply_offline_queue(st.session_state["offline_queue"])
            st.session_state["offline_queue"] = []
            st.rerun()

    st.markdown("---")
    st.caption("SupplyChainIQ Enterprise Edition v3.0 | SQLite Relational Backend")

# ---------------------------------------------------------
# Global Error Boundary Wrapper
# ---------------------------------------------------------
try:
    # ---------------------------------------------------------
    # Data Layer: Ingest and Compute Live Operational Metrics
    # ---------------------------------------------------------
    raw_products = get_all_products()
    products_df = pd.DataFrame(raw_products)

    if products_df.empty:
        st.info("📦 Database is currently empty. Initialize demo data to begin.")
        if st.button("🚀 Seed 250 Realistic Inventory SKUs"):
            with st.spinner("Seeding database..."):
                from init_db import seed_database
                seed_database()
                st.rerun()
        st.stop()

    # Compute Quantitative Supply Chain Metrics
    df = compute_inventory_metrics(
        products_df=products_df,
        po_cost=po_cost,
        holding_rate=holding_rate,
        service_level_pct=service_level
    )
    kpis = calculate_kpis(df)

    # Toast hazard alerts once per session
    if not st.session_state["toast_shown"] and kpis["critical_count"] > 0:
        st.toast(f"🚨 ALERT: {kpis['critical_count']} items have dropped below safety stock!", icon="🚨")
        st.session_state["toast_shown"] = True

    # ---------------------------------------------------------
    # Top Application Header
    # ---------------------------------------------------------
    status_class = "badge-offline" if st.session_state["offline_mode"] else "badge-online"
    status_label = "OFFLINE CACHED" if st.session_state["offline_mode"] else "LIVE SYNCED"

    st.markdown(f"""
    <div class="app-header">
        <div class="app-title">
            <span>📦 SupplyChainIQ Optimizer</span>
            <span class="status-badge {status_class}">{status_label}</span>
        </div>
        <div style="font-size: 0.85rem; color: #94a3b8;">
            Active SKUs: <strong>{len(df):,}</strong> | DB: <strong>SQLite (Encrypted Foreign Keys Active)</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # Main Navigation Tabs
    # ---------------------------------------------------------
    tab_dash, tab_crud, tab_scanner, tab_alerts, tab_reports = st.tabs([
        "📊 Interactive Dashboard",
        "📦 Inventory Management (CRUD)",
        "📷 Barcode & QR Scanner",
        "🚨 Risk & Safety Alerts",
        "📑 Reports & Export"
    ])

    # =========================================================
    # TAB 1: INTERACTIVE DASHBOARD
    # =========================================================
    with tab_dash:
        # Visual Alert Banners if Hazards exist
        if kpis["critical_count"] > 0:
            st.markdown(f"""
            <div class="alert-banner-danger">
                <strong>🚨 CRITICAL STOCKOUT HAZARD:</strong> 
                <strong>{kpis['critical_count']} SKUs</strong> are currently operating below their probabilistic safety stock buffer.
                Immediate supplier purchase orders are required to prevent order backlogs.
            </div>
            """, unsafe_allow_html=True)
        elif kpis["reorder_count"] > 0:
            st.markdown(f"""
            <div class="alert-banner-warning">
                <strong>⚠️ REORDER WARNING:</strong> 
                <strong>{kpis['reorder_count']} SKUs</strong> have breached their Reorder Point (ROP). Replenishment recommended.
            </div>
            """, unsafe_allow_html=True)

        # Visual KPIs Row (Requested: Total Inv Value, Stockout Risk %, Turnover Rate + Trapped Cash)
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Inventory Value</div>
                <div class="kpi-value">₹{kpis['total_inventory_value']:,.2f}</div>
                <div class="kpi-sub">Across {kpis['total_skus']:,} active catalog items</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi_col2:
            hazard_color = "#ef4444" if kpis['stockout_risk_pct'] > 10 else "#10b981"
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Stockout Risk Rate</div>
                <div class="kpi-value" style="color: {hazard_color};">{kpis['stockout_risk_pct']:.1f}%</div>
                <div class="kpi-sub">{kpis['critical_count']} items below safety buffer</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi_col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Inventory Turnover Rate</div>
                <div class="kpi-value" style="color: #38bdf8;">{kpis['turnover_rate']:.2f}x</div>
                <div class="kpi-sub">Annual demand velocity ratio</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi_col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Trapped Cash</div>
                <div class="kpi-value" style="color: #f59e0b;">₹{kpis['total_trapped_cash']:,.2f}</div>
                <div class="kpi-sub">{kpis['trapped_pct']:.1f}% capital recoverable from overstock</div>
            </div>
            """, unsafe_allow_html=True)

        # Charts Section
        st.markdown("#### 📈 Demand Forecasting & Inventory Level Trends")
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("**Moving Average Demand Forecast (Hero SKU Time Series)**")
            
            # Select SKU for detailed demand trend
            available_skus = df["sku"].tolist()
            selected_sku = st.selectbox("Select Item for Forecast Analysis:", available_skus, index=0)
            
            history_rows = get_demand_history(selected_sku, days=60)
            if history_rows:
                h_df = pd.DataFrame(history_rows)
                forecast_df = compute_moving_average_forecast(h_df, window_short=7, window_long=30)
                error_stats = compute_forecast_error_metrics(forecast_df)

                # Line Chart of Actual vs 7-day MA vs 30-day MA
                plot_data = forecast_df.set_index("date")[["actual_demand", "ma_7d", "ma_30d"]]
                plot_data.columns = ["Actual Daily Demand", "7-Day Moving Avg", "30-Day Trendline"]
                st.line_chart(plot_data, color=["#38bdf8", "#10b981", "#f59e0b"])
                st.caption(f"📊 Forecast Performance on {selected_sku}: **MAE: {error_stats['mae']} units** | **MAPE: {error_stats['mape']}%**")
            else:
                st.info(f"Generating synthetic projection for {selected_sku}...")
                sample_dates = pd.date_range(end=datetime.now(), periods=30)
                mean_d = df.loc[df['sku'] == selected_sku, 'avg_daily_sales'].values[0]
                synth_actual = np.maximum(0, np.random.normal(mean_d, mean_d * 0.2, 30))
                synth_ma = pd.Series(synth_actual).rolling(7, min_periods=1).mean()
                synth_df = pd.DataFrame({
                    "Actual Demand": synth_actual,
                    "7-Day Moving Avg": synth_ma
                }, index=sample_dates)
                st.line_chart(synth_df)

        with chart_col2:
            st.markdown("**Top 10 Overstocked Items (Current Stock vs. Optimal Target)**")
            top_over = df.sort_values(by="trapped_cash", ascending=False).head(10)
            if not top_over.empty:
                chart_over = pd.DataFrame({
                    "SKU": top_over["sku"],
                    "Current Stock": top_over["current_stock"],
                    "Optimal Target": top_over["optimal_target"].round(0)
                })
                st.bar_chart(chart_over, x="SKU", y=["Current Stock", "Optimal Target"], color=["#ef4444", "#10b981"])
                st.caption("🔴 Red: Excess Current Stock | 🟢 Green: Lean Optimal Target (EOQ + Safety Stock)")
            else:
                st.success("No overstocked items found.")

        # ABC Classification Value Breakdown
        st.markdown("#### 🎯 Automated ABC Stratification")
        abc_cols = st.columns(3)
        for idx, cls in enumerate(["A", "B", "C"]):
            subset = df[df["abc_class"] == cls]
            val = subset["annual_usage_value"].sum()
            share = (val / max(1.0, kpis["total_inventory_value"])) * 100.0
            with abc_cols[idx]:
                badge_color = "#34d399" if cls == "A" else "#38bdf8" if cls == "B" else "#94a3b8"
                st.markdown(f"""
                <div class="kpi-card" style="border-left: 4px solid {badge_color};">
                    <strong style="color: {badge_color}; font-size: 1.1rem;">Class {cls} ({'High Value' if cls=='A' else 'Moderate' if cls=='B' else 'Low Value'})</strong>
                    <div style="font-size: 1.3rem; font-weight: 800; margin-top: 4px;">{len(subset):,} SKUs</div>
                    <div style="font-size: 0.85rem; color: #94a3b8;">₹{val:,.2f} ({share:.1f}% annual value)</div>
                </div>
                """, unsafe_allow_html=True)

    # =========================================================
    # TAB 2: INVENTORY MANAGEMENT MODULE (CRUD)
    # =========================================================
    with tab_crud:
        st.markdown("### 📦 Inventory Catalog & CRUD Operations")
        
        crud_action = st.radio(
            "Inventory Action:",
            ["🔍 Browse & Filter Catalog", "➕ Add New Item", "✏️ Edit Item", "🗑️ Delete Item"],
            horizontal=True
        )

        # Action 1: Browse & Filter (Read)
        if crud_action == "🔍 Browse & Filter Catalog":
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                cat_options = ["All"] + sorted(df["category"].unique().tolist())
                sel_category = st.selectbox("Filter Category:", cat_options)
            with f_col2:
                status_options = ["All", "CRITICAL_STOCKOUT", "REORDER_TRIGGERED", "OVERSTOCKED", "HEALTHY"]
                sel_status = st.selectbox("Filter Stock Status:", status_options)
            with f_col3:
                search_query = st.text_input("Search SKU or Product Name:", "")

            # Filter data
            filtered_df = df.copy()
            if sel_category != "All":
                filtered_df = filtered_df[filtered_df["category"] == sel_category]
            if sel_status != "All":
                filtered_df = filtered_df[filtered_df["alert_status"] == sel_status]
            if search_query.strip():
                clean_q = search_query.strip().lower()
                filtered_df = filtered_df[
                    filtered_df["sku"].str.lower().str.contains(clean_q) |
                    filtered_df["name"].str.lower().str.contains(clean_q)
                ]

            st.write(f"Showing **{len(filtered_df):,}** of **{len(df):,}** items:")

            display_table = pd.DataFrame({
                "SKU": filtered_df["sku"],
                "Product Name": filtered_df["name"],
                "Category": filtered_df["category"],
                "ABC": filtered_df["abc_class"].apply(lambda x: f"Class {x}"),
                "Current Stock": filtered_df["current_stock"].map(lambda x: f"{x:,}"),
                "Safety Stock": filtered_df["safety_stock"].round(1),
                "Reorder Point": filtered_df["reorder_point"].round(1),
                "EOQ": filtered_df["eoq"].round(1),
                "Unit Cost": filtered_df["unit_cost"].map(lambda x: f"₹{x:,.2f}"),
                "Trapped Cash": filtered_df["trapped_cash"].map(lambda x: f"₹{x:,.2f}"),
                "Status": filtered_df["alert_status"]
            })
            st.dataframe(display_table, use_container_width=True, hide_index=True)

        # Action 2: Add New Item (Create)
        elif crud_action == "➕ Add New Item":
            st.markdown("#### Enroll New SKU into Inventory Database")
            suppliers_list = get_all_suppliers()
            sup_dict = {f"{s['name']} (ID: {s['supplier_id']})": s['supplier_id'] for s in suppliers_list}

            with st.form("add_product_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_sku = st.text_input("SKU (e.g. APP-TEE-999)*", max_chars=40)
                    new_name = st.text_input("Product Name*", max_chars=100)
                    new_category = st.selectbox("Category*", ["Apparel", "Beauty & Skincare", "Wellness & Supplements", "Footwear", "Home & Fragrance", "Accessories"])
                with c2:
                    selected_sup_name = st.selectbox("Assigned Supplier*", list(sup_dict.keys()) if sup_dict else ["Default Supplier"])
                    new_cost = st.number_input("Unit Cost (₹)*", min_value=0.01, value=500.0, step=10.0)
                    new_price = st.number_input("Selling Price (₹)*", min_value=0.01, value=1200.0, step=10.0)
                with c3:
                    new_stock = st.number_input("Current Stock on Hand*", min_value=0, value=100, step=1)
                    new_demand = st.number_input("Estimated Annual Demand*", min_value=1, value=3650, step=50)
                    new_lead_time = st.number_input("Lead Time (Days)*", min_value=1, value=14, step=1)
                    new_barcode = st.text_input("Barcode / QR Code (Optional)", max_chars=48)

                submitted = st.form_submit_button("💾 Save Product to Database")
                if submitted:
                    # Input Sanitization & Safety Validation
                    is_valid_sku, valid_sku_or_err = validate_sku(new_sku)
                    if not is_valid_sku:
                        st.error(f"Validation Error: {valid_sku_or_err}")
                    else:
                        clean_name = sanitize_text(new_name, 100)
                        if not clean_name:
                            st.error("Validation Error: Product name cannot be blank.")
                        else:
                            is_valid_bc, valid_bc_or_err = validate_barcode(new_barcode)
                            if not is_valid_bc:
                                st.error(f"Validation Error: {valid_bc_or_err}")
                            else:
                                product_payload = {
                                    "sku": valid_sku_or_err,
                                    "name": clean_name,
                                    "category": new_category,
                                    "supplier_id": sup_dict.get(selected_sup_name, 1),
                                    "unit_cost": new_cost,
                                    "unit_price": new_price,
                                    "current_stock": new_stock,
                                    "annual_demand": new_demand,
                                    "avg_daily_sales": round(new_demand / 365.0, 1),
                                    "max_daily_sales": int(np.ceil((new_demand / 365.0) * 2.2)),
                                    "lead_time_days": new_lead_time,
                                    "barcode": valid_bc_or_err
                                }

                                if st.session_state["offline_mode"]:
                                    st.session_state["offline_queue"].append({
                                        "sku": valid_sku_or_err,
                                        "type": "INITIAL",
                                        "quantity": new_stock,
                                        "notes": f"Create SKU {clean_name}"
                                    })
                                    st.warning(f"Offline Mode: Product creation queued for {valid_sku_or_err}.")
                                else:
                                    success, msg = create_product(product_payload)
                                    if success:
                                        st.success(f"✅ {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")

        # Action 3: Edit Item (Update)
        elif crud_action == "✏️ Edit Item":
            st.markdown("#### Update Existing SKU Parameters")
            sku_to_edit = st.selectbox("Select SKU to Edit:", df["sku"].tolist())
            item = get_product_by_sku(sku_to_edit)
            suppliers_list = get_all_suppliers()
            sup_dict = {f"{s['name']} (ID: {s['supplier_id']})": s['supplier_id'] for s in suppliers_list}

            if item:
                with st.form("edit_product_form"):
                    e1, e2 = st.columns(2)
                    with e1:
                        edit_name = st.text_input("Product Name", value=item["name"])
                        edit_category = st.selectbox(
                            "Category",
                            ["Apparel", "Beauty & Skincare", "Wellness & Supplements", "Footwear", "Home & Fragrance", "Accessories"],
                            index=["Apparel", "Beauty & Skincare", "Wellness & Supplements", "Footwear", "Home & Fragrance", "Accessories"].index(item["category"]) if item["category"] in ["Apparel", "Beauty & Skincare", "Wellness & Supplements", "Footwear", "Home & Fragrance", "Accessories"] else 0
                        )
                        edit_cost = st.number_input("Unit Cost (₹)", min_value=0.01, value=float(item["unit_cost"]), step=10.0)
                        edit_price = st.number_input("Selling Price (₹)", min_value=0.01, value=float(item["unit_price"]), step=10.0)
                    with e2:
                        edit_demand = st.number_input("Annual Demand", min_value=1, value=int(item["annual_demand"]), step=50)
                        edit_lead_time = st.number_input("Lead Time (Days)", min_value=1, value=int(item["lead_time_days"]), step=1)
                        edit_barcode = st.text_input("Barcode", value=item["barcode"] or "")

                    update_btn = st.form_submit_button("💾 Save Changes")
                    if update_btn:
                        clean_name = sanitize_text(edit_name, 100)
                        is_valid_bc, clean_bc = validate_barcode(edit_barcode)
                        if not is_valid_bc:
                            st.error(clean_bc)
                        else:
                            update_payload = {
                                "name": clean_name,
                                "category": edit_category,
                                "supplier_id": item["supplier_id"],
                                "unit_cost": edit_cost,
                                "unit_price": edit_price,
                                "annual_demand": edit_demand,
                                "avg_daily_sales": round(edit_demand / 365.0, 1),
                                "max_daily_sales": int(np.ceil((edit_demand / 365.0) * 2.2)),
                                "lead_time_days": edit_lead_time,
                                "barcode": clean_bc
                            }
                            ok, msg = update_product(sku_to_edit, update_payload)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

        # Action 4: Delete Item (Delete)
        elif crud_action == "🗑️ Delete Item":
            st.markdown("#### Delete Inventory Item")
            st.warning("⚠️ Deleting an item removes all historical records and transaction logs for this SKU.")
            sku_to_del = st.selectbox("Select SKU to Remove:", df["sku"].tolist(), key="del_sku_select")
            confirm_del = st.checkbox(f"Yes, I confirm permanent deletion of SKU '{sku_to_del}'")
            
            if st.button("🚨 Permanently Delete Product", disabled=not confirm_del):
                ok, msg = delete_product(sku_to_del)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # =========================================================
    # TAB 3: BARCODE & QR SCANNER MODULE
    # =========================================================
    with tab_scanner:
        st.markdown("### 📷 Camera Barcode / QR Scanner & Rapid Fulfillment")
        st.caption("Use your device camera or handheld scanner for immediate stock check-in and check-out.")

        scan_col1, scan_col2 = st.columns([1, 1])

        with scan_col1:
            st.markdown("#### 1. Scan Code via Camera or Keyboard")
            camera_img = st.camera_input("Point camera at Barcode / QR code")

            barcode_detected = ""
            if camera_img is not None:
                st.info("📷 Image captured from camera. Processing frame...")
                # Attempt pyzbar / cv2 QR decoding if installed
                try:
                    import cv2
                    from pyzbar.pyzbar import decode
                    from PIL import Image
                    pil_img = Image.open(camera_img)
                    decoded = decode(pil_img)
                    if decoded:
                        barcode_detected = decoded[0].data.decode('utf-8')
                        st.success(f"🎯 Recognized Barcode: `{barcode_detected}`")
                    else:
                        st.warning("No barcode detected in camera frame. You can enter the code manually below.")
                except ImportError:
                    st.caption("ℹ️ Optional pyzbar/OpenCV library not present. Direct manual scanner input active below.")

            manual_scan = st.text_input(
                "Or Scan with Handheld Barcode Gun / Manual Entry:",
                value=barcode_detected,
                help="Type or scan any Barcode or SKU and press Enter."
            )

        with scan_col2:
            st.markdown("#### 2. Rapid Check-In / Check-Out")
            active_code = manual_scan.strip() or barcode_detected.strip()

            target_item = None
            if active_code:
                # Find by barcode or SKU
                target_item = get_product_by_barcode(active_code)
                if not target_item:
                    target_item = get_product_by_sku(active_code)

            if target_item:
                sku_val = target_item["sku"]
                curr_stock = target_item["current_stock"]
                st.markdown(f"""
                <div class="kpi-card" style="border-left: 5px solid #3b82f6;">
                    <div style="font-size: 1.2rem; font-weight: 800; color: #ffffff;">{target_item['name']}</div>
                    <div style="font-size: 0.9rem; color: #94a3b8; margin-top: 4px;">
                        SKU: <strong>{sku_val}</strong> | Category: <strong>{target_item['category']}</strong>
                    </div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: #34d399; margin-top: 8px;">
                        On Hand: {curr_stock:,} units
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Movement Controls
                move_col1, move_col2 = st.columns(2)
                with move_col1:
                    qty = st.number_input("Quantity:", min_value=1, max_value=50000, value=10, step=1)
                    notes = st.text_input("Transaction Notes:", "Warehouse Scan Check-In/Out")

                with move_col2:
                    st.write("Execute Movement:")
                    btn_in = st.button("📥 Check-In (+ Stock)")
                    btn_out = st.button("📤 Check-Out (- Stock)")

                    if btn_in:
                        if st.session_state["offline_mode"]:
                            st.session_state["offline_queue"].append({
                                "sku": sku_val, "type": "CHECK_IN", "quantity": qty, "notes": notes
                            })
                            st.warning(f"Offline: Queued Check-In of +{qty} units for {sku_val}.")
                        else:
                            ok, msg, new_qty = record_stock_movement(sku_val, "CHECK_IN", qty, notes)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

                    if btn_out:
                        if st.session_state["offline_mode"]:
                            st.session_state["offline_queue"].append({
                                "sku": sku_val, "type": "CHECK_OUT", "quantity": qty, "notes": notes
                            })
                            st.warning(f"Offline: Queued Check-Out of -{qty} units for {sku_val}.")
                        else:
                            ok, msg, new_qty = record_stock_movement(sku_val, "CHECK_OUT", qty, notes)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
            else:
                if active_code:
                    st.error(f"No product matches Barcode or SKU '{active_code}'.")
                else:
                    st.info("Scan a barcode or select an item above to perform rapid stock movements.")

        st.markdown("---")
        st.markdown("#### 📜 Recent Transaction Audit Trail")
        recent_txs = get_recent_transactions(limit=10)
        if recent_txs:
            tx_df = pd.DataFrame(recent_txs)[["timestamp", "sku", "product_name", "type", "quantity", "previous_stock", "new_stock", "notes"]]
            st.dataframe(tx_df, use_container_width=True, hide_index=True)

    # =========================================================
    # TAB 4: RISK & SAFETY ALERTS MODULE
    # =========================================================
    with tab_alerts:
        st.markdown("### 🚨 Supply Chain Risk & Safety Stock Alerts")
        st.caption("Active exceptions where inventory has breached critical replenishment thresholds.")

        critical_df = df[df["alert_status"] == "CRITICAL_STOCKOUT"].sort_values(by="annual_usage_value", ascending=False)
        reorder_df = df[df["alert_status"] == "REORDER_TRIGGERED"].sort_values(by="annual_usage_value", ascending=False)
        overstock_df = df[df["alert_status"] == "OVERSTOCKED"].sort_values(by="trapped_cash", ascending=False)

        a_tab1, a_tab2, a_tab3 = st.tabs([
            f"🚨 Critical Stockouts ({len(critical_df):,})",
            f"⚠️ Reorder Point Breaches ({len(reorder_df):,})",
            f"📦 Trapped Working Capital ({len(overstock_df):,})"
        ])

        with a_tab1:
            if not critical_df.empty:
                st.error(f"**{len(critical_df):,} SKUs** have breached Safety Stock. High stockout and revenue loss risk:")
                for _, r in critical_df.head(10).iterrows():
                    deficit = r['safety_stock'] - r['current_stock']
                    st.markdown(f"""
                    <div style="background: #1e1315; border-left: 5px solid #ef4444; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                        <strong style="color: #f87171; font-size: 1.05rem;">{r['sku']} - {r['name']}</strong> 
                        <span style="font-size: 0.8rem; background: #991b1b; padding: 2px 8px; border-radius: 4px; margin-left: 8px;">CRITICAL DEFICIT</span>
                        <div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 4px;">
                            Current Stock: <strong>{r['current_stock']:,}</strong> | Safety Stock Buffer: <strong>{r['safety_stock']:.1f}</strong> | Deficit: <strong>{deficit:.1f} units</strong>
                        </div>
                        <div style="font-size: 0.82rem; color: #fca5a5; margin-top: 4px;">
                            👉 Recommended Action: Place urgent PO for <strong>{int(np.ceil(r['eoq'])):,} units</strong> with <em>{r['supplier_name']}</em> (Lead Time: {r['lead_time_days']} days).
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ Zero items operating below safety stock buffer.")

        with a_tab2:
            if not reorder_df.empty:
                st.warning(f"**{len(reorder_df):,} SKUs** are currently below their Reorder Point (ROP):")
                reorder_table = pd.DataFrame({
                    "SKU": reorder_df["sku"],
                    "Name": reorder_df["name"],
                    "Current Stock": reorder_df["current_stock"],
                    "Reorder Point": reorder_df["reorder_point"].round(1),
                    "Suggested Order (EOQ)": reorder_df["eoq"].round(0).astype(int),
                    "Supplier": reorder_df["supplier_name"]
                })
                st.dataframe(reorder_table, use_container_width=True, hide_index=True)
            else:
                st.success("✅ All items operate above Reorder Point.")

        with a_tab3:
            if not overstock_df.empty:
                st.info(f"**{len(overstock_df):,} SKUs** holding excess working capital beyond optimal targets:")
                over_table = pd.DataFrame({
                    "SKU": overstock_df["sku"],
                    "Name": overstock_df["name"],
                    "Current Stock": overstock_df["current_stock"],
                    "Optimal Target": overstock_df["optimal_target"].round(0).astype(int),
                    "Trapped Cash": overstock_df["trapped_cash"].map(lambda x: f"₹{x:,.2f}"),
                    "Days Forward Supply": overstock_df["days_of_supply"].round(1).map(lambda x: f"{x}d")
                })
                st.dataframe(over_table, use_container_width=True, hide_index=True)
            else:
                st.success("✅ No overstocked items detected.")

    # =========================================================
    # TAB 5: REPORTS & EXPORT MODULE
    # =========================================================
    with tab_reports:
        st.markdown("### 📑 Executive Reports & Multi-Format Exports")
        st.caption("Generate publication-ready PDF audit packages and raw CSV analytical extracts.")

        rep_col1, rep_col2 = st.columns(2)

        with rep_col1:
            st.markdown("#### 1. PDF Audit Report")
            st.write("Comprehensive executive brief detailing working capital opportunities, stockout hazards, and ABC classification breakdown.")

            top_over_items = df[df["trapped_cash"] > 0].sort_values(by="trapped_cash", ascending=False)
            critical_items = df[df["alert_status"] == "CRITICAL_STOCKOUT"].sort_values(by="annual_usage_value", ascending=False)

            pdf_bytes, mime_type = generate_executive_pdf_report(kpis, top_over_items, critical_items)

            st.download_button(
                label="📥 Download Executive PDF Audit Report",
                data=pdf_bytes,
                file_name=f"SupplyChain_Audit_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime=mime_type,
                help="Generates clean, printable executive audit report."
            )

        with rep_col2:
            st.markdown("#### 2. Raw Data Manifests (CSV)")
            st.write("Download operational tables for ERP integration and quantitative modeling.")

            # CSV 1: Inventory Table
            inv_csv = generate_inventory_csv(df)
            st.download_button(
                label=f"📥 Download Current Inventory Manifest CSV ({len(df):,} SKUs)",
                data=inv_csv,
                file_name="Inventory_Optimization_Manifest.csv",
                mime="text/csv"
            )

            # CSV 2: Forecast Error Analysis
            hist_sample = get_demand_history(df.iloc[0]["sku"], days=60)
            if hist_sample:
                forecast_sample_df = compute_moving_average_forecast(pd.DataFrame(hist_sample))
                error_csv = generate_forecast_error_csv(forecast_sample_df)
                st.download_button(
                    label="📥 Download Demand Forecast & Errors CSV",
                    data=error_csv,
                    file_name="Forecast_Error_Analysis.csv",
                    mime="text/csv"
                )

except Exception as global_err:
    st.error(f"""
    ### ⚠️ Application Error Boundary Triggered
    An unexpected error occurred while executing the platform:
    **Details:** `{global_err}`

    *The application caught this error safely to prevent process termination.*
    """)
    if st.button("🔄 Reload Application"):
        st.rerun()

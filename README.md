# 📦 SupplyChainIQ | Enterprise Inventory Optimization & Management Platform

A production-ready, full-stack Supply Chain & Inventory Optimization application built with **Streamlit**, **Pandas**, **NumPy**, **SciPy**, and an encrypted **SQLite** relational backend. 

Engineered for enterprise operators, warehouse managers, and D2C brands to optimize working capital, eliminate costly stockouts, track real-time inventory movements via camera barcode scanning, and automate replenishments using industrial operations research models.

---

## 🌟 Core Application Architecture & Features

### 1. 📊 Executive Diagnostic Dashboard
- **Visual Supply Chain KPIs**:
  - **Total Inventory Value (₹)**: Real-time portfolio valuation across all active catalog items.
  - **Stockout Risk Percentage (%)**: Proportion of SKUs operating below statistical safety stock.
  - **Inventory Turnover Rate ($x$)**: Capital rotation velocity based on annual cost of goods sold.
  - **Total Trapped Working Capital (₹)**: Cash unnecessarily frozen in overstocked inventory.
- **Demand Forecasting & Trends**:
  - **Moving Average Demand Forecasting**: 7-day and 30-day moving average time-series curves plotted against actual demand.
  - **Forecast Accuracy Tracking**: Computes Mean Absolute Error (MAE) and Mean Absolute Percentage Error (MAPE).
  - **Burn-down & Optimization Curves**: Top 10 overstocked items comparing Current On-Hand Stock vs. Lean Optimal Target.

### 2. 📦 Inventory Management Module (Full CRUD)
- **Automated ABC Stratification**:
  - **Class A (Hero Items)**: Top 80% of annual usage value — strict continuous replenishment.
  - **Class B (Core Items)**: Next 15% of annual usage value — periodic reorders.
  - **Class C (Longtail Items)**: Bottom 5% of annual usage value — bulk reviews to minimize carrying cost.
- **Quantitative Parameter Automation**:
  - **Wilson Economic Order Quantity (EOQ)**:
    $$EOQ = \sqrt{\frac{2 \cdot D \cdot S}{H}}$$
    Balances batch purchase order costs against storage and capital holding rates.
  - **Probabilistic Safety Stock (SS) & Reorder Point (ROP)**:
    $$SS = Z \times \sqrt{(L \cdot \sigma_D^2) + (\text{Daily Demand}^2 \cdot \sigma_L^2)}$$
    $$ROP = (\text{Daily Demand} \cdot L) + SS$$
    Absorbs daily sales volatility and supplier delivery lead-time fluctuations at a target service level (default 95%).
- **Interactive Multi-Filter Catalog**:
  - Instant filtering by Category, Stock Hazard Status (Critical Deficit, Reorder Triggered, Overstocked, Healthy), or real-time text search.
- **Full Database CRUD**:
  - Enrolls, updates, and deletes SKUs with immediate database synchronization.

### 3. 📷 Barcode / QR Code Scanner & Rapid Stock Movements
- **Camera Scanner**: Utilizes mobile or desktop device camera to scan barcodes and QR codes directly from the browser.
- **Handheld & Manual Integration**: Accommodates standard USB/Bluetooth barcode guns and instant keyboard entries.
- **Rapid Check-In / Check-Out**: Adjust stock levels with single-click actions and automatic audit logging in the `transactions` table.

### 4. 🚨 Multi-Tier Alert System
- **Visual Hazard Banners**: Immediate top-of-page notifications when items breach safety buffers.
- **Browser Push-Style Toast**: Interactive pop-ups alert operators to critical stock deficits upon page load.
- **Prioritized Action Playbooks**: Specific supplier reorder manifests indicating exact EOQ batch sizes and supplier turnaround times.

### 5. 📑 Multi-Format Export Module
- **Executive PDF Audit Brief**: High-fidelity PDF report summarizing portfolio valuations, trapped capital recovery opportunities, and critical stockout lists.
- **Current Inventory Manifest (CSV)**: Full export of 250+ SKUs with ROP, EOQ, ABC tiering, and valuation metrics.
- **Forecast & Error Analysis (CSV)**: Raw daily demand, moving averages, and forecast variance metrics.

---

## 🛡️ Technical, Safety & Security Specifications

### Relational Schema (`inventory_system.db`)
- `suppliers`: Supplier credentials, lead times, and reliability coefficients.
- `products`: SKU identifiers, descriptions, unit costs, pricing, on-hand counts, and foreign key references to suppliers.
- `transactions`: Immutable audit log recording transaction type (`CHECK_IN`, `CHECK_OUT`, `ADJUSTMENT`, `INITIAL`), previous stock, new stock, timestamp, and notes.
- `demand_history`: 60-day historical daily sales for moving average forecasting.
- **Foreign Key Integrity**: `PRAGMA foreign_keys = ON;` enforced across all connections with cascade handling.

### Input Sanitization & Anti-XSS / SQLi
- **Anti-XSS**: All user inputs stripped of HTML and script tags via regex and entity escaping (`security.py`).
- **SQL Injection Prevention**: 100% parameterized queries (`cursor.execute(sql, (params,))`).
- **Range & Boundary Checks**: Strict validation enforcing non-negative values for inventory counts, unit costs, and lead times.

### State Management & Offline Resilience
- **Offline Mode Simulation**: If network connectivity drops, the application serves cached catalog data from SQLite.
- **Action Queuing**: Offline check-ins and check-outs are stored in `st.session_state['offline_queue']`.
- **Atomic Queue Synchronization**: One-click sync flushes queued records to the database with transaction integrity.

---

## 🚀 Setup & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Seed Database (250 Realistic Multi-Category SKUs)
```bash
python init_db.py
```

### 3. Launch Application
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser on desktop or mobile.

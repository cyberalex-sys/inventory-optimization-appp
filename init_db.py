"""
Database Initialization and Seed Script
Populates inventory_system.db with:
- 6 Realistic Enterprise Suppliers
- 250 Realistic Multi-Category Products with Barcodes
- Audit Trail Initial Transactions
- 60 Days of Historical Demand Data for Forecasting
"""

import os
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from database import init_db, get_connection

def seed_database():
    print("Initializing relational database schema...")
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM products;")
    existing_count = cursor.fetchone()[0]
    if existing_count >= 250:
        print(f"Database already populated with {existing_count} items. Skipping seed.")
        conn.close()
        return

    print("Seeding Suppliers...")
    suppliers_data = [
        ("Apex Apparel & Textiles Co.", "contact@apexapparel.com", "+91 98110 12345", 14, 0.96),
        ("BioCare Dermaceuticals Ltd.", "procurement@biocarelab.com", "+91 98220 23456", 10, 0.98),
        ("Nordic Pure Nutrition", "supply@nordicnutrition.com", "+91 98330 34567", 21, 0.92),
        ("SoleCraft Footwear Works", "orders@solecraft.in", "+91 98440 45678", 28, 0.89),
        ("AromaLuxe Home Fragrances", "sales@aromaluxe.com", "+91 98550 56789", 7, 0.97),
        ("UrbanElite Leather & Goods", "b2b@urbanelite.in", "+91 98660 67890", 18, 0.94),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO suppliers (name, contact_email, phone, lead_time_days, reliability_score)
        VALUES (?, ?, ?, ?, ?);
    """, suppliers_data)
    conn.commit()

    # Fetch supplier IDs
    cursor.execute("SELECT supplier_id, name, lead_time_days, reliability_score FROM suppliers;")
    suppliers = cursor.fetchall()
    supplier_map = {row["name"]: row["supplier_id"] for row in suppliers}
    supplier_ids = [row["supplier_id"] for row in suppliers]

    print("Generating 250 Realistic Inventory SKUs...")
    np.random.seed(42)

    categories = [
        {"prefix": "APP", "name": "Apparel", "items": ["TEE", "HOODIE", "JOGGER", "LEGGING", "CAP", "SOCKS"], "cost_range": (250, 1200), "margin": 2.4, "sup_idx": 0},
        {"prefix": "BEA", "name": "Beauty & Skincare", "items": ["SERUM", "CREAM", "CLEANSER", "SUNSCREEN", "TONER"], "cost_range": (180, 950), "margin": 2.8, "sup_idx": 1},
        {"prefix": "WEL", "name": "Wellness & Supplements", "items": ["WHEY", "CREATINE", "VITAMIN", "ASHWAGANDHA", "OMEGA3"], "cost_range": (350, 2400), "margin": 2.2, "sup_idx": 2},
        {"prefix": "FTW", "name": "Footwear", "items": ["SNEAKER", "SLIDES", "RUNNER", "LOAFER"], "cost_range": (700, 3400), "margin": 2.6, "sup_idx": 3},
        {"prefix": "HOM", "name": "Home & Fragrance", "items": ["CANDLE", "DIFFUSER", "MUG", "SPRAY", "TOWEL"], "cost_range": (220, 1100), "margin": 2.5, "sup_idx": 4},
        {"prefix": "ACC", "name": "Accessories", "items": ["WALLET", "TOTE", "DUFFLE", "CASE", "BELT"], "cost_range": (180, 1800), "margin": 2.7, "sup_idx": 5},
    ]

    products_rows = []
    transaction_rows = []
    target_count = 250
    sku_id = 1

    while len(products_rows) < target_count:
        for cat in categories:
            if len(products_rows) >= target_count:
                break

            item_type = np.random.choice(cat["items"])
            sku = f"{cat['prefix']}-{item_type}-{sku_id:03d}"
            name = f"{cat['name']} {item_type.capitalize()} Series {sku_id:03d}"
            category = cat["name"]
            supplier_id = supplier_ids[cat["sup_idx"]]

            # Cost and Price
            cost = float(np.round(np.random.uniform(cat["cost_range"][0], cat["cost_range"][1]), 2))
            price = float(np.round(cost * cat["margin"], 2))

            # Demand with Pareto skew
            tier = np.random.choice(["hero", "core", "longtail"], p=[0.15, 0.55, 0.30])
            if tier == "hero":
                annual_demand = int(np.random.randint(12000, 45000))
            elif tier == "core":
                annual_demand = int(np.random.randint(3000, 12000))
            else:
                annual_demand = int(np.random.randint(600, 3000))

            avg_daily_sales = float(np.round(annual_demand / 365.0, 1))
            spike_multiplier = np.random.uniform(1.8, 3.0)
            max_daily_sales = int(np.ceil(avg_daily_sales * spike_multiplier))

            lead_time = int(np.random.choice([7, 10, 14, 18, 21, 28]))

            # Barcode (EAN-13 style numeric format)
            barcode = f"8901234{sku_id:05d}"

            # Stock level distribution:
            # 30% overstocked (trapped cash)
            # 15% low stock (critical / below ROP)
            # 55% balanced
            status = np.random.choice(["overstock", "low_stock", "balanced"], p=[0.30, 0.15, 0.55])

            rough_eoq = np.sqrt((2 * annual_demand * 500) / (cost * 0.20))
            rough_ss = (max_daily_sales * lead_time) - (avg_daily_sales * lead_time)
            rough_opt = rough_eoq + rough_ss
            rough_rop = (avg_daily_sales * lead_time) + rough_ss

            if status == "overstock":
                current_stock = int(np.ceil(rough_opt * np.random.uniform(2.2, 4.5)))
            elif status == "low_stock":
                current_stock = int(np.maximum(4, rough_rop * np.random.uniform(0.15, 0.70)))
            else:
                current_stock = int(np.ceil(rough_opt * np.random.uniform(0.9, 1.25)))

            products_rows.append((
                sku, name, category, supplier_id, cost, price,
                current_stock, annual_demand, avg_daily_sales, max_daily_sales,
                lead_time, barcode
            ))

            # Initial transaction audit record
            transaction_rows.append((
                sku, 'INITIAL', current_stock, 0, current_stock, 'Initial catalog balance'
            ))

            sku_id += 1

    cursor.executemany("""
        INSERT INTO products (
            sku, name, category, supplier_id, unit_cost, unit_price,
            current_stock, annual_demand, avg_daily_sales, max_daily_sales,
            lead_time_days, barcode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, products_rows)

    cursor.executemany("""
        INSERT INTO transactions (sku, type, quantity, previous_stock, new_stock, notes)
        VALUES (?, ?, ?, ?, ?, ?);
    """, transaction_rows)
    conn.commit()

    print("Generating 60 Days of Demand History for Moving Average Forecasting...")
    today = datetime.now().date()
    demand_history_rows = []

    # Seed 60 days of daily sales for top items
    cursor.execute("SELECT sku, avg_daily_sales, max_daily_sales FROM products LIMIT 25;")
    sample_skus = cursor.fetchall()

    for row in sample_skus:
        sku = row["sku"]
        avg_d = row["avg_daily_sales"]
        max_d = row["max_daily_sales"]
        std_d = max(0.5, avg_d * 0.25)

        for day_offset in range(60, 0, -1):
            date_val = today - timedelta(days=day_offset)
            # Add synthetic seasonality and promotions
            day_of_week = date_val.weekday()
            weekend_boost = 1.35 if day_of_week in (4, 5, 6) else 1.0
            daily_actual = float(np.maximum(0.0, np.round(np.random.normal(avg_d * weekend_boost, std_d), 1)))

            demand_history_rows.append((sku, str(date_val), daily_actual))

    cursor.executemany("""
        INSERT INTO demand_history (sku, date, actual_demand)
        VALUES (?, ?, ?);
    """, demand_history_rows)
    conn.commit()

    conn.close()
    print(f"Database successfully seeded with {len(products_rows)} products and {len(demand_history_rows)} demand history points.")

if __name__ == "__main__":
    seed_database()

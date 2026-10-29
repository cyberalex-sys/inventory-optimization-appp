"""
Relational Database Module
Manages SQLite connection, schema definition, foreign key constraints,
CRUD operations, transaction auditing, and offline queue synchronization.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "inventory_system.db")

def get_connection() -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection with foreign keys enabled
    and row factory set for dictionary-like access.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the relational schema:
    - suppliers
    - products
    - transactions
    - demand_history
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Suppliers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        contact_email TEXT,
        phone TEXT,
        lead_time_days INTEGER NOT NULL DEFAULT 14 CHECK(lead_time_days > 0),
        reliability_score REAL NOT NULL DEFAULT 0.95 CHECK(reliability_score >= 0.0 AND reliability_score <= 1.0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Products Table (Inventory Items)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        supplier_id INTEGER NOT NULL,
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0.0),
        unit_price REAL NOT NULL CHECK(unit_price >= 0.0),
        current_stock INTEGER NOT NULL CHECK(current_stock >= 0),
        annual_demand INTEGER NOT NULL CHECK(annual_demand >= 0),
        avg_daily_sales REAL NOT NULL CHECK(avg_daily_sales >= 0.0),
        max_daily_sales INTEGER NOT NULL CHECK(max_daily_sales >= 0),
        lead_time_days INTEGER NOT NULL CHECK(lead_time_days > 0),
        barcode TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE RESTRICT
    );
    """)

    # 3. Transactions Table (Full Audit Trail for Check-In / Check-Out)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('CHECK_IN', 'CHECK_OUT', 'ADJUSTMENT', 'INITIAL')),
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        previous_stock INTEGER NOT NULL,
        new_stock INTEGER NOT NULL CHECK(new_stock >= 0),
        notes TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
    );
    """)

    # 4. Demand History Table (for Moving Average Forecasting & Errors)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS demand_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        date DATE NOT NULL,
        actual_demand REAL NOT NULL CHECK(actual_demand >= 0.0),
        forecast_demand REAL,
        forecast_error REAL,
        FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
    );
    """)

    # Create Indexes for high performance querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_supplier ON products(supplier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_sku ON transactions(sku);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_demand_sku_date ON demand_history(sku, date);")

    conn.commit()
    conn.close()

# ---------------------------------------------------------
# Supplier Operations
# ---------------------------------------------------------
def get_all_suppliers() -> List[Dict[str, Any]]:
    """Retrieves all suppliers ordered by name."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers ORDER BY name ASC;")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def create_supplier(name: str, email: str, phone: str, lead_time_days: int = 14, reliability: float = 0.95) -> int:
    """Inserts a new supplier and returns the generated supplier_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO suppliers (name, contact_email, phone, lead_time_days, reliability_score)
        VALUES (?, ?, ?, ?, ?);
    """, (name, email, phone, lead_time_days, reliability))
    supplier_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return supplier_id

# ---------------------------------------------------------
# Product (Inventory) CRUD Operations
# ---------------------------------------------------------
def get_all_products(category_filter: Optional[str] = None, supplier_filter: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all inventory products with joined supplier details,
    optionally filtered by category and supplier.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        p.*,
        s.name AS supplier_name,
        s.reliability_score AS supplier_reliability
    FROM products p
    JOIN suppliers s ON p.supplier_id = s.supplier_id
    WHERE 1=1
    """
    params = []

    if category_filter and category_filter != "All":
        query += " AND p.category = ?"
        params.append(category_filter)

    if supplier_filter is not None and supplier_filter != 0:
        query += " AND p.supplier_id = ?"
        params.append(supplier_filter)

    query += " ORDER BY p.sku ASC;"

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_product_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single product by SKU."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name AS supplier_name, s.reliability_score AS supplier_reliability
        FROM products p
        JOIN suppliers s ON p.supplier_id = s.supplier_id
        WHERE p.sku = ?;
    """, (sku.strip().upper(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_product_by_barcode(barcode: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single product by scanned Barcode/QR."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, s.name AS supplier_name
        FROM products p
        JOIN suppliers s ON p.supplier_id = s.supplier_id
        WHERE p.barcode = ? OR p.sku = ?;
    """, (barcode.strip(), barcode.strip().upper()))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_product(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Creates a new inventory item with parameterized query and logs initial transaction.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (
                sku, name, category, supplier_id, unit_cost, unit_price,
                current_stock, annual_demand, avg_daily_sales, max_daily_sales,
                lead_time_days, barcode, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        """, (
            data["sku"].strip().upper(),
            data["name"].strip(),
            data["category"].strip(),
            data["supplier_id"],
            float(data["unit_cost"]),
            float(data["unit_price"]),
            int(data["current_stock"]),
            int(data["annual_demand"]),
            float(data["avg_daily_sales"]),
            int(data["max_daily_sales"]),
            int(data["lead_time_days"]),
            data.get("barcode", "").strip() or None
        ))

        # Log initial stock creation in transactions
        cursor.execute("""
            INSERT INTO transactions (sku, type, quantity, previous_stock, new_stock, notes)
            VALUES (?, 'INITIAL', ?, 0, ?, 'Product enrolled into catalog');
        """, (data["sku"].strip().upper(), int(data["current_stock"]), int(data["current_stock"])))

        conn.commit()
        return True, "Product successfully created."
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "UNIQUE constraint failed: products.sku" in str(e):
            return False, f"SKU '{data['sku']}' already exists in inventory."
        if "UNIQUE constraint failed: products.barcode" in str(e):
            return False, f"Barcode '{data.get('barcode')}' is already assigned to another SKU."
        return False, f"Integrity error: {e}"
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {e}"
    finally:
        conn.close()

def update_product(sku: str, data: Dict[str, Any]) -> Tuple[bool, str]:
    """Updates an existing product's attributes."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products SET
                name = ?,
                category = ?,
                supplier_id = ?,
                unit_cost = ?,
                unit_price = ?,
                annual_demand = ?,
                avg_daily_sales = ?,
                max_daily_sales = ?,
                lead_time_days = ?,
                barcode = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE sku = ?;
        """, (
            data["name"].strip(),
            data["category"].strip(),
            data["supplier_id"],
            float(data["unit_cost"]),
            float(data["unit_price"]),
            int(data["annual_demand"]),
            float(data["avg_daily_sales"]),
            int(data["max_daily_sales"]),
            int(data["lead_time_days"]),
            data.get("barcode", "").strip() or None,
            sku.strip().upper()
        ))
        if cursor.rowcount == 0:
            return False, f"SKU '{sku}' not found."
        conn.commit()
        return True, "Product updated successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Update failed: {e}"
    finally:
        conn.close()

def delete_product(sku: str) -> Tuple[bool, str]:
    """Deletes a product and cascades removal of associated transactions and demand history."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE sku = ?;", (sku.strip().upper(),))
        if cursor.rowcount == 0:
            return False, f"SKU '{sku}' not found."
        conn.commit()
        return True, f"SKU '{sku}' deleted successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Deletion failed: {e}"
    finally:
        conn.close()

# ---------------------------------------------------------
# Stock Movement & Scanner Check-In / Check-Out
# ---------------------------------------------------------
def record_stock_movement(sku: str, movement_type: str, quantity: int, notes: str = "") -> Tuple[bool, str, int]:
    """
    Executes an atomic check-in (+), check-out (-), or adjustment with full audit logging.
    Guarantees stock cannot drop below zero.
    """
    clean_sku = sku.strip().upper()
    clean_type = movement_type.strip().upper()
    if clean_type not in ('CHECK_IN', 'CHECK_OUT', 'ADJUSTMENT'):
        return False, "Invalid movement type.", 0

    if quantity <= 0 and clean_type != 'ADJUSTMENT':
        return False, "Quantity must be greater than zero.", 0

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT current_stock FROM products WHERE sku = ?;", (clean_sku,))
        row = cursor.fetchone()
        if not row:
            return False, f"SKU '{clean_sku}' not found.", 0

        prev_stock = row["current_stock"]

        if clean_type == 'CHECK_IN':
            new_stock = prev_stock + quantity
        elif clean_type == 'CHECK_OUT':
            if prev_stock < quantity:
                return False, f"Insufficient stock ({prev_stock} available, requested {quantity}).", prev_stock
            new_stock = prev_stock - quantity
        else:  # ADJUSTMENT
            new_stock = max(0, quantity)

        # Update product stock
        cursor.execute("""
            UPDATE products 
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE sku = ?;
        """, (new_stock, clean_sku))

        # Log transaction
        cursor.execute("""
            INSERT INTO transactions (sku, type, quantity, previous_stock, new_stock, notes)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (clean_sku, clean_type, abs(new_stock - prev_stock), prev_stock, new_stock, notes))

        conn.commit()
        return True, f"Stock updated to {new_stock:,} units.", new_stock
    except Exception as e:
        conn.rollback()
        return False, f"Stock transaction failed: {e}", 0
    finally:
        conn.close()

def get_recent_transactions(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the audit trail of recent stock transactions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, p.name AS product_name
        FROM transactions t
        JOIN products p ON t.sku = p.sku
        ORDER BY t.timestamp DESC
        LIMIT ?;
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# ---------------------------------------------------------
# Demand History & Forecasting Records
# ---------------------------------------------------------
def get_demand_history(sku: str, days: int = 60) -> List[Dict[str, Any]]:
    """Retrieves historical demand time series for a SKU."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM demand_history 
        WHERE sku = ? 
        ORDER BY date ASC 
        LIMIT ?;
    """, (sku.strip().upper(), days))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# ---------------------------------------------------------
# Offline Queue Synchronization
# ---------------------------------------------------------
def apply_offline_queue(queue: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """
    Applies queued offline stock movements when connectivity resumes.
    Returns (successful_count, list_of_errors).
    """
    successes = 0
    errors = []
    for item in queue:
        ok, msg, _ = record_stock_movement(
            sku=item.get("sku", ""),
            movement_type=item.get("type", "CHECK_IN"),
            quantity=item.get("quantity", 1),
            notes=f"[Offline Sync] {item.get('notes', '')}"
        )
        if ok:
            successes += 1
        else:
            errors.append(f"SKU {item.get('sku')}: {msg}")
    return successes, errors

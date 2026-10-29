"""
Supply Chain Mathematical Engine
Calculates ABC Stratification, EOQ, Probabilistic Safety Stock, Reorder Points,
Moving Average Demand Forecasting, and Performance KPIs.
"""

import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, List, Tuple

def compute_inventory_metrics(
    products_df: pd.DataFrame,
    po_cost: float = 500.0,
    holding_rate: float = 0.20,
    service_level_pct: float = 95.0
) -> pd.DataFrame:
    """
    Computes complete quantitative operations metrics for all inventory items:
    - Annual Usage Value & ABC Classification
    - Economic Order Quantity (EOQ)
    - Service Level Z-Score & Probabilistic Safety Stock
    - Reorder Point (ROP) & Optimal Stock Target
    - Trapped Working Capital & Stock Risk Category
    """
    if products_df.empty:
        return products_df

    df = products_df.copy()

    # 1. Annual Usage Value & ABC Classification
    df["annual_usage_value"] = df["unit_cost"] * df["annual_demand"]
    df = df.sort_values(by="annual_usage_value", ascending=False).reset_index(drop=True)

    total_usage_val = df["annual_usage_value"].sum()
    df["cumulative_value"] = df["annual_usage_value"].cumsum()
    df["cumulative_pct"] = (df["cumulative_value"] / max(1.0, total_usage_val)) * 100.0

    abc_classes = []
    for _, row in df.iterrows():
        pct = row["cumulative_pct"]
        if pct <= 80.0:
            abc_classes.append("A")
        elif pct <= 95.0:
            abc_classes.append("B")
        else:
            abc_classes.append("C")
    df["abc_class"] = abc_classes

    # 2. Economic Order Quantity (EOQ)
    # Holding Cost per unit per year = unit_cost * holding_rate
    df["unit_holding_cost"] = np.maximum(0.01, df["unit_cost"] * holding_rate)
    df["eoq"] = np.sqrt((2.0 * df["annual_demand"] * po_cost) / df["unit_holding_cost"])

    # 3. Probabilistic Safety Stock (SS) & Reorder Point (ROP)
    z_score = float(stats.norm.ppf(service_level_pct / 100.0))

    # Standard deviation of demand (estimated at 20% of average daily sales)
    df["sigma_d"] = 0.20 * df["avg_daily_sales"]

    # Lead time uncertainty based on supplier reliability & max lead time buffer
    if "supplier_reliability" in df.columns:
        unreliability = 1.0 - df["supplier_reliability"].fillna(0.95)
        df["sigma_l"] = np.maximum(0.5, df["lead_time_days"] * unreliability)
    else:
        df["sigma_l"] = np.maximum(0.5, (df["max_daily_sales"] - df["avg_daily_sales"]) * 0.5)

    # Lead time variance formula: L * sigma_d^2 + d^2 * sigma_l^2
    variance = (df["lead_time_days"] * (df["sigma_d"] ** 2)) + ((df["avg_daily_sales"] ** 2) * (df["sigma_l"] ** 2))
    df["safety_stock"] = z_score * np.sqrt(variance)

    # Reorder Point (ROP) = (Avg Daily Demand * Lead Time) + Safety Stock
    df["reorder_point"] = (df["avg_daily_sales"] * df["lead_time_days"]) + df["safety_stock"]

    # Optimal Target = EOQ + Safety Stock
    df["optimal_target"] = df["eoq"] + df["safety_stock"]

    # 4. Trapped Cash (Stock held in excess of Optimal Target)
    excess_units = np.maximum(0.0, df["current_stock"] - df["optimal_target"])
    df["trapped_cash"] = excess_units * df["unit_cost"]

    # Current & Optimal Valuations
    df["current_valuation"] = df["current_stock"] * df["unit_cost"]
    df["optimal_valuation"] = df["optimal_target"] * df["unit_cost"]

    # Days of forward supply coverage
    safe_daily = np.where(df["avg_daily_sales"] <= 0, 0.01, df["avg_daily_sales"])
    df["days_of_supply"] = df["current_stock"] / safe_daily

    # 5. Stock Alert Categories
    alert_status = []
    for _, row in df.iterrows():
        curr = row["current_stock"]
        ss = row["safety_stock"]
        rop = row["reorder_point"]
        opt = row["optimal_target"]

        if curr <= ss:
            alert_status.append("CRITICAL_STOCKOUT")
        elif curr <= rop:
            alert_status.append("REORDER_TRIGGERED")
        elif curr > (opt * 1.5):
            alert_status.append("OVERSTOCKED")
        else:
            alert_status.append("HEALTHY")

    df["alert_status"] = alert_status

    return df

def calculate_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes overarching executive dashboard KPIs:
    - Total Inventory Value
    - Stockout Risk Percentage
    - Turnover Rate
    - Total Trapped Cash
    - Total SKUs & Hazard Counts
    """
    if df.empty:
        return {
            "total_inventory_value": 0.0,
            "stockout_risk_pct": 0.0,
            "turnover_rate": 0.0,
            "total_trapped_cash": 0.0,
            "trapped_pct": 0.0,
            "total_skus": 0,
            "critical_count": 0,
            "reorder_count": 0,
            "overstock_count": 0,
            "healthy_count": 0
        }

    total_inv_val = df["current_valuation"].sum()
    total_trapped = df["trapped_cash"].sum()
    trapped_pct = (total_trapped / max(1.0, total_inv_val)) * 100.0

    total_skus = len(df)
    critical_count = int((df["alert_status"] == "CRITICAL_STOCKOUT").sum())
    reorder_count = int((df["alert_status"] == "REORDER_TRIGGERED").sum())
    overstock_count = int((df["alert_status"] == "OVERSTOCKED").sum())
    healthy_count = int((df["alert_status"] == "HEALTHY").sum())

    stockout_risk_pct = (critical_count / max(1, total_skus)) * 100.0

    # Turnover Rate = Total Annual Demand Value / Total Inventory Value
    total_demand_val = (df["annual_demand"] * df["unit_cost"]).sum()
    turnover_rate = total_demand_val / max(1.0, total_inv_val)

    return {
        "total_inventory_value": float(total_inv_val),
        "stockout_risk_pct": float(stockout_risk_pct),
        "turnover_rate": float(turnover_rate),
        "total_trapped_cash": float(total_trapped),
        "trapped_pct": float(trapped_pct),
        "total_skus": total_skus,
        "critical_count": critical_count,
        "reorder_count": reorder_count,
        "overstock_count": overstock_count,
        "healthy_count": healthy_count
    }

def compute_moving_average_forecast(
    history_df: pd.DataFrame,
    window_short: int = 7,
    window_long: int = 30
) -> pd.DataFrame:
    """
    Computes moving average demand forecasting, forecast errors (MAE, MAPE),
    and inventory level burn-down trends.
    """
    if history_df.empty:
        return history_df

    df = history_df.sort_values(by="date").copy()
    df["actual_demand"] = pd.to_numeric(df["actual_demand"])

    # Rolling Moving Averages
    df[f"ma_{window_short}d"] = df["actual_demand"].rolling(window=window_short, min_periods=1).mean().round(1)
    df[f"ma_{window_long}d"] = df["actual_demand"].rolling(window=window_long, min_periods=1).mean().round(1)

    # Forecast Error using 7-day MA as model
    df["forecast_demand"] = df[f"ma_{window_short}d"].shift(1).fillna(df["actual_demand"])
    df["forecast_error"] = (df["actual_demand"] - df["forecast_demand"]).round(2)
    df["abs_error"] = df["forecast_error"].abs()

    # Percentage Error (handle zero division)
    safe_actual = np.where(df["actual_demand"] == 0, 1.0, df["actual_demand"])
    df["abs_pct_error"] = (df["abs_error"] / safe_actual) * 100.0

    return df

def compute_forecast_error_metrics(forecast_df: pd.DataFrame) -> Dict[str, float]:
    """Computes MAE and MAPE from forecast dataframe."""
    if forecast_df.empty or "forecast_error" not in forecast_df.columns:
        return {"mae": 0.0, "mape": 0.0}

    mae = float(forecast_df["abs_error"].mean())
    mape = float(forecast_df["abs_pct_error"].mean())
    return {
        "mae": round(mae, 2),
        "mape": round(mape, 2)
    }

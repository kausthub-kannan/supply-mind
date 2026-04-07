"""
data_generator.py
Generates realistic dummy data for the SupplyMind database and writes it to CSV files.
Run this first, then run db_init.py to load the CSVs into SQLite.
"""

import csv
import json
import random
import os
from datetime import datetime, timedelta, date

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "data"
SEED = 42
random.seed(SEED)

NUM_SUPPLIERS        = 10
NUM_SKUS             = 30
NUM_CONSUMPTION_LOGS = 200
NUM_ORDERS           = 50
NUM_RETURNS          = 20

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def rand_dt(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")

NOW        = datetime(2025, 4, 7, 12, 0, 0)
ONE_YEAR   = NOW - timedelta(days=365)
SIX_MONTHS = NOW - timedelta(days=180)

# ── 1. suppliers ──────────────────────────────────────────────────────────────
SUPPLIER_NAMES = [
    "AlphaSource Inc.",      "BetaGoods Ltd.",       "GammaTrade Co.",
    "DeltaSupply Corp.",     "EpsilonWholesale",     "ZetaDistributors",
    "EtaMaterials Group",    "ThetaLogistics Ltd.",  "IotaVendors LLC",
    "KappaResources Co.",
]

suppliers = []
for i in range(1, NUM_SUPPLIERS + 1):
    name = SUPPLIER_NAMES[i - 1]
    slug = name.split()[0].lower()
    suppliers.append({
        "supplier_id":      i,
        "supplier_name":    name,
        "lead_time_days":   random.randint(2, 21),
        "contact_email":    f"orders@{slug}.com",
        "reliability_score": round(random.uniform(0.65, 1.0), 2),
    })

with open(f"{OUTPUT_DIR}/suppliers.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=suppliers[0].keys())
    w.writeheader(); w.writerows(suppliers)
print(f"[✓] suppliers.csv  → {len(suppliers)} rows")

# ── 2. inventory ──────────────────────────────────────────────────────────────
SKU_TEMPLATES = [
    ("Bolt M8x30",        "Fasteners"),  ("Nut M8",            "Fasteners"),
    ("Washer 10mm",       "Fasteners"),  ("Steel Rod 6mm",     "Raw Material"),
    ("Aluminium Sheet 2mm","Raw Material"),("Copper Wire 1mm",  "Raw Material"),
    ("Hydraulic Seal Kit","Maintenance"),("Filter Element A",  "Maintenance"),
    ("Lubricant 5L",      "Consumables"),("Safety Gloves L",   "PPE"),
    ("Safety Helmet",     "PPE"),        ("Hi-Vis Vest L",     "PPE"),
    ("Circuit Breaker 16A","Electrical"),("Cable Tie 200mm",   "Electrical"),
    ("PVC Conduit 20mm",  "Electrical"), ("O-Ring 25mm",       "Seals"),
    ("Gasket 50mm",       "Seals"),      ("Bearing 6205",      "Mechanical"),
    ("Shaft Coupler 20mm","Mechanical"), ("Sprocket T40",      "Mechanical"),
    ("V-Belt A50",        "Mechanical"), ("Pump Impeller",     "Spare Parts"),
    ("Motor Brush Set",   "Spare Parts"),("Encoder Disc",      "Electronics"),
    ("PLC Module IO-8",   "Electronics"),("Sensor Proximity",  "Electronics"),
    ("Paint Primer 1L",   "Consumables"),("Cleaning Solvent 5L","Consumables"),
    ("Packaging Foam A4", "Packaging"),  ("Bubble Wrap Roll",  "Packaging"),
]

LOCATIONS = ["Warehouse A", "Warehouse B", "Warehouse C", "Store Room 1", "Store Room 2"]

inventory = []
for i in range(1, NUM_SKUS + 1):
    sku_name, _ = SKU_TEMPLATES[i - 1]
    sup_id = random.randint(1, NUM_SUPPLIERS)
    unit_cost = round(random.uniform(0.5, 250.0), 2)
    reorder = random.randint(10, 100)
    qty = random.randint(0, reorder * 5)        # sometimes below threshold
    inventory.append({
        "sku_id":           i,
        "sku_name":         sku_name,
        "location":         random.choice(LOCATIONS),
        "current_quantity": qty,
        "reorder_threshold":reorder,
        "unit_cost":        unit_cost,
        "supplier_id":      sup_id,
        "last_updated":     fmt_dt(rand_dt(SIX_MONTHS, NOW)),
    })

with open(f"{OUTPUT_DIR}/inventory.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=inventory[0].keys())
    w.writeheader(); w.writerows(inventory)
print(f"[✓] inventory.csv  → {len(inventory)} rows")

# ── 3. consumption_log ────────────────────────────────────────────────────────
consumption_log = []
for i in range(1, NUM_CONSUMPTION_LOGS + 1):
    log_date = rand_dt(ONE_YEAR, NOW).date()
    sku = random.choice(inventory)
    consumption_log.append({
        "log_id":            i,
        "sku_id":            sku["sku_id"],
        "quantity_consumed": random.randint(1, 50),
        "date":              fmt_date(log_date),
        "location":          sku["location"],
    })

with open(f"{OUTPUT_DIR}/consumption_log.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=consumption_log[0].keys())
    w.writeheader(); w.writerows(consumption_log)
print(f"[✓] consumption_log.csv  → {len(consumption_log)} rows")

# ── 4. supplier_orders ────────────────────────────────────────────────────────
ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]

def make_agent_trace(sku_id, qty, supplier_id):
    return json.dumps({
        "agent":   "reorder-agent-v2",
        "steps": [
            {"step": "check_inventory",   "sku_id": sku_id, "below_threshold": True},
            {"step": "select_supplier",   "supplier_id": supplier_id, "reason": "lowest_lead_time"},
            {"step": "calculate_qty",     "recommended_qty": qty},
            {"step": "draft_email",       "status": "sent"},
        ],
        "confidence": round(random.uniform(0.80, 0.99), 2),
    })

supplier_orders = []
for i in range(1, NUM_ORDERS + 1):
    inv = random.choice(inventory)
    sup_id = inv["supplier_id"]
    qty = random.randint(20, 500)
    unit_cost = inv["unit_cost"]
    created = rand_dt(ONE_YEAR, NOW)
    sup = next(s for s in suppliers if s["supplier_id"] == sup_id)
    expected = created + timedelta(days=sup["lead_time_days"] + random.randint(0, 3))
    status = random.choice(ORDER_STATUSES)
    supplier_orders.append({
        "order_id":         i,
        "email_thread_id":  f"thread_{random.randint(100000, 999999)}",
        "sku_id":           inv["sku_id"],
        "supplier_id":      sup_id,
        "quantity_ordered": qty,
        "order_value":      round(qty * unit_cost, 2),
        "status":           status,
        "created_at":       fmt_dt(created),
        "expected_delivery":fmt_dt(expected),
        "agent_trace":      make_agent_trace(inv["sku_id"], qty, sup_id),
    })

with open(f"{OUTPUT_DIR}/supplier_orders.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=supplier_orders[0].keys())
    w.writeheader(); w.writerows(supplier_orders)
print(f"[✓] supplier_orders.csv  → {len(supplier_orders)} rows")

# ── 5. returns ────────────────────────────────────────────────────────────────
RETURN_REASONS  = [
    "Wrong item shipped", "Damaged in transit", "Quantity mismatch",
    "Quality below spec", "Duplicate order", "No longer required",
]
RETURN_STATUSES = ["open", "under_review", "approved", "rejected", "refunded"]

CUSTOMER_DOMAINS = ["acme.com", "globex.io", "initech.net", "umbrella.org", "hooli.co"]

def make_agent_decision(status, reason):
    approved = status in ("approved", "refunded")
    return json.dumps({
        "agent":    "returns-agent-v1",
        "approved": approved,
        "reason_classification": reason,
        "policy_rule_matched":   "policy-" + ("full-refund" if approved else "reject-no-fault"),
        "confidence": round(random.uniform(0.75, 0.98), 2),
    })

# Only create returns for orders that exist
eligible_orders = [o for o in supplier_orders if o["status"] in ("delivered", "shipped")]
if len(eligible_orders) < NUM_RETURNS:
    eligible_orders = supplier_orders  # fallback

sampled_orders = random.sample(eligible_orders, min(NUM_RETURNS, len(eligible_orders)))

returns = []
for i, order in enumerate(sampled_orders, start=1):
    created = rand_dt(datetime.fromisoformat(order["created_at"]), NOW)
    status  = random.choice(RETURN_STATUSES)
    resolved = None
    if status in ("approved", "rejected", "refunded"):
        resolved = fmt_dt(created + timedelta(days=random.randint(1, 14)))
    reason = random.choice(RETURN_REASONS)
    returns.append({
        "return_id":       i,
        "email_thread_id": f"thread_{random.randint(100000, 999999)}",
        "customer_email":  f"procurement@{random.choice(CUSTOMER_DOMAINS)}",
        "order_id":        order["order_id"],
        "reason":          reason,
        "status":          status,
        "agent_decision":  make_agent_decision(status, reason),
        "created_at":      fmt_dt(created),
        "resolved_at":     resolved if resolved else "",
    })

with open(f"{OUTPUT_DIR}/returns.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=returns[0].keys())
    w.writeheader(); w.writerows(returns)
print(f"[✓] returns.csv  → {len(returns)} rows")

print("\nAll CSV files written to ./data/")
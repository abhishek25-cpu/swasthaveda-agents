"""Brand domain model. These are PLACEHOLDERS: edit them to match your real catalog and budgets."""
from __future__ import annotations

BRAND = "Swasthaveda Honey"

BRAND_BRIEF = (
    "Swasthaveda Honey is a D2C honey brand selling online through paid search, paid social, "
    "marketplaces, influencers and owned CRM channels. The objective is profitable growth: "
    "maximise blended ROAS without stocking out or eroding brand trust."
)

CHANNEL_DAILY_BUDGET_INR = {
    "google_ads": 12_000,
    "meta_ads": 15_000,
    "influencers": 8_000,
    "amazon_ads": 10_000,
    "crm_whatsapp_email": 3_000,
}

ROAS_TARGET = {
    "google_ads": 3.0,
    "meta_ads": 2.5,
    "influencers": 2.0,
    "amazon_ads": 3.5,
    "crm_whatsapp_email": 6.0,
}

FLAGSHIP_SKU = "raw-honey-500g"
SKU_PRICE_INR = {"raw-honey-500g": 549, "multifloral-honey-1kg": 949, "neem-honey-250g": 349}

AOV_INR = 620
UNITS_PER_ORDER = 1.4
ANOMALY_THRESHOLD_PCT = 25.0  # ROAS deviation from target that counts as an anomaly
LOW_STOCK_DAYS = 14

TREND_KEYWORDS = ["raw honey", "organic honey", "immunity booster", "ayurvedic honey", "honey benefits"]

# Demand multiplier by calendar month (winter / festive season lifts honey demand).
SEASONALITY = {1: 1.15, 2: 1.10, 3: 1.00, 4: 0.95, 5: 0.90, 6: 0.85,
               7: 0.85, 8: 0.90, 9: 1.00, 10: 1.10, 11: 1.20, 12: 1.20}

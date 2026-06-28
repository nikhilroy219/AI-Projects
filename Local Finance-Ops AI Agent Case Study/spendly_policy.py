"""
spendly_policy.py
Spendly GmbH expense policy rules as structured constants.
Used by spendly_commands.py to check transactions against policy.
Effective: January 2026 | Version 2.1
"""

# ── Spend limits by category ──────────────────────────────────────────────────

CATEGORY_LIMITS = {
    "Meals": {
        "individual_meal_max": 50.0,
        "team_meal_max": 150.0,
        "client_entertainment_max": 300.0,
        "receipt_required_above": 25.0,
    },
    "Travel": {
        "hotel_germany_per_night": 200.0,
        "hotel_major_cities_per_night": 350.0,   # London, Paris, Zurich
        "hotel_other_intl_per_night": 250.0,
        "flight_class": "economy",               # business if flight > 4 hours
        "receipt_required_above": 50.0,
    },
    "Software": {
        "individual_max_no_approval": 200.0,
        "team_tool_finance_signoff_above": 500.0,
        "receipt_required_above": 25.0,
    },
    "Transport": {
        "receipt_required_above": 30.0,
        "mileage_rate_per_km": 0.30,
    },
    "Other": {
        "dept_head_approval_above": 100.0,
        "receipt_required_above": 25.0,
    },
}

# ── General rules ─────────────────────────────────────────────────────────────

GENERAL_RECEIPT_THRESHOLD = 25.0      # EUR — receipt required above this for all categories
SUBMISSION_WINDOW_DAYS = 30           # must submit within 30 days
MISSING_RECEIPT_FLAG_DAYS = 14        # flag for potential rejection after this many days
HIGH_VALUE_REVIEW_THRESHOLD = 500.0   # unreviewed transactions above this are critical at close
CFO_APPROVAL_THRESHOLD = 2000.0       # requires CFO approval

# ── Prohibited merchants (automatic rejection) ────────────────────────────────

PROHIBITED_MERCHANT_KEYWORDS = [
    "casino",
    "nightclub",
    "adult entertainment",
    "gambling",
    "strip club",
    "zalando",
]

PROHIBITED_MERCHANT_CATEGORIES = [
    "Casino",
    "Nightclub",
    "Adult Entertainment",
    "Gambling",
    "Personal Shopping",
]

# ── Policy text (embedded in Claude system prompt) ────────────────────────────

SPENDLY_EXPENSE_POLICY = """
SPENDLY GMBH — EXPENSE POLICY (Effective January 2026, Version 2.1)

MEALS & ENTERTAINMENT
- Individual meal: max EUR 50 per person. Receipt required above EUR 25.
- Team lunch/dinner: max EUR 150 total. Receipt always required.
- Client entertainment: max EUR 300 per event. Receipt mandatory. Guest list and
  business purpose also required — without all three the expense will be rejected.
- Alcohol: allowed only for client entertainment, not for internal meals.
- Prohibited: casinos, nightclubs, adult entertainment venues, personal celebrations.

TRAVEL & HOTELS
- Hotel (Germany): max EUR 200 per night.
- Hotel (London, Paris, Zurich): max EUR 350 per night.
- Hotel (other international): max EUR 250 per night.
- Flights: economy class only. Business class permitted if flight exceeds 4 hours.
- All travel above EUR 50 requires a receipt.
- Airbnb: allowed with prior approval only.

SOFTWARE & SUBSCRIPTIONS
- Individual purchases: max EUR 200 without prior approval.
- Individual purchases above EUR 200: require Finance sign-off.
- Team or company tools above EUR 500: require Finance sign-off.
- Annual licenses: require department head pre-approval regardless of amount.
- Personal software purchases are not reimbursable.

FUEL & TRANSPORT
- Taxis/Uber: allowed for client meetings or late-night travel (after 9pm).
  Not permitted for standard commuting. Receipt required above EUR 30.
- Personal vehicle mileage: EUR 0.30/km, mileage log required.
- Public transport receipt required above EUR 25.

OTHER CATEGORY
- Written description of business purpose required.
- Department head approval required above EUR 100.
- Team merchandise and events: HR pre-approval required regardless of amount.
- Personal purchases are never reimbursable.

GENERAL RULES
- Receipts required for all transactions above EUR 25.
- Expenses must be submitted within 30 days of the transaction date.
- Missing receipts after 14 days: expense flagged for potential rejection.
- Unknown or unrecognised merchants: automatically flagged for Finance review.
- Duplicate submissions will result in disciplinary action.
- Splitting transactions to stay below approval thresholds is prohibited.

PROHIBITED MERCHANTS (Automatic Rejection)
- Casinos and gambling establishments
- Nightclubs and adult entertainment
- Personal shopping (Zalando, Amazon personal items, clothing)
- Supermarkets for personal groceries

APPROVAL MATRIX
- Under EUR 100: None (if policy-compliant)
- EUR 100–500: Department head
- EUR 500–2,000: Finance sign-off
- Above EUR 2,000: CFO approval
"""

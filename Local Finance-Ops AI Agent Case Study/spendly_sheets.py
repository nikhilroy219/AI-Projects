"""
spendly_sheets.py
Reads transaction data, policy rules, and month-end tracker from
the Spendly Finance Ops Agent — Master Data Google Sheet.

Sheet ID: 1C8XnVM2za7QWUGASMsBA2eVsHr1WP_ySh2D0zlXrZ8w
Tabs:
  - Tab 1: Transactions
  - Tab 2: Policy Rules
  - Tab 3: Month End Tracker

Auth: Google Service Account. Set GOOGLE_CREDENTIALS_FILE in .env to the
path of your downloaded credentials.json, and share the sheet with the
service account email address.
"""

import csv
import io
import logging
import os

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

log = logging.getLogger("spendly.sheets")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1C8XnVM2za7QWUGASMsBA2eVsHr1WP_ySh2D0zlXrZ8w")
CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Tab names (adjust if renamed in the sheet)
TAB_TRANSACTIONS = "Transactions"
TAB_POLICY_RULES = "Policy Rules"
TAB_MONTH_END = "Month End Tracker"


def _get_client() -> gspread.Client:
    """Authenticate and return a gspread client."""
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _rows_to_dicts(rows: list[list]) -> list[dict]:
    """Convert a list-of-lists (first row = headers) to a list of dicts."""
    if not rows or len(rows) < 2:
        return []
    headers = [h.strip() for h in rows[0]]
    return [
        {headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))}
        for row in rows[1:]
        if any(cell.strip() for cell in row)  # skip blank rows
    ]


def get_transactions() -> list[dict]:
    """
    Fetch all rows from the Transactions tab.
    Returns a list of dicts with keys matching column headers:
    Transaction ID, Date, Employee Name, Department, Merchant,
    Category, Amount (EUR), Receipt Attached, Notes, Policy Status
    """
    try:
        client = _get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = sheet.worksheet(TAB_TRANSACTIONS)
        rows = ws.get_all_values()
        data = _rows_to_dicts(rows)
        log.info("Fetched %d transactions from sheet.", len(data))
        return data
    except Exception as e:
        log.error("Failed to fetch transactions: %s", e)
        raise RuntimeError(f"Could not read Transactions tab: {e}") from e


def get_policy_rules() -> list[dict]:
    """
    Fetch all rows from the Policy Rules tab.
    Returns a list of dicts with keys:
    Category, Monthly Limit (EUR), Receipt Required Above (EUR),
    Allowed Merchants, Notes
    """
    try:
        client = _get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = sheet.worksheet(TAB_POLICY_RULES)
        rows = ws.get_all_values()
        data = _rows_to_dicts(rows)
        log.info("Fetched %d policy rules from sheet.", len(data))
        return data
    except Exception as e:
        log.error("Failed to fetch policy rules: %s", e)
        raise RuntimeError(f"Could not read Policy Rules tab: {e}") from e


def get_month_end_tracker() -> list[dict]:
    """
    Fetch all rows from the Month End Tracker tab.
    Returns a list of dicts with keys:
    Transaction ID, Coded, Receipt Confirmed, Reviewed By, Close Status
    """
    try:
        client = _get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = sheet.worksheet(TAB_MONTH_END)
        rows = ws.get_all_values()
        data = _rows_to_dicts(rows)
        log.info("Fetched %d month-end tracker rows from sheet.", len(data))
        return data
    except Exception as e:
        log.error("Failed to fetch month-end tracker: %s", e)
        raise RuntimeError(f"Could not read Month End Tracker tab: {e}") from e


def transactions_to_csv_string(transactions: list[dict]) -> str:
    """Serialise transaction list to a CSV string for passing to Claude."""
    if not transactions:
        return ""
    headers = list(transactions[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    writer.writerows(transactions)
    return buf.getvalue()

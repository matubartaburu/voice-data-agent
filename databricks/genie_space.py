#!/usr/bin/env python3
"""Crea (o reutiliza) el Genie Space de la demo sobre las tablas gold SINTÉTICAS."""
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as core  # noqa: E402
from databricks_api import Client  # noqa: E402

TITLE = "Personal Spending (synthetic demo)"
TABLES = ["gold_monthly_category", "gold_monthly_summary", "gold_daily_spend", "gold_mtd_comparison", "gold_anomalies",
          "gold_projection", "gold_recurring", "gold_income_vs_spend", "gold_missing_in_mail",
          "gold_reconciliation_monthly", "gold_weekday_pattern", "gold_usd_in_pesos", "gold_ingestion_log"]

INSTRUCTIONS = [
    "This is a synthetic personal-finance dataset (UYU = Uruguayan pesos, USD = dollars). Never add UYU and USD together; "
    "report each currency separately unless a table already converts it (gold_usd_in_pesos).\n",
    "Spanish terms: 'gasto' = spending, 'prescindible' = discretionary spending (tipo = 'prescindible'), 'esencial' = essential, "
    "'gasto variable' = variable spend (everything except fixed monthly expenses such as rent), 'aporte'/'ingreso' = income received.\n",
    "'This month' / 'este mes' means the month of as_of_date in gold_mtd_comparison (the latest loaded day), not the calendar month of today.\n",
    "For month-over-month comparisons use gold_mtd_comparison (same day of the previous month) and gold_monthly_summary (full months).\n",
    "Unusual or atypical expenses are in gold_anomalies (z_score above 3 means far above normal for that category).\n",
    "Movements that appear on the bank statement but never arrived by email are in gold_missing_in_mail; monthly totals are in "
    "gold_reconciliation_monthly. Data freshness is in gold_ingestion_log.\n",
    "Savings transfers are excluded from spending everywhere. Always show amounts with the currency.\n",
]

EXAMPLES = [
    ("How am I doing this month compared to last month at the same day?",
     "SELECT as_of_date, currency, spent_to_date, prev_month_same_point, total_change_pct, variable_to_date, "
     "prev_variable_same_point, variable_change_pct FROM {c}.gastos_demo.gold_mtd_comparison ORDER BY currency"),
    ("Were there any unusual expenses recently?",
     "SELECT day, merchant, category, amount, currency, z_score FROM {c}.gastos_demo.gold_anomalies ORDER BY day DESC LIMIT 10"),
    ("What did the bank statement show that never arrived by email?",
     "SELECT month, currency, statement_lines, missing_in_mail, amount_missing_in_mail, pct_missing "
     "FROM {c}.gastos_demo.gold_reconciliation_monthly ORDER BY month DESC, currency LIMIT 12"),
    ("At this pace, how much will I spend this month?",
     "SELECT month, currency, variable_to_date, fixed_pending, avg_daily_variable, projected_month_total "
     "FROM {c}.gastos_demo.gold_projection ORDER BY currency"),
    ("Which payments repeat every month?",
     "SELECT merchant, currency, months_seen, avg_amount FROM {c}.gastos_demo.gold_recurring ORDER BY avg_amount DESC"),
    ("Is my discretionary spending going up or down?",
     "SELECT month, discretionary_spend, discretionary_pct_of_variable, discretionary_change_vs_prev_month "
     "FROM {c}.gastos_demo.gold_monthly_summary WHERE currency = 'UYU' ORDER BY month DESC LIMIT 6"),
]
SAMPLE_QUESTIONS = [q for q, _ in EXAMPLES] + ["¿Qué día de la semana gasto más en comida?", "¿Cuánto me sobra de los aportes este mes?"]


def uid():
    return uuid.uuid4().hex


def serialized(catalog):
    return json.dumps({
        "version": 2,
        "config": {"sample_questions": [{"id": uid(), "question": [q]} for q in SAMPLE_QUESTIONS]},
        "data_sources": {"tables": [{"identifier": f"{catalog}.gastos_demo.{t}"} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": uid(), "content": INSTRUCTIONS}],
            "example_question_sqls": sorted(
                [{"id": uid(), "question": [q], "sql": [sql.format(c=catalog)]} for q, sql in EXAMPLES], key=lambda e: e["id"]),
        },
    }, ensure_ascii=False)


def main():
    c = Client()
    catalog = c.catalog
    for s in c.request("GET", "/api/2.0/genie/spaces").get("spaces", []):
        if s.get("title") == TITLE:
            print("El Space ya existe:", s["space_id"])
            return s["space_id"]
    body = {"title": TITLE, "warehouse_id": c.warehouse,
            "description": "Natural-language questions over a SYNTHETIC personal-finance medallion pipeline (bronze/silver/gold). No real data.",
            "serialized_space": serialized(catalog)}
    r = c.request("POST", "/api/2.0/genie/spaces", body)
    sid = r.get("space_id")
    print("Space creado:", sid)
    cfg = core.load_config(); cfg["genie_space_id"] = sid
    json.dump(cfg, open(core.CONFIG, "w"), indent=2, ensure_ascii=False)
    return sid


if __name__ == "__main__":
    main()

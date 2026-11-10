#!/usr/bin/env python3
"""Publica las capas como notebooks SQL en el workspace y crea un Job (bronze -> silver -> gold) en cómputo serverless."""
import base64
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from databricks_api import Client, DatabricksError  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/Shared/gastos_demo"
JOB = "gastos-demo-medallion"
LAYERS = [("bronze", "01_bronze.sql"), ("silver", "02_silver.sql"), ("gold", "03_gold.sql")]


def notebook_source(c, sql_file):
    body = open(os.path.join(HERE, "sql", sql_file), encoding="utf-8").read().replace("${catalog}", c.catalog)
    return ("-- Databricks notebook source\n" + f"USE CATALOG {c.catalog};\nUSE SCHEMA gastos_demo;\n"
            "-- COMMAND ----------\n" + body)


def main():
    c = Client(); cat = c.catalog
    c.request("POST", "/api/2.0/workspace/mkdirs", {"path": ROOT})
    for layer, f in LAYERS:
        c.request("POST", "/api/2.0/workspace/import", {
            "path": f"{ROOT}/{layer}", "format": "SOURCE", "language": "SQL", "overwrite": True,
            "content": base64.b64encode(notebook_source(c, f).encode()).decode()})
    print("notebooks publicados en", ROOT)
    for j in c.request("GET", "/api/2.1/jobs/list?name=" + JOB).get("jobs", []):
        c.request("POST", "/api/2.1/jobs/delete", {"job_id": j["job_id"]})
    tasks = []
    for i, (layer, _) in enumerate(LAYERS):
        t = {"task_key": layer, "notebook_task": {"notebook_path": f"{ROOT}/{layer}", "source": "WORKSPACE"}}
        if i:
            t["depends_on"] = [{"task_key": LAYERS[i - 1][0]}]
        tasks.append(t)
    job = c.request("POST", "/api/2.1/jobs/create", {
        "name": JOB, "tasks": tasks, "max_concurrent_runs": 1,
        "schedule": {"quartz_cron_expression": "0 0 7 * * ?", "timezone_id": "America/Montevideo", "pause_status": "PAUSED"}})
    jid = job["job_id"]
    print("job creado (programado todos los días 07:00, en pausa):", jid)
    run = c.request("POST", "/api/2.1/jobs/run-now", {"job_id": jid})["run_id"]
    t0 = time.time()
    while time.time() - t0 < 900:
        r = c.request("GET", f"/api/2.1/jobs/runs/get?run_id={run}")
        st = r["state"]
        if st.get("life_cycle_state") in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
            print("corrida:", st.get("life_cycle_state"), st.get("result_state"), st.get("state_message", "")[:200])
            print("tareas:", [(t["task_key"], t["state"].get("result_state")) for t in r.get("tasks", [])])
            return 0 if st.get("result_state") == "SUCCESS" else 1
        time.sleep(8)
    print("timeout esperando la corrida"); return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DatabricksError as e:
        print("ERROR:", e); sys.exit(1)

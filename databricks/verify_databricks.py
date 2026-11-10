#!/usr/bin/env python3
"""Verifica desde esta Mac que Databricks Free Edition responde por API (no usa datos reales).
(b) autenticación con token personal desde afuera, (c) SQL Statement API, y un intento de listar Genie Spaces."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import config as core  # noqa: E402


def token():
    r = subprocess.run(["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s",
                        "gastos-itau-databricks", "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def call(host, tok, method, path, body=None):
    req = urllib.request.Request(f"https://{host}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode(errors="replace")[:200]}
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def main():
    host, tok = core.load_config().get("databricks_host"), token()
    if not host or not tok:
        print("Faltan credenciales: corré ./demo/setup_databricks.sh (host en config.json y token en el Keychain).")
        return 1
    ok = True

    code, data = call(host, tok, "GET", "/api/2.0/sql/warehouses")
    print(f"(b) Autenticación con token desde la Mac: {'OK' if code == 200 else 'FALLÓ'} (HTTP {code})")
    if code != 200:
        print("    ", data.get("error", ""))
        return 1
    whs = data.get("warehouses", [])
    print(f"    Warehouses: {[(w.get('name'), w.get('state')) for w in whs]}")
    if not whs:
        print("    No hay warehouses: crear uno en SQL Warehouses.")
        return 1

    code, data = call(host, tok, "POST", "/api/2.0/sql/statements",
                      {"warehouse_id": whs[0]["id"], "statement": "SELECT 1 AS ok", "wait_timeout": "30s"})
    state = data.get("status", {}).get("state")
    print(f"(c) SQL Statement API (SELECT 1): {'OK' if state == 'SUCCEEDED' else 'FALLÓ'} (HTTP {code}, estado {state})")
    ok &= state == "SUCCEEDED"

    code, data = call(host, tok, "GET", "/api/2.0/genie/spaces")
    if code == 200:
        spaces = data.get("spaces", [])
        print(f"(a) Genie por API: accesible; Spaces existentes: {len(spaces)}")
    else:
        print(f"(a) Genie por API: no pude listar Spaces (HTTP {code}); crear uno a mano en 'Genie Agents' y probar la conversación.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

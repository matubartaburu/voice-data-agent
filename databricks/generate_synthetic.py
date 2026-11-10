#!/usr/bin/env python3
"""Genera un dataset 100% inventado con el mismo esquema que gastos.db (semilla fija, sin datos reales).

Siembra a propósito situaciones interesantes para consultar: gastos atípicos, recurrentes, aportes, cotización
mensual, movimientos del estado de cuenta que nunca llegaron por mail, montos sin informar y días nuevos que
entran de a poco (carpeta incoming/) para mostrar un pipeline incremental."""
import csv
import hashlib
import os
import random
from datetime import date, datetime, timedelta, timezone

SEED = 20261105
START, END = date(2025, 11, 1), date(2026, 11, 5)
CUTOFF = date(2026, 11, 1)  # lo anterior es la carga inicial; lo posterior llega "de a un día"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# categoría: (comercios inventados, monto medio UYU, prob. por día, sesgo fin de semana)
VARIABLE = {
    "Supermercado": (["Super Norte", "Mercado Central", "Almacén La Esquina"], 1250, 0.38, 1.0),
    "Comida": (["Pizzería Roma", "Burger Lab", "Sushi Corner", "DeliveryYa Envío"], 650, 0.42, 1.9),
    "Café": (["Café del Puerto", "Tostado Café"], 190, 0.30, 1.2),
    "Transporte": (["Taxi App", "Taxi App Centro"], 290, 0.35, 1.1),
    "Kiosco": (["Kiosco 24h"], 120, 0.50, 1.0),
    "Salud": (["Farmacia Central", "Óptica Visión"], 420, 0.08, 0.8),
    "Ocio": (["Cine Plaza", "Bar La Plaza"], 950, 0.10, 2.4),
    "Compras online": (["Tienda Web"], 1500, 0.06, 1.0),
}
TIPOS = {"Alquiler": "esencial", "Universidad": "esencial", "Celular": "esencial", "Supermercado": "esencial",
         "Salud": "esencial", "Gym": "esencial", "Comida": "prescindible", "Café": "prescindible",
         "Kiosco": "prescindible", "Transporte": "prescindible", "Ocio": "prescindible",
         "Compras online": "prescindible", "Suscripciones": "prescindible", "Viajes": "prescindible"}
EXCLUDED = {"Ahorro"}
# fijos con montos inventados
FIJOS = [("Alquiler", 32500.0, 1), ("Universidad", 27800.0, 10), ("Gym", 1900.0, 1), ("Celular", 1350.0, 1)]
SUBS_USD = [("Streaming Plus", 12.99, 5), ("Cloud Storage", 2.99, 12), ("AI Tools", 20.00, 18)]
ANOMALIAS = [(date(2026, 3, 14), "Electro Hogar", 18900.0, "UYU"), (date(2026, 7, 21), "Tienda Web", 9400.0, "UYU"),
             (date(2026, 10, 12), "Burger Lab", 4300.0, "UYU"), (date(2026, 9, 17), "Resort Booking", 389.90, "USD")]


def months(a, b):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def utc_iso(d, hour, minute):
    local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone(timedelta(hours=-3)))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name, header, rows, sub=""):
    folder = os.path.join(OUT, sub)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def generate():
    rnd = random.Random(SEED)
    counter = [0]

    def new_id():
        counter[0] += 1
        return hashlib.sha1(f"{SEED}-{counter[0]}".encode()).hexdigest()[:16]

    tx, lines, day_of = [], [], {}
    TXH = ["id", "date", "type", "card", "amount", "currency", "merchant", "origen", "monto_conocido"]

    def add(d, hour, minute, type_, card, amount, cur, merchant, origen="mail", known=1, in_mail=True):
        iso = utc_iso(d, hour, minute)
        row = [new_id(), iso, type_, card, f"{amount:.2f}", cur, merchant, origen, known]
        if origen == "recurrente" or in_mail:
            tx.append(row)
            day_of[row[0]] = d  # la partición inicial/incremental se hace por día LOCAL, no por fecha UTC
        if origen != "recurrente":
            lines.append([f"L{len(lines) + 1:05d}", d.isoformat(), merchant.upper().replace(" (SIN MONTO INFORMADO)", ""),
                          f"{amount:.2f}", cur])

    d = START
    while d <= END:
        weekend = d.weekday() >= 5
        for cat, (merchants, mean, p, wk) in VARIABLE.items():
            prob = min(0.95, p * (wk if weekend else 1.0))
            if rnd.random() < prob:
                amount = round(rnd.lognormvariate(0, 0.45) * mean, 2)
                merchant, known = rnd.choice(merchants), 1
                if rnd.random() < (0.06 if cat == "Kiosco" else 0.01):  # el banco no informa el monto
                    amount, known = 0.0, 0
                    merchant += " (sin monto informado)"
                in_mail = rnd.random() > 0.05  # ~5% de movimientos nunca llegan por mail
                add(d, rnd.randint(8, 22), rnd.randint(0, 59), "debito", "1111", amount, "UYU", merchant,
                    known=known, in_mail=in_mail)
                if known and rnd.random() < 0.02:
                    add(d, 23, rnd.randint(0, 59), "reembolso", "1111", amount, "UYU", merchant)
        if rnd.random() < 0.015:
            add(d, rnd.randint(9, 21), 5, "credito", "2222", round(rnd.uniform(25, 85), 2), "USD", "Intl Store")
        for name, amount, day in SUBS_USD:
            if d.day == day:
                add(d, 6, 0, "debito", "1111", amount, "USD", name)
        if d.day == 3:  # ahorro programado: no cuenta como gasto
            add(d, 10, 0, "transferencia", "1111", 12000.0, "UYU", "Transferencia a cuenta propia (ahorro)")
        for fd, merchant, amount, cur in ANOMALIAS:
            if d == fd:
                add(d, 15, 30, "credito" if cur == "USD" else "debito", "2222" if cur == "USD" else "1111",
                    amount, cur, merchant)
        for name, amount, day in FIJOS:
            if d.day == day:
                add(d, 12, 0, "manual", "-", amount, "UYU", name, origen="recurrente")
        d += timedelta(days=1)

    fx = [[m, round(39.6 + 0.12 * i + rnd.uniform(-0.25, 0.25), 2)] for i, m in enumerate(months(START, END))]
    ingresos = [[f"ing-{m}-{k}", f"{m}-{day:02d}", "Familia", f"{amt:.2f}", "UYU"]
                for m in months(START, date(2026, 10, 31))
                for k, (day, amt) in enumerate([(2, rnd.choice([30000, 35000, 40000])), (19, rnd.choice([5000, 10000, 15000]))])]
    rules = [[1, "SUPER NORTE", "Supermercado"], [2, "MERCADO CENTRAL", "Supermercado"], [3, "ALMACÉN", "Supermercado"],
             [4, "PIZZERÍA", "Comida"], [5, "BURGER", "Comida"], [6, "SUSHI", "Comida"], [7, "DELIVERYYA", "Comida"],
             [8, "CAFÉ", "Café"], [9, "TOSTADO", "Café"], [10, "TAXI", "Transporte"], [11, "KIOSCO", "Kiosco"],
             [12, "FARMACIA", "Salud"], [13, "ÓPTICA", "Salud"], [14, "CINE", "Ocio"], [15, "BAR LA PLAZA", "Ocio"],
             [16, "TIENDA WEB", "Compras online"], [17, "ELECTRO", "Compras online"],
             [18, "STREAMING", "Suscripciones"], [19, "CLOUD STORAGE", "Suscripciones"], [20, "AI TOOLS", "Suscripciones"],
             [21, "RESORT", "Viajes"], [22, "INTL STORE", "Compras online"], [23, "ALQUILER", "Alquiler"],
             [24, "UNIVERSIDAD", "Universidad"], [25, "GYM", "Gym"], [26, "CELULAR", "Celular"],
             [27, "AHORRO", "Ahorro"]]
    cat_tipo = [[c, t, "false"] for c, t in TIPOS.items()] + [[c, "excluido", "true"] for c in EXCLUDED]
    recurrentes = [[n, f"{a:.2f}", "UYU", day, "2025-11"] for n, a, day in FIJOS]

    initial = [r for r in tx if day_of[r[0]] < CUTOFF]
    incoming = {}
    for r in tx:
        if day_of[r[0]] >= CUTOFF:
            incoming.setdefault(day_of[r[0]].isoformat(), []).append(r)
    # los estados de cuenta llegan con rezago: solo hasta fin de octubre
    lines = [l for l in lines if l[1] < CUTOFF.isoformat()]

    write("transactions_initial.csv", TXH, initial, "transactions")
    for day, rows in incoming.items():
        write(f"transactions_{day}.csv", TXH, rows, "incoming")
    write("fx.csv", ["month", "usd_uyu"], fx, "dims")
    write("ingresos.csv", ["id", "date", "source", "amount", "currency"], ingresos, "dims")
    write("rules.csv", ["rule_id", "pattern", "category"], rules, "dims")
    write("category_tipo.csv", ["category", "tipo", "excluded"], cat_tipo, "dims")
    write("recurrentes.csv", ["name", "amount", "currency", "day", "desde"], recurrentes, "dims")
    write("statement_lines.csv", ["line_id", "date", "concept", "amount", "currency"], lines, "dims")
    return {"initial": len(initial), "incoming_days": len(incoming), "statement_lines": len(lines), "months": len(fx)}


if __name__ == "__main__":
    print(generate())

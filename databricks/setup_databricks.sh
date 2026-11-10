#!/bin/bash
# Guarda el token de Databricks en el Keychain y el host en config.json (ignorado por git).
# Nunca pegues el token en un chat ni lo escribas en un archivo del repo.
# Hay que correrlo en una Terminal real (necesita tu teclado), no con el "!" del chat.
set -e
cd "$(dirname "$0")/.."

echo "1) HOST: solo la dirección, algo como  dbc-xxxxxxxx-xxxx.cloud.databricks.com"
echo "   (se copia de la barra del navegador, desde 'dbc-' hasta 'databricks.com')"
read -r -p "Host: " HOST
HOST="${HOST#https://}"; HOST="${HOST%%/*}"; HOST="${HOST// /}"
if ! [[ "$HOST" =~ ^[A-Za-z0-9.-]+\.databricks\.com$ ]]; then
  echo "Eso no parece un host de Databricks (debe terminar en .databricks.com y no tener espacios ni comandos)."
  echo "No se guardó nada. Volvé a correr el script."; exit 1
fi

echo
echo "2) TOKEN: el que empieza con 'dapi' (Settings > Developer > Access tokens > Generate new token)."
echo "   No es el 'Token ID' de la tabla: ese no sirve. Se muestra UNA sola vez al generarlo."
read -r -s -p "Token (no se ve al escribir): " TOKEN
echo
if ! [[ "$TOKEN" =~ ^dapi[A-Za-z0-9]+$ ]]; then
  unset TOKEN
  echo "Ese texto no tiene formato de token personal (empieza con 'dapi' y no tiene espacios)."
  echo "No se guardó nada. Generá uno nuevo y volvé a correr el script."; exit 1
fi

security add-generic-password -U -a "$USER" -s gastos-itau-databricks -w "$TOKEN"
unset TOKEN
python3 - "$HOST" <<'PY'
import json, sys
p = "config.json"
c = json.load(open(p))
c["databricks_host"] = sys.argv[1]
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False)
PY
echo
echo "Guardado (token en Keychain, host en config.json). Probando la conexión..."
python3 demo/verify_databricks.py

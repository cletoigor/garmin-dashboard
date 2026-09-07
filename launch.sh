#!/bin/bash
# Sobe o Garmin Dashboard (se ainda nao estiver no ar) e abre no navegador.
# Reusado pelo Garmin-Dash.app (Dock) e pela skill /garmin-dash.
DIR="/Users/igorcleto/automacoes/garmin-dashboard"
cd "$DIR" || exit 1
if ! lsof -ti:5557 >/dev/null 2>&1; then
  "$DIR/.venv/bin/python" "$DIR/app.py" >/tmp/garmin.log 2>&1 &
  for _ in $(seq 1 25); do
    lsof -ti:5557 >/dev/null 2>&1 && break
    sleep 0.3
  done
fi
open "http://localhost:5557"

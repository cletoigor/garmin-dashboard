#!/bin/bash
# Atualiza cache do Garmin Dashboard todo dia as 09h via launchd.
# Em caso de falha: grava status e dispara notificacao no macOS.
DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$DIR/cron.log"

exec >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') — iniciando daily fetch"

source "$DIR/.venv/bin/activate"

# Limpa cache antigo e busca dados frescos
rm -f "$DIR/cache/"*.json
OUT=$(python -c "
import sys
sys.path.insert(0, '$DIR')
from app import fetch_multi_day, fetch_activities, fetch_fitness, write_sync_status
try:
    data = fetch_multi_day(60)
    acts = fetch_activities(20)
    fetch_fitness()
    write_sync_status(True, f'{len(data)} dias, {len(acts)} atividades', 'daily_fetch')
    print(f'OK: {len(data)} dias, {len(acts)} atividades')
except Exception as e:
    write_sync_status(False, str(e)[:200], 'daily_fetch')
    print(f'FAIL: {e}')
    raise
" 2>&1)
STATUS=$?
echo "$OUT"

if [ $STATUS -ne 0 ] || ! echo "$OUT" | grep -q "^OK:"; then
  MSG=$(echo "$OUT" | tail -1)
  osascript -e "display notification \"$MSG\" with title \"Garmin Dashboard\" subtitle \"Falha na sincronização diária\" sound name \"Basso\"" 2>/dev/null
  echo "$(date '+%Y-%m-%d %H:%M:%S') — fetch FALHOU"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') — fetch concluido"
fi

#!/usr/bin/env bash
# cron: 0 12 * * *  /opt/infra/projects/vuelos/correr_diario.sh   (12:00 UTC = 7:00am Colombia)

cd /opt/infra/projects/serpapi_vuelos
source .venv/bin/activate
mkdir -p logs
echo "===== $(date) inicio =====" >> logs/cron.log
python run.py >> logs/run.log 2>&1 || echo "run.py fallo" >> logs/cron.log
echo "===== $(date) fin =====" >> logs/cron.log
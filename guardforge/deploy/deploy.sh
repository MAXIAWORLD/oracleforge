#!/usr/bin/env bash
# GuardForge — VPS deploy script
# Run on the VPS after a fresh rsync/git pull of /opt/guardforge/backend/
#
# Usage:
#   sudo /opt/guardforge/deploy/deploy.sh          # full deploy
#   sudo /opt/guardforge/deploy/deploy.sh --install-systemd  # also (re)install systemd unit
#
# What it does:
#   1. Create venv if missing
#   2. pip install requirements
#   3. Optional: install/update systemd unit
#   4. Restart service
#   5. Smoke test /health
set -euo pipefail

GF_DIR="/opt/guardforge"
VENV="${GF_DIR}/venv"
BACKEND="${GF_DIR}/backend"
SERVICE="guardforge-backend"
UNIT_SRC="${GF_DIR}/deploy/guardforge-backend.service"
UNIT_DST="/etc/systemd/system/guardforge-backend.service"
HEALTH_URL="http://127.0.0.1:8004/health"

log() { echo "[deploy] $*"; }
fail() { echo "[deploy] ERROR: $*" >&2; exit 1; }

[[ -d "${BACKEND}" ]] || fail "${BACKEND} does not exist — rsync the code first"
[[ -f "${GF_DIR}/secrets/.env.production" ]] || fail "missing /opt/guardforge/secrets/.env.production"

log "creating venv if missing"
if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
fi

log "upgrading pip and installing requirements"
"${VENV}/bin/pip" install --quiet --upgrade pip
"${VENV}/bin/pip" install --quiet -r "${BACKEND}/requirements.txt"

if [[ "${1:-}" == "--install-systemd" ]] || [[ ! -f "${UNIT_DST}" ]]; then
    log "installing systemd unit"
    [[ -f "${UNIT_SRC}" ]] || fail "missing ${UNIT_SRC}"
    sudo cp "${UNIT_SRC}" "${UNIT_DST}"
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE}"
fi

log "restarting ${SERVICE}"
sudo systemctl restart "${SERVICE}"

log "waiting for service to be ready"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf "${HEALTH_URL}" > /dev/null; then
        log "service is up after ${i}s"
        break
    fi
    if [[ ${i} -eq 10 ]]; then
        log "service did not become healthy — last journal lines:"
        sudo journalctl -u "${SERVICE}" -n 30 --no-pager
        fail "health check failed"
    fi
    sleep 1
done

log "smoke test /health:"
curl -s "${HEALTH_URL}" | head -c 300
echo
log "done"

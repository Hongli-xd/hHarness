#!/usr/bin/env bash
# Start HistRAG web UI in a repeatable way on macOS.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS_DIR="$ROOT_DIR/Harness"
RESOURCES_DIR="$HARNESS_DIR/histrag/resources"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
LABEL="${HISTRAG_LAUNCH_LABEL:-histrag.web}"
HOST="${HISTRAG_HOST:-127.0.0.1}"
PORT="${HISTRAG_PORT:-7860}"
URL="http://$HOST:$PORT"
LOG_DIR="${HISTRAG_LOG_DIR:-$ROOT_DIR/.logs}"
STDOUT_LOG="$LOG_DIR/histrag-web.out.log"
STDERR_LOG="$LOG_DIR/histrag-web.err.log"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-00000000}"

say() {
  printf '[histrag] %s\n' "$*"
}

fail() {
  printf '[histrag] ERROR: %s\n' "$*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ensure_venv() {
  if [ ! -x "$PYTHON_BIN" ]; then
    say "creating virtual environment at $VENV_DIR"
    if command_exists python3.11; then
      python3.11 -m venv "$VENV_DIR"
    elif command_exists python3; then
      python3 -m venv "$VENV_DIR"
    else
      fail "python3 is not installed"
    fi
  fi

  if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, neo4j" >/dev/null 2>&1; then
    say "installing Python dependencies"
    "$PIP_BIN" install -U pip
    "$PIP_BIN" install -e "$HARNESS_DIR[dev]"
  fi
}

ensure_resources() {
  local missing=0
  for file in \
    "$RESOURCES_DIR/lib/d3.min.js" \
    "$RESOURCES_DIR/lib/topojson.min.js" \
    "$RESOURCES_DIR/data/countries-110m.json"; do
    if [ ! -s "$file" ]; then
      missing=1
    fi
  done

  if [ "$missing" -eq 1 ]; then
    say "map resources missing; running resources/setup.sh"
    (cd "$RESOURCES_DIR" && bash setup.sh)
  fi

  if [ -f "$RESOURCES_DIR/data/rivers.geojson" ] && grep -q '^404:' "$RESOURCES_DIR/data/rivers.geojson"; then
    say "repairing invalid rivers.geojson placeholder"
    printf '{"type":"FeatureCollection","features":[]}\n' > "$RESOURCES_DIR/data/rivers.geojson"
  fi
}

ensure_neo4j() {
  if ! command_exists cypher-shell; then
    say "cypher-shell not found; skipping Neo4j health check"
    return 0
  fi

  if cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1;" >/dev/null 2>&1; then
    say "Neo4j is reachable"
    return 0
  fi

  if command_exists brew; then
    say "Neo4j is not reachable; trying brew services start neo4j"
    brew services start neo4j >/dev/null 2>&1 || true
    sleep 5
  fi

  if cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1;" >/dev/null 2>&1; then
    say "Neo4j is reachable"
  else
    say "Neo4j is still not reachable at $NEO4J_URI"
    say "The web page can open, but graph/RAG queries may fail until Neo4j is running."
    say "If the password changed, run with: NEO4J_PASSWORD='your-password' scripts/start_histrag_web.sh"
  fi
}

start_web() {
  mkdir -p "$LOG_DIR"
  mkdir -p "$(dirname "$PLIST_PATH")"
  : > "$STDOUT_LOG"
  : > "$STDERR_LOG"

  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    say "port $PORT is already in use; replacing existing $LABEL service if present"
  fi

  cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$HARNESS_DIR:$ROOT_DIR</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>frontend.server:app</string>
    <string>--host</string>
    <string>$HOST</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$STDERR_LOG</string>
</dict>
</plist>
EOF

  launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
  launchctl kickstart -k "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

  say "waiting for web server at $URL"
  for _ in $(seq 1 30); do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      say "web server is ready: $URL"
      return 0
    fi
    sleep 1
  done

  say "web server did not become ready in time"
  say "stderr log:"
  sed -n '1,120p' "$STDERR_LOG" >&2 || true
  exit 1
}

main() {
  cd "$ROOT_DIR"
  ensure_venv
  ensure_resources
  ensure_neo4j
  start_web

  if [ "${HISTRAG_OPEN_BROWSER:-1}" = "1" ] && command_exists open; then
    open "$URL" >/dev/null 2>&1 || true
  fi

  cat <<EOF

HistRAG web is running.
URL:      $URL
Logs:     $STDERR_LOG
Stop:     launchctl bootout gui/$(id -u) "$PLIST_PATH"
Neo4j:    http://127.0.0.1:7474  user=$NEO4J_USER password=$NEO4J_PASSWORD

EOF
}

main "$@"

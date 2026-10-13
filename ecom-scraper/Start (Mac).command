#!/bin/bash
# Double-click this file to start the E-com Brand Scraper.
# The first time it installs everything (a few minutes). Close this window to stop it.

cd "$(dirname "$0")" || exit 1
URL="http://localhost:3000"

fail() {
  echo ""
  echo "⚠️  $1"
  [ -n "$2" ] && open "$2"
  read -r -p "Press Enter to close this window."
  exit 1
}

echo "=== E-com Brand Scraper ==="

command -v python3 >/dev/null 2>&1 || fail "Python isn't installed. Install it from the page that just opened, then double-click this file again." "https://www.python.org/downloads/"
command -v npm >/dev/null 2>&1 || fail "Node.js isn't installed. Install the LTS version from the page that just opened, then double-click this file again." "https://nodejs.org/"

if curl -s -o /dev/null "$URL"; then
  echo "It's already running – opening your browser."
  open "$URL"
  exit 0
fi

# --- Backend (Python) ---
cd backend || fail "Couldn't find the backend folder. Keep this file inside the ecom-scraper folder."
if [ ! -d .venv ]; then
  echo "First-time setup: installing Python packages (takes a few minutes)…"
  python3 -m venv .venv || fail "Couldn't set up Python."
fi
# shellcheck disable=SC1091
source .venv/bin/activate
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  pip install -q -r requirements.txt || fail "Installing Python packages failed. Check your internet connection and try again."
  touch .venv/.installed
fi
[ -f .env ] || cp .env.example .env

python server.py > /dev/null 2>&1 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null' EXIT

# --- Frontend (Next.js) ---
cd ../frontend || fail "Couldn't find the frontend folder."
if [ ! -d node_modules ]; then
  echo "First-time setup: installing the interface (takes a minute)…"
  npm install --no-audit --no-fund --loglevel=error || fail "Installing the interface failed. Check your internet connection and try again."
fi

# Open the browser as soon as the page is ready
(
  for _ in $(seq 1 180); do
    if curl -s -o /dev/null "$URL"; then open "$URL"; exit 0; fi
    sleep 1
  done
) &

echo ""
echo "✅ Starting… your browser will open $URL in a moment."
echo "   Keep this window open while you use the scraper. Close it to stop."
echo ""
npm run dev

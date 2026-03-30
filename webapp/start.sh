#!/usr/bin/env bash
# Start the Lunchbag webapp (backend + frontend dev server)
# Run from project root: ./webapp/start.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEBAPP="$ROOT/webapp"
FRONTEND="$WEBAPP/frontend"

echo "=== Lunchbag Webapp ==="
echo "Project root: $ROOT"

# Install Python deps if needed
if ! "$ROOT/test_env/bin/python3" -c "import flask" 2>/dev/null; then
  echo "Installing Python dependencies..."
  "$ROOT/test_env/bin/pip" install flask flask-cors -q
fi

# Install JS deps if needed
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd "$FRONTEND" && npm install
fi

# Start Flask backend in background
echo ""
echo "Starting API server on http://localhost:5001"
cd "$ROOT"
"$ROOT/test_env/bin/python3" "$WEBAPP/api.py" &
BACKEND_PID=$!

# Give Flask a moment to start
sleep 1

# Start Vite frontend
echo "Starting frontend on http://localhost:5173"
echo ""
cd "$FRONTEND" && npm run dev

# On exit, kill backend
kill $BACKEND_PID 2>/dev/null

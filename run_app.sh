#!/bin/bash

# Function to kill background processes on exit
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup SIGINT

# Function to kill process on a specific port
kill_port() {
    local port=$1
    local pids=$(lsof -t -i:$port)
    if [ ! -z "$pids" ]; then
        echo "Cleaning up port $port..."
        echo "$pids" | xargs kill -9 2>/dev/null
    fi
}

# ── Run Tests ──────────────────────────────────────────────
echo "━━━ Running Backend Tests ━━━"
cd backend
python3 -m pytest tests/ -v --tb=short
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Tests failed! Fix the failing tests before starting the app."
    exit 1
fi
echo "✅ All tests passed!"
echo ""
cd ..

# ── Start Backend ─────────────────────────────────────────
echo "Starting Backend..."
kill_port 8000
cd backend
python3 -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start Frontend
echo "Starting Frontend..."
kill_port 5173
cd frontend
npm run dev -- --host &
FRONTEND_PID=$!
cd ..

echo "Application running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
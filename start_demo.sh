#!/bin/bash
echo "Starting Call2Care Backend Server..."
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "Waiting for server to initialize..."
sleep 3

echo "Starting Ngrok..."
ngrok http 8000

echo "Cleaning up..."
kill $SERVER_PID

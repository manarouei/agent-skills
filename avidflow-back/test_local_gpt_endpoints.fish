#!/usr/bin/env fish
# Test script for Local GPT endpoints

set BASE_URL "http://178.131.134.191:11300"
set USERNAME "madna@email.com"
set PASSWORD "lavashaj"
set MODEL "gpt-oss:120b"

echo "Testing Local GPT Endpoints..."
echo "================================"
echo ""

# Test 1: OpenWebUI API endpoint
echo "Test 1: /api/chat/completions (OpenWebUI)"
curl -X POST "$BASE_URL/api/chat/completions" \
  -H "Content-Type: application/json" \
  -u "$USERNAME:$PASSWORD" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Say hello\"}],
    \"temperature\": 0.7,
    \"max_tokens\": 50
  }" \
  --max-time 30 \
  -w "\nHTTP Status: %{http_code}\n" \
  -s
echo ""
echo "---"
echo ""

# Test 2: Standard OpenAI endpoint
echo "Test 2: /v1/chat/completions (OpenAI-compatible)"
curl -X POST "$BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -u "$USERNAME:$PASSWORD" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Say hello\"}],
    \"temperature\": 0.7,
    \"max_tokens\": 50
  }" \
  --max-time 30 \
  -w "\nHTTP Status: %{http_code}\n" \
  -s
echo ""
echo "---"
echo ""

# Test 3: OpenWebUI native
echo "Test 3: /api/chat (OpenWebUI native)"
curl -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -u "$USERNAME:$PASSWORD" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [{\"role\": \"user\", \"content\": \"Say hello\"}]
  }" \
  --max-time 30 \
  -w "\nHTTP Status: %{http_code}\n" \
  -s
echo ""
echo "================================"
echo "Check which endpoint returned 200 OK"

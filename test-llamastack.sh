#!/bin/bash
# Test Llama Stack endpoints
# Usage: ./test-llamastack.sh [LLAMA_STACK_URL]

LLAMA_STACK_URL="${1:-https://llama-stack-genai-demo.apps.cluster-5t99k.5t99k.sandbox1248.opentlc.com}"

echo "=== Llama Stack: $LLAMA_STACK_URL ==="
echo ""

echo "--- GET /v1/models ---"
curl -s -X 'GET' \
  "${LLAMA_STACK_URL}/v1/models" \
  -H 'accept: application/json'
echo ""
echo ""

echo "--- POST /v1/chat/completions ---"
curl -s -X 'POST' \
  "${LLAMA_STACK_URL}/v1/chat/completions" \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
      "model": "vllm/tinyllama",
      "messages": [
        {"role": "user", "content": "Say hello in one word."}
      ],
      "max_tokens": 50
    }'
echo ""

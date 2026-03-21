#!/bin/bash
# Test Llama Stack endpoints
# Usage: ./test-llamastack.sh [LLAMA_STACK_URL]
# llamastack local service: http://llama-stack-service.genai-demo.svc.cluster.local:8321/v1 
# go to any service pod terminal and run curl "http://llama-stack-service.genai-demo.svc.cluster.local:8321/v1/models"
#  For CPU without GPU, you need non-quantized small models:
# hf://HuggingFaceTB/SmolLM2-135M
#   - TinyLlama/TinyLlama-1.1B-Chat-v1.0 (already working)
#   - facebook/opt-350m (350M, similar size to LFM2)
#   - Qwen/Qwen2.5-0.5B
#   - microsoft/phi-2 (2.7B, needs ~8GB RAM, non-quantized)
#   - SmolLM2-135M or SmolLM2-360M from HuggingFace

LLAMA_STACK_URL="http://llama-stack-service.genai-demo.svc.cluster.local:8321/v1"
LLAMA_STACK_URL="https://llama-stack-genai-demo.apps.cluster-5t99k.5t99k.sandbox1248.opentlc.com"

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
      "model": "vllm/smollm2-135m-instruct",
      "messages": [
        {"role": "user", "content": "Say hello in one word."}
      ],
      "max_tokens": 50
    }'
echo ""

#!/bin/bash
# =============================================================================
# Llama Stack API - curl test via oc exec
# =============================================================================

NAMESPACE="langflow"
DEPLOY="deploy/llama-stack"
BASE="http://localhost:8321"

run_curl() {
  local desc="$1"
  shift
  echo ""
  echo "--- $desc ---"
  oc exec -n "$NAMESPACE" "$DEPLOY" -- curl -s --max-time 30 "$@" 2>&1
  echo ""
}

echo "============================================="
echo "  Llama Stack API - curl tests"
echo "============================================="

# Health check
run_curl "Health Check" "$BASE/v1/health"

# List models
run_curl "List Models" "$BASE/v1/models"

# Chat completion
run_curl "Chat Completion" \
  "$BASE/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"vllm/llama32","messages":[{"role":"user","content":"Say hello in one sentence."}],"max_tokens":50}'

# Embeddings
run_curl "Embeddings" \
  "$BASE/v1/embeddings" \
  -H "Content-Type: application/json" \
  -d '{"model":"sentence-transformers/nomic-ai/nomic-embed-text-v1.5","input":["Hello world"]}'

echo ""
echo "============================================="
echo "  Tests complete"
echo "============================================="

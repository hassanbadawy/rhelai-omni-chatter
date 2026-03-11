#!/bin/bash
# Build: docker build -f Containerfile -t llama-stack-playground .
#
# Usage:
#   ./start-dev-container.sh              # UI only (connect to external API server)
#   ./start-dev-container.sh --with-api   # Start API server container + UI container

LLAMA_STACK_TEMPLATE="${LLAMA_STACK_TEMPLATE:-starter}"
LLAMA_STACK_PORT="${LLAMA_STACK_PORT:-8321}"

# Build the image if it doesn't exist
if ! docker image inspect llama-stack-playground > /dev/null 2>&1; then
    echo "Image not found. Building llama-stack-playground..."
    docker build -f Containerfile -t llama-stack-playground .
fi

if [ "$1" = "--with-api" ]; then
    echo "Starting Llama Stack API server (template: ${LLAMA_STACK_TEMPLATE}, port: ${LLAMA_STACK_PORT})..."
    docker run -d --rm --name llama-stack-api \
      -p "${LLAMA_STACK_PORT}:${LLAMA_STACK_PORT}" \
      -e TOGETHER_API_KEY="${TOGETHER_API_KEY}" \
      --entrypoint llama \
      llama-stack-playground \
      stack run "${LLAMA_STACK_TEMPLATE}" --port "${LLAMA_STACK_PORT}"

    echo "Waiting for API server to be ready..."
    for i in $(seq 1 120); do
        if curl -sf "http://localhost:${LLAMA_STACK_PORT}/v1/health" > /dev/null 2>&1; then
            echo "API server is ready."
            break
        fi
        if [ "$i" -eq 120 ]; then
            echo "WARNING: API server did not become ready within 120 seconds."
            echo "Check logs with: docker logs llama-stack-api"
        fi
        sleep 1
    done

    LLAMA_STACK_ENDPOINT="http://host.docker.internal:${LLAMA_STACK_PORT}"
else
    LLAMA_STACK_ENDPOINT="${LLAMA_STACK_ENDPOINT:-http://host.docker.internal:${LLAMA_STACK_PORT}}"
fi

echo "Starting Streamlit UI..."
docker run --rm --name llama-stack-ui \
  -p 8501:8501 \
  -v "$(pwd)":/app \
  -e LLAMA_STACK_ENDPOINT="${LLAMA_STACK_ENDPOINT}" \
  -e TOGETHER_API_KEY="${TOGETHER_API_KEY}" \
  llama-stack-playground

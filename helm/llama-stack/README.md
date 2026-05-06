# llama-stack

Llama Stack inference server for OpenShift, with optional guardrails and Milvus RAG support.

## Required values for production install

These values **must be customized** for each environment — defaults will not work.

| Value | Why | How to get it |
|---|---|---|
| `vllm.url` | Points at your vLLM InferenceService | `oc get inferenceservice -n <ns>` — use the cluster-internal URL on port 8443 (`https://<name>-predictor.<ns>.svc.cluster.local:8443/v1`) |
| `vllm.apiToken` | OpenShift InferenceServices require token auth. The default `"fake"` will return `Unauthorized` | `oc get secret -n <ns> default-token-<inferenceservice-name>-sa -o jsonpath='{.data.token}' \| base64 -d` |
| `vllm.modelId` | Llama Stack registers this model ID. Must match the ID exposed by vLLM | `curl -k -H "Authorization: Bearer <token>" <vllm-url>/models` and use the `id` field |

## Quick install

```bash
# Get the SA token
TOKEN=$(oc get secret -n <ns> default-token-<is-name>-sa -o jsonpath='{.data.token}' | base64 -d)

# Install without guardrails
helm install llama-stack helm/llama-stack/ -n <ns> \
  --set vllm.url="https://<is-name>-predictor.<ns>.svc.cluster.local:8443/v1" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="<model-id-from-vllm>"
```

## Install with guardrails

Requires the `guardrails-orchestrator` chart to be installed in the same namespace first.

```bash
helm install llama-stack helm/llama-stack/ -n <ns> \
  --set vllm.url="..." \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="..." \
  --set guardrails.enabled=true \
  --set guardrails.hap.enabled=true \
  --set guardrails.hap.confidence_threshold=0.5 \
  --set guardrails.prompt_injection.enabled=true \
  --set guardrails.prompt_injection.confidence_threshold=0.5 \
  --set guardrails.language_detection.enabled=true \
  --set guardrails.language_detection.confidence_threshold=0.85 \
  --set guardrails.regex.enabled=true \
  --set guardrails.regex.confidence_threshold=0.5
```

> **Always set `confidence_threshold` when enabling a shield.** A blank threshold causes `'>' not supported between 'float' and 'NoneType'` errors at runtime.

## Image pull requirements

The guardrails-enabled mode uses `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` — a third-party image. If the customer cluster blocks `quay.io/rhoai-genaiops`, mirror the image to a private registry and override `image:` in values.

The default mode uses the RHOAI operator's `rh-dev` image, which is automatically available on RHOAI clusters.

## Network requirements

| From | To | Port | Purpose |
|---|---|---|---|
| llama-stack pod | vLLM predictor svc | 8443 (or as configured) | Inference |
| llama-stack pod | guardrails-orchestrator svc | 8080 | Safety shields (when enabled) |
| llama-stack pod | milvus svc | 19530 | RAG (when `milvus.mode=remote`) |

## Verifying the install

```bash
POD=$(oc get pod -n <ns> -l app=llama-stack -o name | head -1)

# Models registered (should include your vLLM model + the embedding model)
oc exec -n <ns> $POD -- curl -s http://localhost:8321/v1/models | python3 -m json.tool

# Test inference
oc exec -n <ns> $POD -- curl -s -X POST http://localhost:8321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<your-model-id>","messages":[{"role":"user","content":"Hi"}],"max_tokens":20}'

# Shields registered (only when guardrails enabled)
oc exec -n <ns> $POD -- curl -s http://localhost:8321/v1/shields | python3 -m json.tool
```

If `/v1/models` only shows the embedding model, the vLLM connection is failing — check the SA token.

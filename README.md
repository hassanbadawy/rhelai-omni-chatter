# RHELAI Omni Chatter

AI platform stack for Red Hat OpenShift — Helm charts and deployment scripts for Langflow, Llama Stack, AnythingLLM, and supporting services.

## Helm Chart Repository

Add to OpenShift web console:

```bash
oc apply -f - <<'EOF'
apiVersion: helm.openshift.io/v1beta1
kind: HelmChartRepository
metadata:
  name: rhelai-omni-chatter
spec:
  connectionConfig:
    url: https://hassanbadawy.github.io/rhelai-omni-chatter/
  name: RHELAI Omni Chatter
EOF
```

Or add via Helm CLI:

```bash
helm repo add rhelai https://hassanbadawy.github.io/rhelai-omni-chatter/
helm repo update
helm search repo rhelai
```

## Available Charts

| Chart | Description | Port |
|-------|-------------|------|
| **langflow** | Visual LLM flow builder | 7860 |
| **llama-stack** | Llama Stack via RHOAI operator (rh-dev + SQLite) | 8321 |
| **anythingllm** | All-in-one AI app with RAG, agents, multi-user | 3001 |
| **qdrant** | Vector database for similarity search | 6333/6334 |
| **n8n** | Workflow automation platform | 5678 |
| **dashy** | Dashboard with workspace view | 8080 |
| **postgresql-stack** | PostgreSQL + pgAdmin + PostgREST + Swagger UI | 5432/5050/3000/8080 |

## Quick Start

Install individual charts from the OpenShift web console (**Developer > +Add > Helm Chart**) or via CLI:

```bash
# Example: install langflow
helm install langflow rhelai/langflow -n my-namespace

# Example: install the full PostgreSQL stack
helm install db rhelai/postgresql-stack -n my-namespace
```

## vLLM CPU Model Deployment

A generic ServingRuntime for running any HuggingFace model on CPU without GPU:

```bash
oc apply -f k8s/vllm-cpu-servingruntime.yaml -n <namespace>
```

Then deploy models from the RHOAI dashboard using **"vLLM CPU Generic Runtime"**.

### CPU-Compatible Models (no GPU required)

| Model | HuggingFace ID | Size | Chat Support |
|-------|---------------|------|-------------|
| SmolLM2-135M-Instruct | `hf://HuggingFaceTB/SmolLM2-135M-Instruct` | 135M | Yes |
| TinyLlama-1.1B-Chat | `hf://TinyLlama/TinyLlama-1.1B-Chat-v1.0` | 1.1B | Yes |
| Qwen2.5-0.5B | `hf://Qwen/Qwen2.5-0.5B` | 0.5B | Basic |
| SmolLM2-360M-Instruct | `hf://HuggingFaceTB/SmolLM2-360M-Instruct` | 360M | Yes |

> **Note**: Quantized models (GPTQ, AWQ, W4A16) require GPU. Use non-quantized models for CPU.

> **Tip**: Set env var `VLLM_CPU_KVCACHE_SPACE=1` to limit KV cache memory (allows running in 4Gi).

## Architecture

```
                    +-----------+
                    |   Dashy   |  (Dashboard)
                    +-----+-----+
                          |
          +-------+-------+-------+--------+
          |       |       |       |        |
     +----+--+ +--+---+ +-+--+ +-+------+ +--+--------+
     |Langflow| |Llama | | n8n| |Anything| |PostgreSQL |
     |        | |Stack | |    | |  LLM   | |  Stack    |
     +----+---+ +--+---+ +----+ +--------+ +--+--------+
          |        |                           |
          |   +----+----+              +-------+-------+
          |   |  vLLM   |             |pgAdmin|PostgREST|
          |   | (RHOAI) |             +-------+---+-----+
          |   +---------+                         |
          |                                 +-----+----+
          +-------> Qdrant                  |Swagger UI|
            (Vector DB)                     +----------+
```

## Llama Stack Configuration

The llama-stack chart deploys via the RHOAI operator using `LlamaStackDistribution` CR with:
- **Distribution**: `rh-dev` with ConfigMap override (SQLite storage, no PostgreSQL dependency)
- **Vector DB**: Inline Milvus (default) — Qdrant is upstream-only, not supported by rh-dev
- **Inference**: Remote vLLM provider
- **Embedding**: Inline sentence-transformers

Key values to configure:

```yaml
vllm:
  url: "http://<vllm-predictor>.<namespace>.svc.cluster.local:8080/v1"
  apiToken: "fake"
  maxTokens: "4096"
```

## Test Scripts

```bash
# Test Llama Stack endpoints (models, chat)
bash test-llamastack.sh

# Test vLLM directly (port-forward + curl)
bash test-vllm.sh
```

## Files

| File | Description |
|------|-------------|
| `helm/` | Helm charts for all services |
| `k8s/vllm-cpu-servingruntime.yaml` | Generic vLLM CPU ServingRuntime |
| `langflow-openshift.yaml` | Monolith manifest (all services) |
| `openshift-install.sh` | Installation script |
| `openshift-test.sh` | Deployment verification |
| `test-llamastack.sh` | Llama Stack API test |
| `test-vllm.sh` | vLLM endpoint test |
| `langflow-vllm-component.py` | Custom Langflow vLLM component (fixes empty kwarg issues) |

## OpenShift Tips

- All routes use TLS edge termination with `insecureEdgeTerminationPolicy: Redirect`
- pgAdmin and AnythingLLM require `anyuid` SCC (they run as root)
- Use internal service URLs between pods: `http://<svc>.<namespace>.svc.cluster.local:<port>`
- KServe predictor services are headless — use external routes for cross-namespace access
- Set `haproxy.router.openshift.io/timeout=120s` on routes for slow model responses

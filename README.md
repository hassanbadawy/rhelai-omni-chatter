# Langflow Stack on OpenShift

A multi-service AI platform deployed on Red Hat OpenShift. Includes Langflow, Llama Stack, Qdrant, n8n, PostgreSQL, PostgREST, and Swagger UI.

## Architecture

```
                    ┌──────────────┐
                    │   Langflow   │ :7860 - Visual LLM flow builder
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              v            v            v
     ┌────────────┐ ┌────────────┐ ┌────────┐
     │ Llama Stack│ │   vLLM     │ │ Qdrant │ :6333 - Vector DB
     │   :8321    │ │ (external) │ └────────┘
     └─────┬──────┘ └────────────┘
           │
           v
     ┌────────────┐
     │   vLLM     │ - Model serving (KServe)
     └────────────┘

     ┌────────┐  ┌───────────┐  ┌────────────┐  ┌────────────┐
     │  n8n   │  │ PostgreSQL│  │  PostgREST  │  │ Swagger UI │
     │ :5678  │  │   :5432   │  │    :3000    │  │   :8080    │
     └────────┘  └───────────┘  └─────────────┘  └────────────┘
```

## Quick Start

```bash
# Deploy to OpenShift
./openshift-install.sh

# Verify deployment
./openshift-test.sh

# Test Llama Stack API (health, models, chat, embeddings)
./openshift-curl-test.sh

# Find vLLM services on the cluster
./openshift-lookfor-vllm.sh

# Local dev with Podman (port 7860)
./run.sh
```

## Stack Components

| Component | Port | Description |
|-----------|------|-------------|
| Langflow | 7860 | Visual LLM flow builder |
| Llama Stack | 8321 | AI API layer (inference, RAG, agents, safety) |
| Qdrant | 6333/6334 | Vector database |
| n8n | 5678 | Workflow automation |
| PostgreSQL | 5432 | Relational database |
| PostgREST | 3000 | RESTful API for PostgreSQL |
| Swagger UI | 8080 | API documentation |

## Connecting Langflow to LLMs

### Langflow -> vLLM (direct)

Use the **vLLM** block in Langflow:

| Setting | Value |
|---------|-------|
| Model Name | `llama32` |
| vLLM API Base | `https://llama32-ai501.apps.ocp.8r4k4.sandbox235.opentlc.com/v1` |
| API Key | `fake` (anything) |

This connects Langflow directly to the vLLM model server for raw inference.

### Langflow -> Llama Stack

Use the **OpenAI-compatible** block in Langflow:

| Setting | Value |
|---------|-------|
| API Base | `https://llama-stack-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com/v1` |
| Model Name | `vllm/llama32` |
| API Key | `fake` (any non-empty string) |

This routes through Llama Stack, which adds agents, RAG, safety, and tool support on top of vLLM.

### Internal Service URLs (within the cluster)

| Service | URL |
|---------|-----|
| Llama Stack | `http://llama-stack-service.langflow.svc:8321` |
| Qdrant | `http://qdrant.langflow.svc:6333` |
| PostgreSQL | `postgresql.langflow.svc:5432` |
| PostgREST | `http://postgrest.langflow.svc:3000` |

## Prerequisites

- Red Hat OpenShift cluster with RHOAI (Red Hat OpenShift AI) installed
- Llama Stack operator activated
- vLLM model serving endpoint available (via KServe InferenceService)

## Finding vLLM on a New Cluster

```bash
# Find InferenceServices (KServe/RHOAI-managed vLLM)
oc get inferenceservice -A

# Find related services and routes
oc get svc -A | grep -i -E "vllm|llama|predictor"
oc get route -A | grep -i -E "vllm|llama"
```

## Files

| File | Description |
|------|-------------|
| `langflow-openshift.yaml` | Main manifest (Namespace, Deployments, Services, Routes, NetworkPolicy, CR) |
| `openshift-install.sh` | Installation script |
| `openshift-test.sh` | Deployment verification script |
| `openshift-curl-test.sh` | API test script (health, models, chat, embeddings) |
| `openshift-lookfor-vllm.sh` | Discovers vLLM services across the cluster |
| `run.sh` | Local Podman-based Langflow |

## Key Notes

- Llama Stack uses the `rh-dev` distribution with a ConfigMap override for SQLite storage (avoids PostgreSQL dependency)
- The Llama Stack operator creates a NetworkPolicy that blocks external access by default — the manifest includes an additional NetworkPolicy to allow the OpenShift router and same-namespace pods
- vLLM InferenceServices use headless services — use external routes for cross-namespace access from Langflow
- vLLM being down does not prevent the stack from starting — Llama Stack only validates that the URL is configured, not that it's reachable

# access routes

  - Langflow — https://langflow-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com                                                                         
  - Llama Stack — https://llama-stack-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com/docs                                                              
  - Qdrant — https://qdrant-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com/dashboard                                                                   
  - n8n — https://n8n-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com                                                                                   
  - PostgREST — https://postgrest-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com                                                                       
  - Swagger UI — https://swagger-ui-langflow.apps.ocp.8r4k4.sandbox235.opentlc.com     
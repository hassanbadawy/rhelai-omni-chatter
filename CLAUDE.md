# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Langflow Stack — a multi-service AI platform deployed on Red Hat OpenShift. Includes Langflow, Llama Stack, Qdrant, n8n, PostgreSQL, PostgREST, and Swagger UI.

## Files

- `langflow-openshift.yaml` — Main manifest with all Kubernetes resources (Namespace, Deployments, Services, Routes, NetworkPolicy, LlamaStackDistribution CR)
- `openshift-install.sh` — Installation script (login, cleanup old resources, activate operator, apply manifest)
- `openshift-test.sh` — Verification script (checks pods, services, routes, logs, health)
- `openshift-curl-test.sh` — API test script (health, models, chat completion, embeddings via oc exec)
- `openshift-lookfor-vllm.sh` — Discovers vLLM InferenceServices and related services across the cluster
- `run.sh` — Local Podman-based Langflow for development

## Deployment

```bash
# OpenShift deployment
./openshift-install.sh

# Verify deployment
./openshift-test.sh

# Local dev (Podman, port 7860)
./run.sh
```

## OpenShift Stack Components

| Component | Port | Image |
|-----------|------|-------|
| Langflow | 7860 | `langflowai/langflow:latest` |
| Llama Stack | 8321 | Managed by LlamaStackDistribution CR (rh-dev distribution) |
| Qdrant | 6333/6334 | `docker.io/qdrant/qdrant:latest` |
| n8n | 5678 | `docker.io/n8nio/n8n:latest` |
| PostgreSQL | 5432 | `registry.redhat.io/rhel9/postgresql-16:latest` |
| PostgREST | 3000 | `docker.io/postgrest/postgrest:latest` |
| Swagger UI | 8080 | `docker.io/swaggerapi/swagger-ui:latest` |

## Llama Stack on OpenShift — Key Knowledge

### Distribution Choices

- **`starter`**: Upstream community distribution. **NOT supported by RHOAI operator** — will fail with "Distribution name not supported".
- **`rh-dev`** (currently used): The ONLY distribution supported by the RHOAI operator. Defaults to PostgreSQL for metadata storage — will crash without it. **Must** use a ConfigMap with custom `run.yaml` (SQLite storage) to avoid PostgreSQL dependency. This is the documented Red Hat lab pattern.
- Never use `rh-dev` without a ConfigMap override or providing PostgreSQL connection.

### LlamaStackDistribution CR (Operator-managed)

The Llama Stack Operator is part of Red Hat OpenShift AI (RHOAI). Activate it via:
```bash
oc patch datasciencecluster default-dsc --type=merge \
  -p '{"spec":{"components":{"llamastackoperator":{"managementState":"Managed"}}}}'
```

The operator creates Deployment, Service, PVC, and **NetworkPolicy** automatically from the CR. Do NOT create raw Deployments for llama-stack when using the operator.

### CR Structure (starter)

```yaml
apiVersion: llamastack.io/v1alpha1
kind: LlamaStackDistribution
metadata:
  name: llama-stack
spec:
  replicas: 1
  server:
    distribution:
      name: starter
    containerSpec:
      port: 8321
      env:
        - name: VLLM_URL
          value: "http://..."
        - name: VLLM_MAX_TOKENS
          value: "4096"
        - name: VLLM_API_TOKEN
          value: "fake"
    storage:
      size: "20Gi"
      mountPath: "/home/lls/.lls"
```

### CR Structure (rh-dev with ConfigMap override)

If using `rh-dev`, you MUST provide a ConfigMap with a custom `run.yaml`:
```yaml
spec:
  server:
    distribution:
      name: rh-dev
    containerSpec:
      command:
        - /bin/sh
        - "-c"
        - llama stack run /etc/llama-stack/run.yaml
    userConfig:
      configMapName: llama-stack-config
```

The ConfigMap must contain a `config.yaml` key (not `run.yaml`) defining all providers and storage backends. See the Red Hat lab example at `https://github.com/burrsutter/fantaco-redhat-one-2026`.

### Vector Database Options (rh-dev only)

| Option | Env Vars Needed | External Infra |
|--------|----------------|----------------|
| Inline Milvus | None (default) | No |
| Remote Milvus | `MILVUS_ENDPOINT`, `MILVUS_TOKEN`, `MILVUS_CONSISTENCY_LEVEL` | Yes (etcd + Milvus) |
| Inline FAISS | None (RHOAI 3.0+) | No |

Qdrant is NOT supported by the rh-dev distribution. It's an upstream-only provider.

### Env Var Names

- vLLM: `VLLM_URL` (env var), `VLLM_API_TOKEN`, `VLLM_TLS_VERIFY`, `VLLM_MAX_TOKENS`
- **In ConfigMap config.yaml, use `base_url` (not `url`)** for the vLLM endpoint. The Pydantic model (`VLLMInferenceAdapterConfig`) expects `base_url`; using `url` is silently ignored.
- PostgreSQL (rh-dev default storage): `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Note: `INFERENCE_MODEL` is used by rh-dev but NOT by starter

### Common Pitfalls

1. **rh-dev crashes with "Could not connect to PostgreSQL"** — The rh-dev distribution defaults to PostgreSQL for kvstore. Either provide PostgreSQL env vars or use a ConfigMap with SQLite storage.
2. **"Provider 'vllm-inference' not found"** — Happens with custom RHOAI images that have their own entrypoint generating a different run.yaml. Use the operator-managed approach instead.
3. **Env vars ignored by rh-dev** — The rh-dev built-in run.yaml may not reference `${env.POSTGRES_HOST}` etc. The ConfigMap approach is the only reliable way to customize rh-dev.
4. **Don't mix raw Deployments with the operator** — If using LlamaStackDistribution CR, the operator manages the Deployment/Service. Clean up any manually created llama-stack Deployment/Service/Route before applying the CR.
5. **Operator NetworkPolicy blocks external access** — The operator creates a NetworkPolicy that only allows ingress from pods labeled `app.kubernetes.io/part-of: llama-stack` and the `redhat-ods-applications` namespace. To expose llama-stack via a Route or allow other pods (e.g., Langflow) to reach it, you must create an additional NetworkPolicy allowing ingress from the OpenShift router (`network.openshift.io/policy-group: ingress`) and same-namespace pods.
6. **vLLM InferenceService uses headless services** — KServe predictor services have `clusterIP: None`, which can cause cross-namespace connectivity issues. Use the external route URL instead for Langflow vLLM blocks.

## OpenShift Tips

- All routes use TLS edge termination with `insecureEdgeTerminationPolicy: Redirect`
- PostgreSQL route uses `tls.termination: passthrough` (not edge)
- Non-root containers need `securityContext` with `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, and drop ALL capabilities
- Use `emptyDir: {}` volumes for temp/cache dirs that need write access
- Langflow needs writable dirs at `/app/data`, `/tmp`, and `/.cache`
- PostgreSQL on RHEL9 image uses env vars: `POSTGRESQL_USER`, `POSTGRESQL_PASSWORD`, `POSTGRESQL_DATABASE`
- PostgREST connects via: `PGRST_DB_URI=postgres://user:pass@postgresql.langflow.svc:5432/dbname`
- Qdrant internal URL for Langflow flows: `http://qdrant.langflow.svc:6333` or `http://qdrant:6333`

## Finding vLLM on a New Cluster

```bash
# Find InferenceServices (KServe/RHOAI-managed vLLM)
oc get inferenceservice -A
# Find related services
oc get svc -A | grep -i -E "vllm|llama|predictor"
# Find external routes
oc get route -A | grep -i -E "vllm|llama"
```

Internal URL pattern: `http://<service-name>.<namespace>.svc:port/v1`
Note: KServe predictor services are headless — use external routes for cross-namespace access from Langflow.

## Reference Links

- Red Hat Llama Stack docs: `https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.0/html-single/working_with_llama_stack/index`
- OpenDataHub Llama Stack: `https://opendatahub.io/docs/working-with-llama-stack/`
- Llama Stack demos: `https://github.com/opendatahub-io/llama-stack-demos/tree/main/deployment/kubernetes`
- Red Hat lab example: `https://github.com/burrsutter/fantaco-redhat-one-2026`
- Llama Stack K8s Operator: `https://github.com/llamastack/llama-stack-k8s-operator`

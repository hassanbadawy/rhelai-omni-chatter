# Deployment & Ops

## Summary [coverage: high -- 4 sources]

`rhelai-omni-chatter` is a multi-service AI platform deployed onto Red Hat OpenShift via Helm. The core inference path (Llama Stack + vLLM-served LLM + optional Guardrails Orchestrator + optional Milvus) and a custom Streamlit UI are all packaged as Helm charts under [`helm/`](../../helm/) and published as a Helm repository at `https://hassanbadawy.github.io/rhelai-omni-chatter/`. Charts are installed either from the OpenShift web console (the user's default install path — see user memory) or from the CLI via `helm upgrade --install`. Each chart is **self-contained**: it must work in any namespace without external KServe-resident detectors or other cross-namespace dependencies, because OpenShift web-console users cannot wire those up by hand.

Two deploy modes are gated by `guardrails.enabled` on the `llama-stack` chart — a default mode using the RHOAI operator's `rh-dev` image with `inline::llama-guard`, and a guardrails mode using `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` with `remote::trusty_fms`. Auxiliary charts (LiteMaaS, PostgreSQL, MinIO, Langflow, n8n, etc.) cover the broader RHOAI environment but are not on the inference path.

## Architecture & Design [coverage: high -- 2 sources]

### Chart catalog

| Chart | Role | Status / notes |
|-------|------|----------------|
| `helm/llama-stack` | Llama Stack distribution (LLM + safety + RAG runtime) | Two modes via `guardrails.enabled`. Operator-managed: chart deploys a `LlamaStackDistribution` CR; the operator creates the Service named `llama-stack-service` (not `llama-stack`). |
| `helm/llama-stack-ui` | Custom Streamlit UI (built from `llama-stack-ui/`) | Preferred UI. Defaults `ui.llamaStackUrl=http://llama-stack-service:8321`. Image built in-cluster via `oc new-build` using `Containerfile`. |
| `helm/llama-stack-playground` | Upstream genaiops Streamlit playground (`quay.io/rhoai-genaiops/llama-stack-playground:0.3.0-fix`) | Standalone, only needs a Llama Stack URL. Has known upload bug (`AttributeError: 'dict' object has no attribute 'content'`) and shields-only-in-Agent-mode bug — prefer `llama-stack-ui`. |
| `helm/guardrails-orchestrator` | TrustyAI/FMS Guardrails Orchestrator + bundled HF detectors | v0.2.0+ self-contained: each `type: huggingface` detector entry generates its own `Deployment`+`Service` with an `initContainer` that runs `snapshot_download()` into an `emptyDir` at `/mnt/models`. No external `ai501` namespace dependency. |
| `helm/milvus` | Standalone Milvus vector DB | Optional. Default token `root:Milvus` — `remote::milvus` provider requires a non-empty token field or fails with `Field required`. |
| `helm/postgresql`, `helm/postgresql-stack`, `helm/pgadmin`, `helm/postgrest` | Postgres stack | Supporting services. |
| `helm/litemaas`, `helm/anythingllm`, `helm/dashy`, `helm/docling-serve`, `helm/gitea`, `helm/langflow`, `helm/minio`, `helm/n8n`, `helm/qdrant`, `helm/swagger-ui` | Supporting / utility charts | Not on the core inference path. |

### Helm repository (gh-pages)

Published at `https://hassanbadawy.github.io/rhelai-omni-chatter/`. Chart `.tgz` packages are stored as **GitHub Releases**; the repo's `index.yaml` lives on the **`gh-pages` branch**. Add the repo:

```bash
helm repo add hassanbadawy https://hassanbadawy.github.io/rhelai-omni-chatter/
helm install llama-stack hassanbadawy/llama-stack
```

### Routes & TLS

Each user-facing chart enables an OpenShift `Route` with **edge TLS termination** (`route.enabled: true` is the default on `llama-stack-ui` and `llama-stack-playground`). In-cluster traffic between pods uses plain HTTP on the operator-created `*-service` ClusterIP — except for vLLM, which is fronted by kube-rbac-proxy on `:8443` with self-signed certs and therefore needs `tls_verify: false` on the Llama Stack vLLM provider.

### How charts compose

```
llama-stack-ui (chart)
    --[ui.llamaStackUrl="http://llama-stack-service:8321"]-->
        llama-stack (chart, deploys LlamaStackDistribution CR)
            --[remote::vllm provider, vllm.url=https://<isvc>-predictor.<ns>.svc.cluster.local:8443/v1, tls_verify=false]-->
                vLLM InferenceService (KServe)
            --[remote::trusty_fms provider, when guardrails.enabled=true]-->
                guardrails-orchestrator (chart) --> bundled HF detectors
            --[remote::milvus provider, when milvus.mode=remote]-->
                milvus (chart) at http://milvus.<ns>.svc:19530
```

Internal URLs (only reachable in-cluster):

| Component | URL |
|-----------|-----|
| Llama Stack | `http://llama-stack-service:8321` |
| HAP detector (legacy ai501) | `http://guardrails-detector-ibm-hap-predictor.ai501.svc:8000` |
| Prompt-injection detector (legacy ai501) | `http://prompt-injection-detector-predictor.ai501.svc:8000` |
| Language detector (legacy ai501) | `http://language-detector-predictor.ai501.svc:8000` |
| Milvus (when remote) | `http://milvus.<ns>.svc:19530` |

## Decisions & Rationale [coverage: medium -- 2 sources]

**Charts must be self-contained.** The user's primary install path is the OpenShift web console (per the user-memory note `user_openshift_webconsole.md`), which does not let an installer hand-wire detectors in another namespace. The legacy pattern (detectors in `ai501`, orchestrator in `user1-canopy`) breaks the moment a new tenant tries to install via the console. As of `helm/guardrails-orchestrator` v0.2.0, every detector is generated by the same chart from a `type: huggingface` entry in `values.yaml`, with an `initContainer` that pulls the model into an `emptyDir`. New deployments do not need `ai501`.

**Operator-created Service is `llama-stack-service`.** The `llama-stack` chart submits a `LlamaStackDistribution` CR; the `llama-stack-k8s-operator` then generates the Service and names it `<name>-service`, not `<name>`. The `llama-stack-playground` chart originally defaulted `playground.llamaStackUrl=http://llama-stack:8321` — that URL only matches deployment-as-service patterns (helm-only, no operator) and DNS-fails inside the pod (`nslookup llama-stack` exit code 6) on operator installs. Both `llama-stack-playground` and `llama-stack-ui` now default `llamaStackUrl` / `ui.llamaStackUrl` to `http://llama-stack-service:8321` (pitfalls.md #18).

**Wrap genaiops chart bugs in our own chart.** The genaiops `llama-stack-operator-instance` chart only includes `vector_io: remote::milvus` when `.Release.Namespace` contains `"test"` or `"prod"`, leaving custom-named tenants (e.g. `user1-canopy`) with `inline::milvus` and ephemeral RAG state. Our chart replaces this with a simple `milvus.mode={inline,remote}` value, works in any namespace, and always emits a `vector_io` provider when `rag.enabled`. The genaiops `0.3.0-fix` playground image also has a `RAGDocument` dict-vs-object crash on file upload (`upload.py:59` does `doc.content.encode(...)` but the SDK returns a dict). We wrap that by shipping our own UI (`helm/llama-stack-ui`) instead of trying to patch the upstream image (pitfalls.md #19).

**Use `remote::trusty_fms`, not `remote::passthrough`.** `remote::passthrough` calls `POST /moderations` (OpenAI moderations format). FMS Guardrails Orchestrator exposes `POST /api/v2/text/detection/content` (IBM format). Different request and response schemas — no violations are ever detected if you mismatch them. `remote::trusty_fms` is only available in the custom `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms` image, which is why our chart switches images when `guardrails.enabled=true` (pitfalls.md #14).

## Operational Notes [coverage: high -- 1 source]

### Cluster login

```bash
# As of 2026-05-09
source .env  # OC_USER, OC_PASSWORD, CLUSTER_DOMAIN
oc login -u $OC_USER -p $OC_PASSWORD https://api.$CLUSTER_DOMAIN:6443 --insecure-skip-tls-verify
```

### Discover services on a fresh cluster

```bash
oc get inferenceservice -A
oc get inferenceservice -A | grep -iE "guard|hap|inject|language"
oc get svc -A | grep -iE "vllm|llama|predictor|guard|milvus"
oc get route -A | grep -iE "vllm|llama|guard"
```

### Deploy llama-stack with guardrails

Always re-source `vllm.url`, `vllm.apiToken`, `vllm.modelId` from the live cluster — never reuse stale values.

```bash
# As of 2026-05-09
NS=user1-canopy
ISVC=qwen25-7b-instruct
TOKEN=$(oc get secret -n $NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d)
VLLM_URL="https://${ISVC}-predictor.${NS}.svc.cluster.local:8443/v1"

helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set guardrails.enabled=true \
  --set guardrails.hap.enabled=true \
  --set guardrails.hap.confidence_threshold=0.5 \
  --set guardrails.prompt_injection.enabled=true \
  --set guardrails.prompt_injection.confidence_threshold=0.5 \
  --set guardrails.language_detection.enabled=true \
  --set guardrails.language_detection.confidence_threshold=0.99 \
  --set guardrails.regex.enabled=true \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus.${NS}.svc:19530" \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

`confidence_threshold` must be set **explicitly** on every enabled shield. Blank renders as YAML null and the `trusty_fms` provider crashes with `'>' not supported between 'float' and 'NoneType'`. Defaults: `hap=0.5`, `prompt_injection=0.5`, `language_detection=0.85` (raise to 0.99 if you keep it on, see pitfalls.md #23), `regex=0.5`.

### Deploy llama-stack without guardrails

```bash
helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

### Verification curls

```bash
# Models registered (must include the vllm/-prefixed LLM)
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/models | jq '.data[].id'

# Vector_io provider — check inline vs remote Milvus
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/providers \
  | jq '.[] | select(.api=="vector_io") | {provider_id, provider_type}'

# Shields registered
oc exec -n $NS deployment/llama-stack -- \
  curl -s http://llama-stack-service:8321/v1/shields | jq '.data[].identifier'
```

### Route timeout for long file uploads

OpenShift routes default to a 30-second timeout. Embedding a large document during upload can exceed it.

```bash
oc annotate route llama-stack -n $NS \
  haproxy.router.openshift.io/timeout=300s
```

### Build llama-stack-ui image in-cluster

```bash
# As of 2026-05-09
NS=user1-canopy
oc new-build --binary --strategy=docker --name=llama-stack-ui -n $NS
oc patch bc/llama-stack-ui -n $NS --type=json \
  -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]'
oc start-build llama-stack-ui --from-dir=./llama-stack-ui --follow -n $NS

helm upgrade --install llama-stack-ui helm/llama-stack-ui/ -n $NS \
  --set ui.llamaStackUrl="http://llama-stack-service:8321" \
  --set ui.defaultModel="vllm/qwen25-7b-instruct"
```

### Helm chart release flow

```bash
# 1. Bump version in helm/<chart>/Chart.yaml

# 2. Package
helm package helm/<chart>/

# 3. Create GitHub release with the .tgz attached
gh release create <chart>-<version> <chart>-<version>.tgz \
  --title "<chart> <version>" \
  --notes "Release notes here"

# 4. Update gh-pages index.yaml
git checkout gh-pages
helm repo index --merge index.yaml --url https://hassanbadawy.github.io/rhelai-omni-chatter .
git add index.yaml
git commit -m "Add <chart> <version>"
git push
git checkout main
```

### Debug: chat completions return APIConnectionError 500

Likely causes (in order):

1. `tls_verify` missing in the vLLM provider config. Both guardrails and non-guardrails config blocks must have `tls_verify: false`.
2. Stale `vllm.url` from `--reuse-values`. Re-source from the cluster.
3. Stale SA token. `oc get secret -n $NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d` and re-set.
4. Wrong model ID — `/v1/models` returns the registered LLM with a `vllm/` prefix; the UI must use the prefixed ID.

Confirm by curl-ing vLLM directly from the llama-stack pod:

```bash
oc exec -n $NS deployment/llama-stack -- \
  curl -k -H "Authorization: Bearer $TOKEN" "$VLLM_URL/models"
```

## Pitfalls & Known Issues [coverage: high -- 1 source]

**`helm upgrade --reuse-values` carries forward stale `vllm.url` / `vllm.apiToken` / `vllm.modelId`** (pitfalls.md #24). When someone swaps the running InferenceService (e.g. stops Qwen3, starts Qwen2.5) or rotates the SA token, `--reuse-values` reuses the old values literally. Llama Stack returns `APIConnectionError` (DNS) or `404 model not found`. Always re-source the cluster-truth values on every upgrade — the `default-token-<isvc>-sa` secret name is reproducible from the InferenceService name, so this is fully scriptable. Detect with `helm get values llama-stack -n <ns> | grep -E 'url|modelId'`.

**Manual `oc create route` conflicts with `helm upgrade`** (CLAUDE.md). If you manually created a Route for `llama-stack`, `helm upgrade` will fail with "cannot import into current release". Delete the manual route before upgrading: `oc delete route llama-stack -n <namespace>`.

**Custom `distribution.image` is ignored when `distribution.name` is also set** (CLAUDE.md). The `LlamaStackDistribution` CR uses `distribution.image` for a custom image. Setting both `distribution.name: rh-dev` AND `distribution.image: quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` makes the operator silently ignore the image. Only one should be set — the chart picks based on `guardrails.enabled`.

**Helm chart renames vLLM model providers between charts** (CLAUDE.md). The genaiops chart names providers `vllm-<model>` (e.g. `vllm-llama32/llama32`). Our chart uses `vllm` (e.g. `vllm/llama32`). After switching charts, every UI must re-select the model in Settings; the old prefixed ID is gone.

**`networkPolicy.enabled` defaults to `false` on the playground** (components.md). An earlier version of `helm/llama-stack-playground` defaulted to `true` with egress targeting label `app.kubernetes.io/name: llama-stack` — but the llama-stack chart labels pods as `app: llama-stack`, a label mismatch that silently blocked all outbound traffic and surfaced as `APIConnectionError`. The default is now `false`; only enable it if you have verified the egress selector matches the live llama-stack pod labels.

**`vllm.modelId` is required, and the registered LLM is exposed with a `vllm/` prefix** (pitfalls.md #16). Llama Stack auto-registers the embedding model (`inline::sentence-transformers`) but **not** the vLLM-served LLM. Without `vllm.modelId`, `/v1/models` lists embeddings only and chat completions fail with `400 Bad Request: model field expected string`. After registration the LLM appears as `vllm/<modelId>` (e.g. `vllm/qwen25-7b-instruct`) — UIs and routers must use the prefixed ID.

**`tls_verify` missing in the guardrails-mode vLLM provider config** (pitfalls.md #17). vLLM behind kube-rbac-proxy on `:8443` uses self-signed serving certs. The non-guardrails config block in our chart had `tls_verify: {{ .Values.vllm.tlsVerify }}` from the start; the guardrails block was missing it for a while, causing `APIConnectionError 500` on every chat completion despite raw `curl -k` from the pod working. Verify with `oc get cm llama-stack-config -n <ns> -o jsonpath='{.data.config\.yaml}' | grep -A3 'provider_id: vllm'` — must show three keys: `url`, `api_token`, `tls_verify`.

**Inline Milvus is ephemeral** (pitfalls.md #22). `milvus.mode=inline` (the default) writes to a SQLite file at `/opt/app-root/src/.llama/distributions/rh/milvus.db` on the pod's writable layer, with no PVC. Vector stores and uploaded documents disappear on every pod restart. For persistence, deploy `helm/milvus/` and switch to `milvus.mode=remote`.

## Findings & Measurements [coverage: medium -- 1 source]

### 2026-05-09 — LiteLLM TLS chain works end-to-end (claude-mem #813)

Full `llama-stack → LiteLLM → vLLM/KServe` chain verified working on the `agentic-ivr` cluster after fixing TLS trust on LiteLLM. The fix:

- Add an `initContainer` to LiteLLM that combines the OpenShift service-CA bundle with the system CA bundle into a single PEM file and mounts it at `/etc/ssl/certs/ca-bundle.crt`.
- Set `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and `CURL_CA_BUNDLE` to that path.
- LiteLLM's main container then trusts the in-cluster `*.svc` certificates issued by the OpenShift service-CA.

Without this, LiteLLM rejected the vLLM KServe predictor's self-signed cert and `llama-stack` saw a `500 Connection error`. Direct `llama-stack → vLLM` worked because llama-stack already had `tls_verify: false` set on the vLLM provider — but routing through LiteLLM made `tls_verify: false` insufficient because the failure was now between LiteLLM and vLLM, where llama-stack has no say.

Commit: `3770ba6` ("Fix LiteMaaS SSO and trust OpenShift service-CA in LiteLLM").

### 2026-05-09 — Wiki bootstrap into `wiki/`

Legacy `llama-stack-ui/docs/` and `docs/` were merged into the Karpathy-style `wiki/` tree. Operational recipes consolidated into a single [`runbook.md`](../../wiki/runbook.md); deployment-time gotchas accumulated in [`pitfalls.md`](../../wiki/pitfalls.md). Going forward, dated empirical results land in [`findings.md`](../../wiki/findings.md), bug-with-root-cause-and-fix entries in `pitfalls.md`, and architectural choices in `decisions.md`.

### 2026-05-09 — Guardrails red-team: `language_detection` always trips on English greetings

Documented in [`guardrails-redteam-report.md`](../../wiki/guardrails-redteam-report.md). The `papluca/xlm-roberta-base-language-detection` model classifies short English greetings (`hi`, `hey, how are you`) as non-English at >0.9 confidence. With the chart default `confidence_threshold: 0.85`, every greeting is blocked. Mitigations applied at deploy time: drop the shield from `output_shields`, raise the threshold to ≥0.99 via `--set guardrails.language_detection.confidence_threshold=0.99`, or skip the shield client-side for messages under N tokens.

## Sources

- [components.md](../../wiki/components.md) — chart catalog, image tags, internal URLs, helm repo, model registration, shields
- [runbook.md](../../wiki/runbook.md) — cluster login, deploy with/without guardrails, verification curls, route timeout, in-cluster build, release flow, debug procedures
- [pitfalls.md](../../wiki/pitfalls.md) — `--reuse-values` desync (#24), operator service naming (#18), `tls_verify` (#17), `vllm.modelId` + prefix (#16), inline-vs-remote Milvus (#22), `confidence_threshold` null (#10), genaiops upload bug (#19), `remote::passthrough` vs FMS (#14), language_detection short-text (#23)
- [findings.md](../../wiki/findings.md) — 2026-05-09 LiteLLM TLS chain end-to-end, 2026-05-09 wiki bootstrap, 2026-05-09 language_detection red-team result

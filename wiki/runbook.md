# Runbook

Operational recipes — deploy, debug, build, release. Every recipe is a self-contained sequence; copy-paste should work without context.

When a recipe changes (new flag, new prerequisite, new gotcha), update it in place. Add a `# As of YYYY-MM-DD` comment at the top of the recipe so future readers can tell freshness at a glance.

---

## Cluster login

```bash
# As of 2026-05-09
source .env  # OC_USER, OC_PASSWORD, CLUSTER_DOMAIN
oc login -u $OC_USER -p $OC_PASSWORD https://api.$CLUSTER_DOMAIN:6443 --insecure-skip-tls-verify
```

## Deploy LlamaStack for RHOAI AutoRAG (vanilla cluster)

```bash
# As of 2026-07-02
# Full sequence for a clean cluster where nothing is pre-installed.
# All resources go into the same namespace as the RHOAI project selected in the dashboard.

NS=genai

# 0. Prerequisites: Milvus must be deployed first
helm upgrade --install milvus helm/milvus/ -n $NS

# 1. Deploy LlamaStack (standard mode, no guardrails)
VLLM_NS=<model-namespace>
ISVC=<isvc-name>          # e.g. granite-3-1-8b-instruct
TOKEN=$(oc get secret -n $VLLM_NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d)
VLLM_URL="https://${ISVC}-predictor.${VLLM_NS}.svc.cluster.local:8443/v1"

helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC" \
  --set milvus.mode=remote \
  --set milvus.endpoint="http://milvus:19530" \
  --set autorag.connectionSecret.enabled=true \
  --set autorag.connectionSecret.llamaStackUrl="http://llama-stack-service.${NS}.svc.cluster.local:8321"

# 2. Wait for LlamaStack to come up
oc rollout status deployment -l app=llama-stack -n $NS --timeout=5m

# 3. Get the auto-created Milvus vector store ID
VSID=$(oc exec -n $NS deploy/llama-stack -- \
  curl -s http://localhost:8321/v1/vector_stores | jq -r '.data[0].identifier')
echo "Vector store ID: $VSID"

# 4. Create gen-ai-aa-vector-stores ConfigMap (required by AutoRAG BFF)
EMBED_MODEL=ibm-granite/granite-embedding-125m-english
EMBED_DIM=768
cat <<EOF | oc apply -n $NS -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: gen-ai-aa-vector-stores
  namespace: $NS
data:
  config.yaml: |
    providers:
      vector_io:
        - provider_id: milvus
          provider_type: remote::milvus
          config:
            uri: http://milvus:19530
            custom_gen_ai:
              credentials:
                secretRefs:
                  - name: milvus-secret
                    key: root-password
    registered_resources:
      vector_stores:
        - provider_id: milvus
          vector_store_id: $VSID
          embedding_model: $EMBED_MODEL
          embedding_dimension: $EMBED_DIM
          vector_store_name: "Milvus ($NS)"
          metadata:
            description: "Milvus vector store for AutoRAG in $NS namespace"
EOF

# 5. Upload the fixed pipeline (RHOAIENG-64768)
# Requires DSPA to be deployed first (Data Science Pipelines Application CR)
DS_ROUTE=$(oc get route ds-pipeline-dspa -n $NS -o jsonpath='{.spec.host}')
curl -sk -X POST "https://$DS_ROUTE/apis/v2beta1/pipelines/upload?name=documents-rag-optimization-pipeline" \
  -H "Authorization: Bearer $(oc whoami -t)" \
  -F "uploadfile=@pipeline-fix/pipeline.yaml"
```

**Important FQDN rule:** The `autorag.connectionSecret.llamaStackUrl` MUST be a fully-qualified service name (`http://<svc>.<ns>.svc.cluster.local:<port>`). The gen-ai-ui BFF container does not inherit the target namespace in its DNS search path; short names cause HTTP 000 (silent connection failure). See [`pitfalls.md`](pitfalls.md) #29.

**AutoRAG namespace:** In the RHOAI dashboard, always select the namespace where LlamaStack is deployed before navigating to Gen AI Studio → AutoRAG. The BFF passes the active namespace to all LSD calls.

---

## Discover services on a fresh cluster

```bash
# vLLM InferenceServices
oc get inferenceservice -A

# Guardrails detectors (legacy ai501 namespace)
oc get inferenceservice -A | grep -iE "guard|hap|inject|language"

# Llama Stack and supporting services
oc get svc -A | grep -iE "vllm|llama|predictor|guard|milvus"
oc get route -A | grep -iE "vllm|llama|guard"
```

## Deploy llama-stack with guardrails

```bash
# As of 2026-05-09
NS=user1-canopy

# Source the live vLLM InferenceService details — never reuse stale values
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

**Always re-source `vllm.url`, `vllm.apiToken`, `vllm.modelId` on every upgrade.** `--reuse-values` carries forward stale values and causes `APIConnectionError` (DNS) or `404 model not found` after the InferenceService is swapped or its SA token is rotated. See [`pitfalls.md`](pitfalls.md) "Helm upgrade caveat".

**Set `confidence_threshold` explicitly** on every enabled shield. Blank renders as YAML null and breaks the provider with `'>' not supported between 'float' and 'NoneType'`. See [`components.md`](components.md) for default thresholds.

## Deploy llama-stack without guardrails

```bash
helm upgrade --install llama-stack helm/llama-stack/ -n $NS \
  --set vllm.url="$VLLM_URL" \
  --set vllm.apiToken="$TOKEN" \
  --set vllm.modelId="$ISVC"
```

## Verify llama-stack came up correctly

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

## Build llama-stack-ui image in-cluster

```bash
# As of 2026-05-09
NS=user1-canopy
oc new-build --binary --strategy=docker --name=llama-stack-ui -n $NS
oc patch bc/llama-stack-ui -n $NS --type=json \
  -p='[{"op":"add","path":"/spec/strategy/dockerStrategy/dockerfilePath","value":"Containerfile"}]'
oc start-build llama-stack-ui --from-dir=./llama-stack-ui --follow -n $NS
```

After the build finishes:

```bash
helm upgrade --install llama-stack-ui helm/llama-stack-ui/ -n $NS \
  --set ui.llamaStackUrl="http://llama-stack-service:8321" \
  --set ui.defaultModel="vllm/qwen25-7b-instruct"
```

## Run UI locally (dev)

```bash
cd llama-stack-ui
export LLAMA_STACK_API_ENDPOINT="https://llama-stack-${NS}.apps.${CLUSTER_DOMAIN}"
streamlit run app.py
# or:
./run.sh
```

## Test guardrails end-to-end

```bash
cd llama-stack-ui
./tests/test-guardrails.sh    # 18 e2e scenarios
# Edit tests/test-env.sh to point at different endpoints
```

## Test llama-stack core API

```bash
./tests/test-llamastack.sh
```

## Annotate route for long file uploads

OpenShift routes default to a 30s timeout. Embedding a large document during upload can exceed it.

```bash
oc annotate route llama-stack -n $NS \
  haproxy.router.openshift.io/timeout=300s
```

## Debug: chat completions return APIConnectionError 500

Likely causes (in order):

1. **`tls_verify` missing** in the vLLM provider config. Both guardrails and non-guardrails config blocks must have `tls_verify: false`. See [`pitfalls.md`](pitfalls.md).
2. **Stale `vllm.url`** from `--reuse-values`. Re-source from the cluster.
3. **Stale SA token.** `oc get secret -n $NS default-token-${ISVC}-sa -o jsonpath='{.data.token}' | base64 -d` and re-set.
4. **Wrong model ID.** `/v1/models` returns the registered LLM with a `vllm/` prefix. The UI must use the prefixed ID.

Confirm by curl-ing vLLM directly from the llama-stack pod:

```bash
oc exec -n $NS deployment/llama-stack -- \
  curl -k -H "Authorization: Bearer $TOKEN" "$VLLM_URL/models"
```

## Debug: shield always trips (e.g. language_detection on greetings)

Raise the threshold:

```bash
helm upgrade llama-stack helm/llama-stack/ -n $NS --reuse-values \
  --set guardrails.language_detection.confidence_threshold=0.99
```

Or drop the shield from `output_shields` in the UI Settings page. See [`findings.md`](findings.md) "language_detection always trips on English greetings".

## Debug: file upload silently fails on the upstream playground

Use `helm/llama-stack-ui` instead. The genaiops `0.3.0-fix` image has a `RAGDocument` dict-vs-object bug in `upload.py:59`. See [`architecture.md`](architecture.md) "Why a custom UI".

## Release a new helm chart version

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

## Run the wiki linter

```bash
python3 scripts/wiki_lint.py
```

Exits non-zero if any check fails. Run before commits that touch wiki content.

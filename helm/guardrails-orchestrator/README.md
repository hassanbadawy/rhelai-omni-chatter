# guardrails-orchestrator

FMS Guardrails Orchestrator with self-contained HuggingFace detector deployments. Deploys content safety detectors (HAP, prompt injection, language detection, regex) without requiring KServe, MinIO, or any external namespace.

## Architecture

Each detector with `type: huggingface` automatically deploys:

1. **initContainer** — downloads the HuggingFace model via `snapshot_download()` into an `emptyDir` volume at `/mnt/models`
2. **Main container** — `quay.io/trustyai/guardrails-detector-huggingface-runtime` runtime, loads from `MODEL_DIR=/mnt/models`, exposes `POST /api/v1/text/contents` on port 8000
3. **Service** — in-namespace ClusterIP service so the orchestrator can reach the detector

Models are pulled fresh from HuggingFace on every pod restart (~1-2 min). For air-gapped clusters, see "Disconnected installs" below.

## Quick install

```bash
helm install guardrails-orchestrator helm/guardrails-orchestrator/ -n <ns>
```

Default values deploy:

| Detector | HuggingFace model | Memory (init / runtime) |
|---|---|---|
| `hap` | `ibm-granite/granite-guardian-hap-125m` | 2Gi / 2Gi |
| `prompt_injection` | `protectai/deberta-v3-base-prompt-injection-v2` | 2Gi / 2Gi |
| `language_detection` | `papluca/xlm-roberta-base-language-detection` | 4Gi / 2Gi |
| `regex_competitor` | Built-in sidecar (no model) | — |

## Adding a new detector

Just add an entry to `detectors:` in `values.yaml`:

```yaml
detectors:
  my_detector:
    enabled: true
    type: huggingface
    modelId: "org/model-name"      # HuggingFace model ID
    hostname: "my-detector"        # service name (use dashes, not underscores)
    port: 8000
    threshold: 0.5
    input: true
    output: true
    params: {}
```

For gated/private models:

```yaml
detectorDefaults:
  hfToken: "hf_xxx"   # global, applied to all detectors

# OR per-detector:
detectors:
  my_detector:
    hfToken: "hf_xxx"   # overrides global
```

The token is stored in a `guardrails-hf-token` Secret, not as plaintext env vars.

## Image pull requirements

| Image | Source |
|---|---|
| Orchestrator | `registry.redhat.io/rhoai/odh-fms-guardrails-orchestrator-rhel9` |
| Gateway sidecar | `registry.redhat.io/rhoai/odh-trustyai-vllm-orchestrator-gateway-rhel9` |
| Regex detector | `registry.redhat.io/rhoai/odh-built-in-detector-rhel9` |
| HF detector runtime | `quay.io/trustyai/guardrails-detector-huggingface-runtime` |

`registry.redhat.io` requires a pull secret with active Red Hat credentials. On RHOAI clusters, this is usually pre-configured cluster-wide.

If your cluster cannot pull from these registries, set `imagePullSecrets:` and override the image fields:

```yaml
imagePullSecrets:
  - name: my-pull-secret

images:
  orchestrator: "my-registry.example.com/odh-fms-guardrails-orchestrator-rhel9:..."
  gateway: "my-registry.example.com/odh-trustyai-vllm-orchestrator-gateway-rhel9:..."
  regexDetector: "my-registry.example.com/odh-built-in-detector-rhel9:..."

detectorDefaults:
  image: "my-registry.example.com/guardrails-detector-huggingface-runtime:latest"
```

## Network requirements

The detector initContainers need outbound access to **`huggingface.co`** to download models on every pod start. If the cluster has an egress proxy, configure it via:

```yaml
detectorDefaults:
  proxy:
    httpsProxy: "http://proxy.corp:3128"
    httpProxy: "http://proxy.corp:3128"
    noProxy: ".svc,.cluster.local,localhost,127.0.0.1"
```

## Disconnected installs

For air-gapped clusters that can't reach `huggingface.co`:

1. Pre-download each model on a connected machine and push to your own object store (MinIO, S3, etc.)
2. Replace the initContainer command with one that pulls from your object store instead of HuggingFace
3. Or: bake the model files into a custom image and override `detectorDefaults.image` to use that

The `huggingface_hub` library used in the initContainer also supports `HF_ENDPOINT` env var for a private HuggingFace mirror.

## Critical pitfalls

### `chunker.hostname` must be empty (or a real running chunker service)

```yaml
chunker:
  hostname: ""   # default — DO NOT set to namespace name or anything else
```

Setting `chunker.hostname` to a non-service value causes the orchestrator to crash on startup with `invalid config file: chunkers.sentence: missing field 'service'`.

### Detector hostnames must use dashes, not underscores

Kubernetes service names cannot contain underscores. The chart auto-converts the detector key (e.g. `prompt_injection` → `prompt-injection-detector`), but if you override `hostname:` directly, use dashes.

## Verifying the install

```bash
# All pods should be 1/1 Running
oc get pods -n <ns> | grep -E "detector|orchestrator"

# Test from inside the orchestrator
oc exec -n <ns> deploy/guardrails-orchestrator -c guardrails-orchestrator -- \
  curl -sk -X POST https://localhost:8032/api/v2/text/detection/content \
  -H "Content-Type: application/json" \
  -d '{"detectors":{"hap":{}},"content":"hello world"}'
```

A clean response means the orchestrator can reach the detector. A `client error (Connect)` means the detector pod isn't reachable — check service names and detector pod status.

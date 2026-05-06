# Future Work

Ideas explored in conversation but not yet implemented. Each entry: what it is, why we'd consider it, what it would cost, and a concrete first step. Trim entries that no longer apply.

---

## GitOps via ArgoCD (`alpha-hack-program/llm-d-guide` pattern)

**What:** Replace ad-hoc `helm install` / `helm upgrade --reuse-values` with an ArgoCD ApplicationSet that reconciles all our charts (`llama-stack`, `guardrails-orchestrator`, `llama-stack-ui`, `llama-stack-playground`, `milvus`, etc.) from git.

**Why:** Several recurring pain points map directly to "no GitOps":
- `--reuse-values` carries forward stale `vllm.url` / `vllm.apiToken` / `vllm.modelId` across upgrades (pitfall 24)
- Manual `oc set env` and `helm upgrade` drift between sessions; no audit trail
- Install order (cert-manager → KServe → Llama Stack operator → llama-stack chart → playground/UI) lives only in CLAUDE.md, not in code
- A new user cannot reproduce the cluster state from this repo alone

GitOps fixes all of those: cluster state lives in git, drift is detected and reverted, install order is encoded in Application sync waves.

**Reference:** `https://github.com/alpha-hack-program/llm-d-guide` — its `gitops/` directory is a working ArgoCD ApplicationSet for the RHOAI dependency stack (cert-manager, KServe, ArgoCD itself, optionally Llama Stack Operator). Borrow the shape; point it at our `helm/` charts.

**First step (when revisited):** Copy the ArgoCD bootstrap from their `gitops/` directory into a new top-level `gitops/` here, and add Applications for two or three of our charts (e.g. `llama-stack`, `guardrails-orchestrator`, `llama-stack-ui`). Validate that an `argocd app sync` reproduces the cluster state we currently set up by hand.

**Trade-offs:**
- Requires ArgoCD installed in the cluster (`oc apply -k argocd/`) — adds a dependency
- Helm value overrides have to be expressed as `values:` blocks in the Application spec rather than `--set` flags. Cluster-truth values like the SA token still need to come from a sealed-secret or external-secrets operator, not from git directly
- The current `helm upgrade --reuse-values` workflow becomes `git commit + argocd sync`, which is slower for one-off testing but safer for production

---

## Bootstrap script for fresh-cluster prereqs

**What:** A `bootstrap/install-prereqs.sh` (adapted from `alpha-hack-program/llm-d-guide`'s `scripts/`) that takes a fresh OpenShift cluster and installs cert-manager, KServe, the Llama Stack operator, and any other dependencies our helm charts assume to be present.

**Why:** Today the README and `CLAUDE.md` assume someone has already deployed RHOAI, KServe, and the Llama Stack operator. A new user cannot run our helm charts on a fresh cluster without copy-pasting from external docs. This is the cheapest reproducibility win — independent of whether we adopt GitOps.

**First step (when revisited):** Add a top-level `bootstrap/` directory with a single shell script that issues the right `oc apply` / `helm install` commands for the prereqs, in the right order, with idempotent retries. Reference the llm-d-guide scripts for the exact resource manifests; do not vendor their files unless their license permits.

**Trade-offs:**
- Easy to write but easy to bit-rot — every RHOAI release shifts CRDs and operator versions. Pin to specific operator versions in the script
- Strictly less powerful than GitOps reconciliation; useful as a one-shot for demos and dev clusters

---

## Migrate to `llm-d` for distributed inference (only when a single GPU is no longer enough)

**What:** Replace single-node KServe `InferenceService` resources with llm-d `LLMInferenceService` resources for any model that exceeds a single GPU. llm-d adds disaggregated prefill/decode, KV-cache-aware routing, and multi-node tensor parallelism.

**Why:** Pure capacity. Today our largest model is `gpt-oss-20b` (a 20B-MoE that fits on one GPU). If we ever need to serve a 70B+ dense model, or push much higher concurrent load on the same hardware, llm-d is the path forward. It went GA in RHOAI 3.3 and is the strategic direction for distributed inference on OpenShift.

**Why not now:**
- All current models fit comfortably on a single GPU. The benchmark numbers (model-benchmarks.md) show neither qwen25-7b nor gpt-oss-20b is GPU-bound at our current load.
- llm-d uses a different CRD (`LLMInferenceService` ≠ `InferenceService`). Llama Stack consumes vLLM endpoints by URL + SA token, so the application side wouldn't change much, but the deployment pattern (KServe ServingRuntime + ModelCar) would.
- Requires RHOAI 3.3+ in the cluster.

**First step (when revisited):** Verify the cluster is on RHOAI 3.3, deploy llm-d via the alpha-hack-program guide, and stand up one of our existing models (e.g. `qwen25-7b-instruct`) as a `LLMInferenceService` alongside the existing `InferenceService`. Compare TTFT and throughput before considering the migration. Keep both endpoints registered in Llama Stack during the transition.

**Trade-offs:**
- Higher operational complexity (gateway, prefill/decode pods, cache routing) for benefits that only show up at scale
- Different model packaging (ModelCar OCI images vs the current `storageUri: oci://...modelcar-...` pattern may or may not be compatible — verify before committing)

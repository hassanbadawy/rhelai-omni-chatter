---
concept: Helm-upgrade staleness from --reuse-values
last_compiled: 2026-05-09
topics_connected: [llama-stack-platform, models-and-inference, deployment-and-ops]
status: active
---

# Helm-upgrade staleness from `--reuse-values`

## Pattern

`helm upgrade --reuse-values` is the obvious shortcut for "I want to change one thing without re-typing everything." In this project's chart, it's the single most reliable way to break a working deployment — because the values that *should* be re-sourced from the cluster on every upgrade get silently carried forward stale. The failure mode looks like a Llama Stack regression, but the root cause is always upstream of Llama Stack itself: a vLLM SA token rotated, an InferenceService renamed, a model swapped in the cluster.

The values in question are tightly coupled to *the live cluster state* at the moment of the previous install: `vllm.url` (DNS that may have changed), `vllm.apiToken` (SA token that may have rotated), `vllm.modelId` (the model name in vLLM, which may have been swapped). None of these can be safely reused; all of them must be re-sourced before every upgrade.

## Instances

- **2026-04 in [llama-stack-platform](../topics/llama-stack-platform.md):** Decision recorded that `--reuse-values` carries forward `vllm.url`/`vllm.apiToken`/`vllm.modelId`. When the running InferenceService is swapped (model change) or its SA token is rotated, the reused values go stale and cause `APIConnectionError` (DNS) or `404 model not found`.
- **2026-04 in [models-and-inference](../topics/models-and-inference.md):** Pitfall log says `vllm.modelId` is required (auto-registers the LLM and exposes it with `vllm/` prefix). When stale from `--reuse-values`, `/v1/models` returns embeddings only, and chat completions fail with `400 Bad Request: model field expected string`.
- **2026-04 in [deployment-and-ops](../topics/deployment-and-ops.md):** Operational recipe is: always re-source `vllm.url`, `vllm.apiToken`, `vllm.modelId` from the live cluster on every upgrade. The runbook codes this as a 3-line shell preamble before any `helm upgrade`.

## What this means

This is a **systemic interaction between helm's caching model and OpenShift's live state**, not a bug in the chart or in helm. Helm correctly assumes `--reuse-values` is what the user wants; OpenShift correctly rotates SA tokens and renames InferenceServices on its own cadence. The mismatch is at the seam.

The right response is operational discipline, not a technical fix:

1. **Treat `--reuse-values` as "scoped to chart-internal values only."** Anything that came from the cluster (URL, token, modelId) must be re-sourced. The runbook's 3-line preamble is the canonical pattern; don't bypass it.
2. **Codify the pattern in CI/automation.** If/when GitOps (ArgoCD) lands, the values file should be regenerated from cluster state before each sync. This concept is the single biggest argument for moving deploys to GitOps — it removes the human in the `--reuse-values` loop.
3. **Error messages should be triaged with this pattern in mind.** When a chat completion suddenly returns `APIConnectionError` or `404 model not found` after a helm upgrade, check `helm get values <release>` and compare against `oc get inferenceservice` first. The error rarely comes from Llama Stack itself.

## Sources

- [llama-stack-platform](../topics/llama-stack-platform.md)
- [models-and-inference](../topics/models-and-inference.md)
- [deployment-and-ops](../topics/deployment-and-ops.md)

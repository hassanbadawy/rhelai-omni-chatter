---
concept: Wrapping upstream where it's broken
last_compiled: 2026-05-09
topics_connected: [streamlit-playground-ui, llama-stack-platform, rag-and-vector-store, guardrails-and-safety, deployment-and-ops]
status: active
---

# Wrapping upstream where it's broken

## Pattern

Across multiple components, this project has a recurring response to upstream defects: rather than patch upstream and wait, fork or wrap into a chart we control. The fork is *minimal* — the diff against upstream is small, focused, and documented in the wiki — but it lives in our chart catalog as a first-class deliverable. We don't pretend the upstream version works.

The rule of thumb is: **if upstream's bug blocks deployment in the OpenShift web console (the user's stated UX requirement), we wrap it.** If it's a behavioral preference, we configure it. The bar for wrapping is "this fails for a customer at install time."

## Instances

- **2026-04 in [streamlit-playground-ui](../topics/streamlit-playground-ui.md):** The genaiops `llama-stack-playground:0.3.0-fix` image has two blocking bugs: file upload crashes (`AttributeError: 'dict' object has no attribute 'content'` in `upload.py:59` — SDK 0.3.0 returns `RAGDocument` as a dict but the code uses attribute access), and default chat mode is "Direct" which bypasses safety shields entirely. Response: built our own custom UI in `llama-stack-ui/` and shipped it as `helm/llama-stack-ui`. Both bugs fixed; plus added context-length probing and SSE-error detection.
- **2026-04 in [llama-stack-platform](../topics/llama-stack-platform.md):** Upstream Llama Stack has no provider that speaks the IBM/FMS detector API. `remote::passthrough` was the closest candidate but calls `/moderations` (OpenAI format) — incompatible. Response: use the custom image `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3` which adds `remote::trusty_fms`. Live with the schema fork (see [`two-image-schema-fork`](./two-image-schema-fork.md)).
- **2026-04 in [rag-and-vector-store](../topics/rag-and-vector-store.md):** The genaiops chart gates `remote::milvus` provider inclusion on the namespace name containing "test" or "prod". Any other namespace silently falls back to inline Milvus → data lost on pod restart. Response: our chart replaces the namespace conditional with a simple `milvus.mode` value (`inline` | `remote`). Works in any namespace.
- **2026-04 in [guardrails-and-safety](../topics/guardrails-and-safety.md):** Earlier guardrails-orchestrator chart referenced detectors deployed in a separate `ai501` namespace — non-self-contained, unfit for OpenShift web-console install. Response: chart v0.2.0+ inlines the detectors as `Deployment`+`Service` pairs in the same namespace, with `initContainer`s that download HuggingFace models into `emptyDir` at `/mnt/models`.
- **2026-04 in [deployment-and-ops](../topics/deployment-and-ops.md):** Operationally, this means the chart catalog has a "wrapped" twin for almost every upstream component — and the wrapping is the supported path. We don't recommend customers install upstream charts directly.

## What this means

**The wiki's value compounds at the wrap boundary.** Every wrap is a place where a future contributor will reach for an upstream pattern, find it missing, and need to know why. The wiki entries that explain *why we forked* are higher-leverage than the entries that document our forked behavior — because the fork-rationale prevents the most common mistake: someone trying to "simplify" by going back to upstream and silently regressing.

Three operational consequences:

1. **Versioning matters.** When upstream releases a new genaiops chart or RHOAI vLLM image, our wraps may become unnecessary. Track upstream release notes per component (the prefix `quay.io/rhoai-genaiops/` is the signal). When a wrap can be retired, retire it; don't carry dead wraps.
2. **Customer-facing docs should mention the wrap.** Customers who try to install upstream and hit one of these bugs need to be redirected to our chart, not left to debug. The component-level chart README should make this explicit.
3. **The cost of wrapping is the long tail of upstream drift.** Six months from now, our `llama-stack-ui` may be 2 versions behind upstream's playground. Schedule a quarterly diff-and-review against upstream for each wrap.

## Sources

- [streamlit-playground-ui](../topics/streamlit-playground-ui.md)
- [llama-stack-platform](../topics/llama-stack-platform.md)
- [rag-and-vector-store](../topics/rag-and-vector-store.md)
- [guardrails-and-safety](../topics/guardrails-and-safety.md)
- [deployment-and-ops](../topics/deployment-and-ops.md)
- [two-image-schema-fork](./two-image-schema-fork.md)

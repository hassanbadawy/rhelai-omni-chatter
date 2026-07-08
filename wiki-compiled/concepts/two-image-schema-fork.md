---
concept: Two-image schema fork
last_compiled: 2026-05-09
topics_connected: [llama-stack-platform, guardrails-and-safety, rag-and-vector-store, deployment-and-ops]
status: active
---

# Two-image schema fork

## Pattern

The Llama Stack chart in this project ships **two completely different config schemas** depending on whether guardrails are enabled. The trigger is the helm value `guardrails.enabled`, but the cascade goes much deeper than a feature toggle: it switches the container image, the safety provider, the kvstore format, the vLLM config key, and the set of available shields. Mixing fields from one schema into the other causes immediate `ValidationError` at startup.

The fork exists because the safety provider that speaks the IBM/FMS Guardrails Orchestrator API (`remote::trusty_fms`) is not in upstream Llama Stack — it lives only in the custom image `quay.io/rhoai-genaiops/llama-stack-vllm-milvus-fms:rhoai-3.0-fix3`. Picking that image forces the rest of the schema to follow because the custom image's config parser is stricter than the rh-dev image.

## Instances

- **2026-04 in [llama-stack-platform](../topics/llama-stack-platform.md):** Decision recorded that the chart has two complete config blocks, selected at template-render time by `guardrails.enabled`. `metadata_store` + `storage.{backends,stores}` (rh-dev) vs `type: sqlite, db_path: ...` (FMS). vLLM key is `base_url` in one, `url` in the other.
- **2026-04 in [guardrails-and-safety](../topics/guardrails-and-safety.md):** Confirmed that `remote::trusty_fms` is the only viable safety provider for FMS detectors — `remote::passthrough` calls `/moderations`, IBM detectors expect `/api/v1/text/contents`. Switching to upstream image without changing the safety provider yields `Provider 'remote::trusty_fms' is not available for API 'Api.safety'`.
- **2026-04 in [rag-and-vector-store](../topics/rag-and-vector-store.md):** Provider config differs by image — `remote::milvus` vs `inline::milvus` selection runs through the same conditional. The chart's `milvus.mode` value sits on top of the image fork.
- **2026-04 in [deployment-and-ops](../topics/deployment-and-ops.md):** Operationally, every helm upgrade has to know which mode it's in — the upgrade command differs (different `--set` flags, different fields to source from cluster).

## What this means

**The fork is not optional and not soon-removable.** It exists because the custom FMS image is the only path to the IBM detector ecosystem and the upstream Llama Stack hasn't absorbed `remote::trusty_fms` yet. Anyone touching the helm chart, writing a deploy recipe, or debugging a startup failure must first answer: which image is this?

Three implications for future work:

1. **Migration from rh-dev to FMS (or vice versa) is not a single helm upgrade.** It's a rewrite of the values file. Plan it as such.
2. **Documentation must always specify which mode** when quoting config snippets. A YAML stanza shown without its mode is ambiguous and likely wrong in one of the two contexts.
3. **If/when upstream Llama Stack absorbs an FMS-compatible safety provider** (or `remote::trusty_fms` itself), the fork can collapse. Watch upstream for this — it would be the single biggest simplification available to the chart.

## Sources

- [llama-stack-platform](../topics/llama-stack-platform.md)
- [guardrails-and-safety](../topics/guardrails-and-safety.md)
- [rag-and-vector-store](../topics/rag-and-vector-store.md)
- [deployment-and-ops](../topics/deployment-and-ops.md)

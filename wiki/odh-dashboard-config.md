# RHOAI Dashboard Configuration (`OdhDashboardConfig`)

How to turn RHOAI dashboard features on without silently misconfiguring them.
Recorded against **RHOAI 3.5.0**; the field set is version-specific, so always
re-derive it from the cluster rather than copying a list.

Related: [pitfall #30](pitfalls.md) — unknown fields are pruned, not rejected.

---

## The one rule: validate against the live CRD, not the docs

The [docs page](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard)
lags the shipped CRD and its true/false wording is ambiguous. The cluster is
authoritative and carries per-field descriptions and deprecation notes:

```bash
# every field under spec.dashboardConfig
oc get crd odhdashboardconfigs.opendatahub.io \
  -o jsonpath='{.spec.versions[0].schema.openAPIV3Schema.properties.spec.properties.dashboardConfig.properties}' \
  | python3 -c 'import json,sys; [print(k) for k in sorted(json.load(sys.stdin))]'

# what a specific field actually does
oc get crd odhdashboardconfigs.opendatahub.io -o json | python3 -c "
import json,sys
p=json.load(sys.stdin)['spec']['versions'][0]['schema']['openAPIV3Schema']['properties']['spec']['properties']['dashboardConfig']['properties']
for k in ['gpuaas','guardrails','mlflow']: print(k,'->',p[k].get('description'))
"
```

RHOAI 3.5.0 has **67** fields under `spec.dashboardConfig` and these top-level
`spec` sections:

```
dashboardConfig       genAiStudioConfig     globalMLflowNamespaces
groupsConfig          hardwareProfileOrder  modelServerSizes
modelServing          notebookController    notebookSizes
templateDisablement   templateOrder
```

## True/false semantics

| Field shape | `true` means | Examples |
|---|---|---|
| `disableX` | feature **off** | `disableKServe`, `disableModelRegistry` |
| plain feature flag | feature **on** | `gpuaas`, `guardrails`, `genAiStudio`, `toolCalling` |

Mixing these up inverts your intent. A config that reads `disableKServe: false`
alongside `gpuaas: true` is correct — both enable.

## Three traps

1. **Case sensitivity.** Field names are lowercase. `Gpuaas`, `Guardrails`, `Mlflow`
   are all silently pruned.
2. **Dots are not paths in YAML.** `aiAssetCustomEndpoints.externalProviders: true`
   creates a single literal key containing a dot — not a nested field.
3. **`aiAssetCustomEndpoints` exists twice, with different types.**

   | Path | Type | Purpose |
   |---|---|---|
   | `spec.dashboardConfig.aiAssetCustomEndpoints` | boolean | turn the feature on |
   | `spec.genAiStudioConfig.aiAssetCustomEndpoints` | object | configure it (`externalProviders`, `clusterDomains`) |

   Both are needed. The boolean alone does not enable external LLM providers.

## Correct shape

```yaml
spec:
  dashboardConfig:
    disableKServe: false          # disable* -> false = feature ON
    gpuaas: true                  # plain flag -> true = feature ON
    guardrails: true
    genAiStudio: true
    aiAssetCustomEndpoints: true  # boolean: enable the feature
  genAiStudioConfig:              # separate top-level section
    aiAssetCustomEndpoints:       # object: configure the feature
      externalProviders: true     # allow OpenAI / Gemini / Anthropic etc.
      clusterDomains: ["cluster.local"]   # optional: in-cluster vs external
```

## Verify after applying — a clean apply proves nothing

Unknown fields are **pruned**, so the apply succeeds and the feature stays off.
Any `violates policy 299 - "unknown field ..."` warning is a hard failure. Read
the value back; empty means pruned:

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.gpuaas}{"\n"}'
```

## Deprecations seen in 3.5.0

- **`mlflow`** — *"MLflow is now always enabled when the operator component is
  present. This field will be removed in a future version."* Drop the field. For a
  shared workspace use the top-level `globalMLflowNamespaces` list (max 1 namespace).

## Note on `gpuaas`

`gpuaas: true` enables the GPUaaS Infrastructure page for cluster capacity and
accelerator utilization. It renders empty until GPU nodes actually exist — see
[gpu-nodes.md](gpu-nodes.md), and note MIG needs P-family instances.

# RHOAI Models-as-a-Service (MaaS) — install state and blocker

Status of the MaaS install on `cluster-sznd8` (RHOAI **3.5.0**), as of **2026-09-12**.

**Bottom line: MaaS cannot be enabled on RHOAI 3.5.0.** Both enablement paths are
closed — see [pitfall #31](pitfalls.md). Everything *else* the docs require is done,
so a cluster with a build that ships the AI Gateway component would finish quickly.

---

## Check this first

One command decides whether MaaS is even possible on a given cluster:

```bash
oc get crd aigateways.components.platform.opendatahub.io
```

`NotFound` → stop. No DSC setting will deploy `maas-api`.

## Why it is blocked

| Path | Doc version | Result on 3.5.0 |
|---|---|---|
| `kserve.modelsAsService` | 3.3 / 3.4 | CEL-blocked: *"cannot re-enable once Removed"* |
| `aigateway.modelsAsAService` | 3.5 (page 404s) | `AIGateway` CRD not in the 3.5.0 bundle |

An upgraded-from-3.4 cluster that already had `kserve.modelsAsService: Managed` keeps
working — the CEL rule only blocks `Removed→Managed`. Fresh 3.5.0 installs cannot.

## Prerequisite checklist (verified 2026-09-12)

| Requirement | State |
|---|---|
| GatewayClass `openshift-default` | ✅ Accepted |
| Gateway `maas-default-gateway` (openshift-ingress) | ✅ Programmed, ELB-backed |
| — annotations `opendatahub.io/managed=false`, `security.opendatahub.io/authorino-tls-bootstrap=true` | ✅ both |
| PostgreSQL + `maas-db-config` secret (both namespaces) | ✅ |
| User Workload Monitoring | ✅ enabled |
| Dashboard `modelAsService`, `genAiStudio`, `observabilityDashboard` | ✅ true |
| Dashboard `maasAuthPolicies` | ❌ deprecated, patch rejected |
| RHCL operator in `openshift-operators` | ⚠️ 1.4.3 (docs pin 1.3.x) |
| Kuadrant CR in `kuadrant-system` Ready | ❌ never reconciled |
| `maas.opendatahub.io` CRDs | ❌ 0 |
| `maas-api` deployment | ❌ absent |

## Two known-bad bits of state on this cluster

**Duplicate Kuadrant CRs.** `kuadrant-system/kuadrant` (created 2026-09-10T06:57:34Z)
has *no status at all* — the operator never reconciled it — because
`openshift-operators/kuadrant-sample` is `Ready` and Kuadrant behaves as a singleton.
The `-sample` name suggests it came from the OLM `alm-examples` "Create instance"
button. The docs want the CR in `kuadrant-system`.

Consequence: `authorino` lives in `openshift-operators`, but the
`authorino-server-cert` secret is in `kuadrant-system` — so the community setup script
fails at *"Patching Authorino CR for TLS"* with `authorinos... "authorino" not found`.

Fixing this means deleting the working Kuadrant and letting `kuadrant-system` take
over — a live auth stack disturbed for zero gain while MaaS cannot deploy. Deferred
deliberately.

## The community setup script

`https://github.com/rh-aiservices-bu/rhoai-maas-guide` → `./scripts/setup-maas.sh`

Useful (`--dry-run`, `--from-phase N`, `--skip-models`) and it did create the Gateway
and PostgreSQL correctly. Two cautions:

- **It exits 0 even when it fails.** Output is piped without `pipefail`, so a failed
  run looks successful. Always read the log, don't trust the exit code.
- It assumes Kuadrant/Authorino in `kuadrant-system`, which does not match a
  cluster where RHCL was installed cluster-scoped into `openshift-operators`.

## What to do instead

- Provision a **3.4** cluster (kserve path still permitted), or wait for a build that
  ships `AIGateway`; then the checklist above is already satisfied.
- Or use **LiteMaaS** — a separate LiteLLM-based product with a chart at
  [`helm/litemaas/`](../helm/litemaas/). `litemaas-postgresql` already runs in the
  `genai` namespace. Unrelated to RHOAI MaaS; different schema, different API.

## References

- [Deploy and manage MaaS — RHOAI 3.4](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service_maas)
- [Use MaaS — RHOAI 3.3](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas)
- [Introducing MaaS in OpenShift AI](https://developers.redhat.com/articles/2025/11/25/introducing-models-service-openshift-ai)

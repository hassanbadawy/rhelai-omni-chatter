# NeMo Guardrails on RHOAI 3.5

Working install, verified on `cluster-sznd8` (RHOAI 3.5.0) on **2026-09-12**.
Manifests: [`k8s/nemo-guardrails/nemo-guardrails.yaml`](../k8s/nemo-guardrails/nemo-guardrails.yaml).

**RHOAI 3.5 has moved to NeMo Guardrails.** The
[3.5 guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/enabling_ai_safety_with_guardrails/index)
states Red Hat is consolidating on NeMo and tracks *"FMS Guardrails to NeMo Guardrails
capability gaps"*. The FMS orchestrator + `remote::trusty_fms` architecture in the root
`CLAUDE.md` still works and is still shipped, but it is now the **legacy** path.

| | NeMo Guardrails (3.5 current) | FMS Orchestrator (legacy) |
|---|---|---|
| CR | `NemoGuardrails` | `GuardrailsOrchestrator` |
| Config | ConfigMaps (`config.yaml` + Colang) | ConfigMap + detector InferenceServices |
| Detectors | built-in rails (PII, sensitive data) | separate HAP / injection / language models |
| Extra GPUs | **none** — reuses the served model | one per detector model |
| Our assets | `k8s/nemo-guardrails/` | `helm/guardrails-orchestrator/`, 18 e2e tests |

Both CRDs exist on 3.5, so either can be deployed.

---

## Prerequisites

- `trustyai` component `Managed` in the DSC → `TrustyAIReady=True`
- A **working** served model. Guardrails front an existing model; they do not serve one.
  Two traps to clear first: [pitfall #33](pitfalls.md) (context vs KV cache) and
  [#34](pitfalls.md) (missing KServe ingress Gateway).
- Dashboard flag `guardrails: true` (see [odh-dashboard-config.md](odh-dashboard-config.md))

## The four objects

1. **CA bundle ConfigMap.** The model serves **HTTPS** with a KServe cert issued by
   `openshift-service-serving-signer`, so NeMo must trust the OpenShift service CA.
   Annotate an empty ConfigMap and OpenShift injects `service-ca.crt`; reference it via
   `caBundleConfig`. Never hardcode a cert — this survives rotation.
   ```yaml
   metadata:
     annotations:
       service.beta.openshift.io/inject-cabundle: "true"
   ```
   Confirm the CA actually validates the endpoint before wiring it:
   ```bash
   oc exec -n <ns> <model-pod> -c main -- curl -s \
     --cacert /var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt \
     https://<model-svc>.<ns>.svc:8000/v1/models -o /dev/null -w '%{http_code}\n'
   ```

2. **API-key Secret.** `config.yaml` requires `api_key_env_var` even when the model has
   no auth annotation (vLLM then ignores `Authorization`). A placeholder keeps enabling
   auth later a one-line change.

3. **Config ConfigMap** — `config.yaml` plus `rails.co`. All files land in
   `/app/config/$Name`. `base_url` must be the **in-cluster** model service, not the
   external route:
   ```yaml
   models:
     - type: main
       engine: openai
       model: "<served-model-name>"
       api_key_env_var: "MODEL_API_KEY"
       parameters:
         base_url: "https://<model>-kserve-workload-svc.<ns>.svc:8000/v1"
   rails:
     config:
       sensitive_data_detection:
         input:  {entities: [EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN, PERSON]}
         output: {entities: [EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN]}
     input:  {flows: [detect sensitive data on input]}
     output: {flows: [detect sensitive data on output]}
   ```

4. **`NemoGuardrails` CR.** Live v1alpha1 spec is small: `nemoConfigs`, `env`, `replicas`,
   `template`, `caBundleConfig`. Mark one `nemoConfigs` entry `default: true`.

## Verify

**Use the fully-qualified name** — `oc get nemoguardrails` silently returns NVIDIA's CRD
instead ([pitfall #35](pitfalls.md)):
```bash
oc get nemoguardrails.trustyai.opendatahub.io -n <ns>      # phase: Ready
```

Measured results on this cluster:

| Prompt | Result |
|---|---|
| "What is the capital of France?" | passes through → *"…the capital of France is **Paris**"* |
| "Email me at john.doe@example.com and call 555-123-4567" | **blocked** → *"I don't know the answer to that."* |
| "My social security number is 123-45-6789" | **blocked** |

```bash
POD=$(oc get pods -n <ns> --no-headers | grep nemo-simple | awk '{print $1}')
oc exec -n <ns> $POD -- curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<served-model-name>","messages":[{"role":"user","content":"..."}]}'
```

NeMo listens on **HTTP :8000** inside the pod and is exposed by an operator-created
Service (:80) and edge-terminated Route. It needs **no GPU** — PII detection is CPU-only.

## Gotchas

- Blocked prompts return a normal `200` with the refusal as content, not an error code.
  Assert on the message text, not the status.
- `base_url` must point at the in-cluster service; the external route adds auth redirects.
- The model needs no auth annotation for this to work. If you add one, swap the
  placeholder secret for a real service-account token.

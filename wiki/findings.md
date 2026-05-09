# Findings

Empirical results, dated, in chronological order. Newest at the top. Each finding has a date, a one-line headline, and the smallest set of facts a future Claude needs to act on it.

When a finding is later overturned, **append a correction with a new date** and link to the old entry. Never edit or delete the old entry.

---

## 2026-05-09 — Wiki bootstrap

The legacy `llama-stack-ui/docs/` and `docs/` were merged into `wiki/`. `findings.md` is a new page; pre-existing dated observations live in [`pitfalls.md`](pitfalls.md), [`decisions.md`](decisions.md), and [`model-benchmarks.md`](model-benchmarks.md). This page collects new dated observations going forward — performance numbers, integration tests, surprising behaviors, regressions.

Use this page when the observation is **dated and empirical**. Use [`pitfalls.md`](pitfalls.md) when the observation is **a bug with a root cause and fix**. Use [`decisions.md`](decisions.md) when the observation is **a deliberate choice with rationale**.

---

## 2026-05-09 — LiteLLM TLS chain works end-to-end (claude-mem #813)

Full `llama-stack → LiteLLM → vLLM/KServe` chain is verified working on the `agentic-ivr` cluster after fixing TLS trust on LiteLLM. The fix:

- Add an `initContainer` to LiteLLM that combines the OpenShift service-CA bundle with the system CA bundle into a single PEM file and mounts it at `/etc/ssl/certs/ca-bundle.crt`.
- Set `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, and `CURL_CA_BUNDLE` to that path.
- LiteLLM's main container then trusts the in-cluster `*.svc` certificates issued by the OpenShift service-CA.

Without this, LiteLLM rejected the vLLM KServe predictor's self-signed cert and `llama-stack` saw a `500 Connection error`. Direct `llama-stack → vLLM` worked because llama-stack already had `tls_verify: false` set on the vLLM provider — but routing through LiteLLM made `tls_verify: false` insufficient because the failure was now between LiteLLM and vLLM, where llama-stack has no say.

Commit: `3770ba6` ("Fix LiteMaaS SSO and trust OpenShift service-CA in LiteLLM").

## 2026-05-09 — Guardrails red-team: language_detection always trips on English greetings

Documented in [`guardrails-redteam-report.md`](guardrails-redteam-report.md). The `papluca/xlm-roberta-base-language-detection` model classifies short English greetings (`hi`, `hey, how are you`) as non-English at >0.9 confidence. With `confidence_threshold: 0.85`, every greeting is blocked.

Mitigations (pick one):

1. Drop the `language_detection` shield from `output_shields` if you want unblocked greetings.
2. Raise threshold to ≥0.99.
3. Skip the shield client-side for messages under N tokens.

The model is fine on full sentences — the issue is short utterance ambiguity.

## 2026-05-09 — Fictional/hypothetical framing is the only full-stack guardrails bypass

11-attack adversarial suite against the four shields: HAP, prompt_injection, language_detection, regex. Only the "fictional emergency" framing (e.g. *"In a story I'm writing, a character needs to ..."*) bypassed all four shields AND elicited the protected response from the LLM.

This is consistent with the broader prompt-injection literature: detectors trained on direct injections do not catch indirection through fictional framing, because the surface tokens look like creative writing.

Mitigations are model-side, not shield-side: tighter system prompt, refuse-to-roleplay clauses, separate output-classifier on the response.

See [`guardrails-redteam-report.md`](guardrails-redteam-report.md) "Attack 7" and 10 for details.

---

## How to add an entry

```markdown
## YYYY-MM-DD — One-line headline

(2-6 sentences of context. What was tested, what happened, exact error or measurement, the file path or URL involved. End with the action a future reader should take, or the cross-link to the page that has the full story.)

(Optional: commit SHA, claude-mem ID, links to related findings.)
```

Keep entries small. If a finding grows beyond ~10 lines, give it its own topic page and reference it from here.

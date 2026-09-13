# Wiki log

Append-only chronological record of every wiki operation. Newest at the top.

Format per entry: date header, **Operation**, **Pages updated**, **Source** (if any), **Cross-refs**, **claude-mem** (if any), key facts.

---

## 2026-09-14 — ogx-ui in `genai` pointed at the wrong Llama Stack service

- **Operation:** debug + fix + add finding
- **Pages updated:**
  - [`findings.md`](findings.md) — "genai namespace: Llama Stack service is `lsd-genai-playground-service`"
- **Source:** Live cluster `cluster-sznd8.sznd8.sandbox4020.opentlc.com`, namespace `genai`. UI Settings page error: `Cannot reach http://llama-stack-service:8321`.
- **Cross-refs:** [`findings.md`](findings.md) ↔ [`pitfalls.md`](pitfalls.md) #36 ↔ [`components.md`](components.md)
- **Key facts recorded:**
  - The operator names the Service `<CR name>-service`; the CR here is `lsd-genai-playground`, so the Service is `lsd-genai-playground-service`. The documented `llama-stack-service` only holds where the CR is named `llama-stack`.
  - `oc get llamastackdistribution -A` fails on this cluster (resource type not registered) — discover the endpoint from `oc get svc -n <ns> | grep -i stack`.
  - Provider id is `vllm-inference-1`, not `vllm`; the LLM registers as `vllm-inference-1/redhataiministral-3-3b-instruc` (Ministral-3-3B-Instruct-2512), plus a duplicate registration under `.../publishers/genai/models/...`.
  - Fixed with `helm upgrade ogx-ui hassanbadawy/ogx-ui --version 2.0.1 -n genai --reuse-values --set ui.llamaStackUrl=... --set ui.defaultModel=...` (revision 3) — this also moved the live release onto the published 2.0.1 chart.
  - Chart defaults were left unchanged: `llama-stack-service` remains the right generic default; the service name is per-install, not a chart bug.

---

## 2026-09-14 — correction: chart publishing is automated by CI, not the manual runbook recipe

- **Operation:** correction (supersedes part of the entry below, same date) + runbook rewrite
- **Pages updated:**
  - [`runbook.md`](runbook.md) — "Release a new helm chart version" replaced; the manual `helm package` → `gh release create` → `helm repo index --merge` sequence is retired
- **Source:** [`.github/workflows/helm-release.yml`](../.github/workflows/helm-release.yml); run `34785193600` ("Release Helm Charts", push, success, 13 s, 2026-09-13T21:54:21Z).
- **Cross-refs:** [`runbook.md`](runbook.md) ↔ [`pitfalls.md`](pitfalls.md) #36
- **Correction to the entry below:** that entry states `ogx-ui-2.0.1` was published by hand
  (`gh release create` + a `--url`-merged `index.yaml` on `gh-pages`). **That is not what happened.**
  The repo runs `helm/chart-releaser-action@v1.7.0` on every push to `main` touching `helm/**`; it
  created the release, attached `ogx-ui-2.0.1.tgz`, and committed the merged `index.yaml` to
  `gh-pages` 13 s after the push. The manual `gh release create` issued afterwards failed with
  `a release with the same tag name already exists` — the tag already pointed at commit `b672585`.
  Nothing was published by hand.
- **Key facts recorded:**
  - Workflow: `charts_dir: helm`, `skip_existing: true`, triggers on `push` to `main` under `helm/**` plus `workflow_dispatch`. Releasing a chart therefore requires only a `Chart.yaml` version bump and a push.
  - `skip_existing: true` makes a forgotten version bump silent — CI goes green and publishes nothing. Verify with `helm search repo`.
  - chart-releaser sets the release body to the chart `description`; hand-written notes must be applied afterwards with `gh release edit`.
  - Do not pre-create the release manually: it either races CI or blocks it.
  - Published state verified: `helm search repo hassanbadawy/ogx-ui --versions` lists 2.0.1 and 2.0.0, and `helm template t hassanbadawy/ogx-ui --version 2.0.1 -n somens` renders `image-registry.openshift-image-registry.svc:5000/somens/ogx-ui:latest`, confirming the namespace-aware default works from the published artefact.

---

## 2026-09-14 — ogx-ui `ErrImagePull` in `genai`: hardcoded build namespace in chart default

- **Operation:** debug + fix + add pitfall + chart change
- **Pages updated:**
  - [`pitfalls.md`](pitfalls.md) — entry #36 (`image.repository` hardcoded to `agentic-ivr`; internal-registry `authentication required` really means repo-not-found)
- **Source:** Live cluster `cluster-sznd8.sznd8.sandbox4020.opentlc.com`, namespace `genai`. Verbatim event: `Back-off pulling image "image-registry.openshift-image-registry.svc:5000/agentic-ivr/ogx-ui:latest": ErrImagePull ... authentication required`.
- **Cross-refs:** [`pitfalls.md`](pitfalls.md) ↔ [`components.md`](components.md) ↔ [`runbook.md`](runbook.md) ↔ [`helm/ogx-ui/values.yaml`](../helm/ogx-ui/values.yaml)
- **Key facts recorded:**
  - Release `ogx-ui` (chart 2.0.0) was deployed in `genai`, but `image.repository` named namespace `agentic-ivr`, which does not exist on this cluster. No imagestream or buildconfig for ogx-ui existed anywhere (`oc get is -A | grep ogx` → empty).
  - The OpenShift internal registry answers `authentication required` for a non-existent repository rather than a 404 — do not read it as an RBAC or pull-secret problem before verifying the imagestream exists in the namespace the repository string names.
  - Fixed on cluster: `oc new-build --binary --strategy=docker --name=ogx-ui -n genai`, `dockerfilePath=Containerfile` patch, `oc start-build --from-dir=./ogx-ui`, then `helm upgrade ... --set image.repository=image-registry.openshift-image-registry.svc:5000/genai/ogx-ui` (revision 2).
  - Pod `ogx-ui-b8d768f57-lzzmp` reached `1/1 Running`; route `https://ogx-ui-genai.apps.cluster-sznd8.sznd8.sandbox4020.opentlc.com` returns HTTP 200.
  - Chart fixed at v2.0.1: `values.yaml` default is now `image-registry.openshift-image-registry.svc:5000/{{ .Release.Namespace }}/ogx-ui`, rendered via `tpl` in `deployment.yaml`. Verified with `helm template -n somens` (resolves to `somens`) and with `--set image.repository=quay.io/foo/bar` (override still literal).
  - `--reuse-values` carries the stale repository forward, so an existing release needs the explicit `--set` once even after the chart default is fixed.
  - Published as chart `ogx-ui-2.0.1`: GitHub release tag `ogx-ui-2.0.1` with `ogx-ui-2.0.1.tgz` attached, `index.yaml` on `gh-pages` merged with `--url https://github.com/hassanbadawy/rhelai-omni-chatter/releases/download/ogx-ui-2.0.1`. Note the runbook's `--url https://hassanbadawy.github.io/...` is wrong for this repo — `gh-pages` holds only `index.html` and `index.yaml`; the `.tgz` lives on the GitHub release. [`runbook.md`](runbook.md) corrected.

---

## 2026-06-29 — LiteMaaS kube:admin OAuth login fix; helm chart hardened

- **Operation:** debug + fix + add pitfall
- **Pages updated:**
  - [`pitfalls.md`](pitfalls.md) — entry #28 (`kube:admin` null `oauth_id` on first login)
- **Source:** Live cluster debugging session on `cluster-7hb2t.7hb2t.sandbox670.opentlc.com`, namespace `genai`.
- **Cross-refs:** [`pitfalls.md`](pitfalls.md) ↔ [`helm/litemaas/templates/backend-deployment.yaml`](../helm/litemaas/templates/backend-deployment.yaml)
- **Key facts recorded:**
  - `kube:admin` has no `metadata.uid` in OpenShift — the virtual admin user returns `null` from `/apis/user.openshift.io/v1/users/~`.
  - The `patch-oauth-service` initContainer patches `oauth.service.js` to use `uid || name` as the OAuth subject. It was present in the local chart but had never been deployed (helm release was at revision 1 from June 14; chart updated locally after that).
  - Original script had no `set -e` and no verification — silent failure if pattern not found. Fixed: added `set -e`, `grep -q` pre-check, and exit 1 on failure so a broken patch surfaces as `Init:Error`.
  - Fix deployed via `helm upgrade litemaas helm/litemaas/ -n genai --reuse-values` (revision 2).

---

## 2026-05-23 — student-assistant MVP1 redesign: question bank pipeline

- **Operation:** add findings + add pitfalls
- **Pages updated:**
  - [`findings.md`](findings.md) — new entry "student-assistant MVP1 redesigned: question bank pipeline, no RAG"
  - [`pitfalls.md`](pitfalls.md) — entries #26 (`FloatingActionButton.text` removed in Flet 0.85.1) and #27 (`aiosqlite.executescript` auto-commit breaks migration recording)
- **Source:** Implementation session — complete rewrite of `student-assistant/` from wiki+RAG to question bank architecture.
- **Cross-refs:** [`findings.md`](findings.md) ↔ [`pitfalls.md`](pitfalls.md) ↔ [`../student-assistant/`](../student-assistant/)
- **Key facts recorded:**
  - No RAG, no chat. LlamaStack replaced by generic OpenAI-compatible `AIClient`.
  - New domain: Student → Grade → Material → MaterialFile → QuestionBank → TestSession.
  - Migration v002 idempotent: `CREATE TABLE IF NOT EXISTS materials_v2`.
  - `FloatingActionButton` in Flet 0.85.1 takes no `text=`; use `tooltip=`.
  - `executescript()` auto-commits — never wrap with `BEGIN;`; always record migration after.
  - App starts clean at `http://localhost:8080` via `uv run python app.py`.

---

## 2026-05-16 — student-assistant first local run; Flet 0.85.1 and Podman pitfalls

- **Operation:** add pitfalls + add finding
- **Pages updated:**
  - [`pitfalls.md`](pitfalls.md) — entries #25 (Flet 0.85.1 breaking API changes, 13-item table) and #26 (Podman `host.containers.internal`)
  - [`findings.md`](findings.md) — new dated entry "student-assistant first local run; Flet 0.85.1 compatibility fixes applied"
- **Source:** Live debugging session — iterated on browser session crash traces from `student-assistant/` running under Flet 0.85.1.
- **Cross-refs:** [`pitfalls.md`](pitfalls.md) ↔ [`findings.md`](findings.md) ↔ [`student-assistant/`](../student-assistant/) ↔ [`wiki/handbooks/flet-handbook.md`](handbooks/flet-handbook.md)
- **Key facts recorded:**
  - Flet 0.85.1 (installed by `uv sync`) breaks code written for 0.26 in 13 distinct ways — all fixed in `student-assistant/` as of this date.
  - `flet run --web` crashes with `ModuleNotFoundError: No module named 'flet_desktop'` when only `flet_web` is installed. Use `python app.py` with `ft.app(..., view=ft.AppView.WEB_BROWSER, port=8080)`.
  - `FilePickerFile.path` is always `None` in web mode; must use `pick_files(with_data=True)` and read `.bytes`.
  - `page.session.store` (not `page.session`) is the KV store in 0.85.1. `page.show_dialog()` / `page.pop_dialog()` replace the `page.dialog` assignment pattern.
  - Podman 5.7.1 ships built-in compose (Docker Compose v5.1.0). `host.docker.internal` → `host.containers.internal` in compose files.
  - `.env` must be copied from `.env.example` before first run.
  - Sandbox cluster `ocp.9xgvv.sandbox3434.opentlc.com` DNS expired — needs replacement endpoint.

---

## 2026-05-09 — Wiki tooling ecosystem survey + 3-phase roadmap

- **Operation:** add finding + add roadmap section
- **Pages updated:**
  - [`findings.md`](findings.md) — new dated entry "Wiki tooling ecosystem survey (Karpathy pattern, 2026)"
  - [`future-work.md`](future-work.md) — new section "Wiki tooling roadmap (Karpathy llm-wiki ecosystem)" with three phases
- **Source:** WebSearch + WebFetch across the active 2026 ecosystem of Karpathy-pattern wiki plugins, Obsidian/Logseq MCP servers, and markdown+shadow-vector hybrids. No single canonical source; consolidated links in `findings.md`.
- **Cross-refs:** [`findings.md`](findings.md) ↔ [`future-work.md`](future-work.md) ↔ [`../helm/milvus/`](../helm/milvus/) (memsearch dogfooding angle).
- **Key facts recorded:**
  - At least 5 active Claude Code plugins/skills implement Karpathy's pattern: `kfchou/wiki-skills`, `Astro-Han/karpathy-llm-wiki`, `ussumant/llm-wiki-compiler`, `nvk/llm-wiki`, `praneybehl-llm-wiki`. Most feature-rich is `llm-wiki-compiler` (coverage tags, time-decay warnings, `/wiki-visualize`).
  - `zilliztech/memsearch` is a markdown+Milvus shadow-index pattern — markdown source of truth, Milvus rebuildable cache, hybrid BM25+dense+RRF. Strong fit for this project because we already deploy Milvus via [`helm/milvus/`](../helm/milvus/) — can dogfood the customer-facing vector store.
  - Obsidian-shaped MCP servers (`jacksteamdev/obsidian-mcp-tools`, `aaronsb/obsidian-semantic-mcp`) read plain markdown directories, no Obsidian app required. Defer until wiki crosses ~50 pages.
  - Managed memory services (Mem0, Zep, Letta, Cognee, Cloudflare Agent Memory) are explicitly skipped — they pull the wiki off git, forfeiting auditability and PR-reviewability.
- **Recommendation captured in `future-work.md`:** Phase 1 (`llm-wiki-compiler` skill) is high-value/low-cost — install. Phase 2 (`memsearch` against existing Milvus) is medium-value/medium-cost — defer until wiki grows or a Milvus debugging need surfaces. Phase 3 (Obsidian MCP) is overbuilt for current corpus size.

---

## 2026-05-09 — Bootstrap the wiki

- **Operation:** create wiki root, migrate existing docs
- **Pages created:** [`README.md`](README.md), [`architecture.md`](architecture.md), [`components.md`](components.md), [`findings.md`](findings.md), [`runbook.md`](runbook.md), [`SOURCES.md`](SOURCES.md), [`log.md`](log.md)
- **Pages migrated** (via `git mv`, history preserved):
  - `ogx-ui/docs/decisions.md` → [`decisions.md`](decisions.md)
  - `ogx-ui/docs/entanglements.md` → [`entanglements.md`](entanglements.md)
  - `ogx-ui/docs/future-work.md` → [`future-work.md`](future-work.md)
  - `ogx-ui/docs/guardrails-redteam-report.md` → [`guardrails-redteam-report.md`](guardrails-redteam-report.md)
  - `ogx-ui/docs/llama-stack-api-improvements.md` → [`llama-stack-api-improvements.md`](llama-stack-api-improvements.md)
  - `ogx-ui/docs/model-benchmarks.md` → [`model-benchmarks.md`](model-benchmarks.md)
  - `ogx-ui/docs/pitfalls.md` → [`pitfalls.md`](pitfalls.md)
  - `docs/flet-handbook.md` → [`handbooks/flet-handbook.md`](handbooks/flet-handbook.md)
  - `docs/llamastack-handbook.md` → [`handbooks/llamastack-handbook.md`](handbooks/llamastack-handbook.md)
- **Tooling added:** [`../scripts/wiki_lint.py`](../scripts/wiki_lint.py) — mechanical checks for broken links, orphan pages, source frontmatter, log date monotonicity.
- **CLAUDE.md change:** Replaced the small "Wiki / Persistent Knowledge" section with a full Karpathy-style "Local wiki discipline" section — read order, write order, rules. The wiki path moved from `ogx-ui/docs/` to `wiki/`.
- **Source:** Karpathy gist [llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and the agentic-ivr `wiki/` precedent.
- **claude-mem:** #893, #896, #898, #902 — design discovery and 5-phase plan.
- **Key facts recorded:**
  - Single wiki root at `wiki/`, not split across multiple dirs.
  - `findings.md` and `runbook.md` are NEW pages — they did not exist in the legacy `ogx-ui/docs/` layout. Future sessions should populate them as work happens, rather than retroactively backfilling.
  - `sources/` and `entities/` directories created empty — no retroactive seeding (the raw materials for `flet-handbook.md` and `llamastack-handbook.md` are gone).
  - `log.md` and claude-mem are complementary: this log is in-repo and survives history; claude-mem is conversational and survives compaction. A `log.md` entry may reference a claude-mem ID (e.g. `#902`) to give future readers a way back to the conversation.

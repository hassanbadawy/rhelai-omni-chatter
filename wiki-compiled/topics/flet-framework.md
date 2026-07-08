# Flet Framework

> Compiled topic article for the rhelai-omni-chatter knowledge base. Reference brought into the project because we plan to build a new student-assistant app on Flet (see `future-work-roadmap.md`). Sole source: the in-tree [flet-handbook.md](../../wiki/handbooks/flet-handbook.md), itself a self-contained reference compiled from web research.

## Summary [coverage: low -- 1 source]

**Flet** is an open-source (Apache 2.0) Python framework for building **real-time, cross-platform applications** — web, mobile, desktop — from a single Python codebase. The UI is rendered by **Flutter** (Google's Dart-based UI toolkit) so controls, animations and gestures are native-quality, but only Python is written. The core idea is `UI = f(state)` — declarative when you want it, imperative when you need it. A program is a Python script with a `main(page)` function that composes `Control` objects (`Text`, `Button`, `Row`, `Column`, …) on a `Page`; Flet ships them over a binary protocol to a Flutter client.

**Versions (as of May 2026):** latest stable `0.84.0` (April 2026); active development `0.85.0.devN`; ~142 total releases; ~16,000 GitHub stars. Source breakdown: Python 72%, Dart 24%, JS 2%, C++ 1%. The Flet 1.0 line (Beta shipped Dec 2025 as `0.80.0`) introduced a re-architecture: dataclass-based controls, the **MessagePack** binary protocol replacing JSON+base64, a services architecture (`page.services.append(...)` for non-visual controls like `FilePicker`, `Audio`, `AudioRecorder`), and React-like declarative UI via `@ft.component` / `@ft.observable` plus hooks.

**What ships:**
- 150+ ready-to-use controls (Material 3 + Cupertino, charts, video, maps, Lottie, Rive, drag-and-drop, gestures, camera as of 0.81, code editor, page view, color picker).
- Built-in OAuth (Google, GitHub, Azure, Auth0, generic OIDC).
- Adaptive controls that switch Material/Cupertino per platform with `adaptive=True`.
- A `flet build` packaging pipeline producing iOS/Android/Windows/macOS/Linux/Web binaries from one source tree (uses the `serious_python` package to bundle a Python interpreter into the Flutter app).

**Position vs Streamlit / Reflex / NiceGUI / Gradio (from Chapter 38).** Streamlit and Gradio are HTML-rerender dashboards — single-page, web-only, no mobile or desktop targets. Reflex is React + FastAPI in Python, web-only. NiceGUI is HTML/Quasar on FastAPI, web-only. Only Flet covers iOS/Android native + Win/macOS/Linux + Web (Pyodide static or FastAPI dynamic) from one codebase, with native-quality UI. The handbook's explicit guidance: *"Pick Flet when you need a real cross-platform app with one Python codebase, native-quality UI, and the ability to ship to mobile stores."* That is precisely our student-assistant use case — we expect to ship to mobile and desktop, want Python-only, and want a UI that doesn't feel like a script-rerun dashboard.

## Architecture & Design [coverage: low -- 1 source]

**Runtime topology.** A Python process holds the business logic, state, async loop, and event handlers. A Flutter client (Dart, native) renders pixels and dispatches events. They communicate over **MessagePack** binary frames carried on a WebSocket (web) or TCP/Unix socket (desktop). On mobile and desktop, the Python interpreter is bundled inside the Flutter app via the **`serious_python`** package, so the same Python source ships into the iOS/Android/macOS/Windows/Linux binary.

**Page model.** `Page` is the root handed to `main(page)`. Treat it as **user-scoped — one per session**. Controls are composed under it. The most relevant properties and methods (Chapter 6):

```python
page.title = "My App"
page.theme_mode = ft.ThemeMode.SYSTEM         # LIGHT | DARK | SYSTEM
page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)
page.padding = 20
page.scroll = ft.ScrollMode.AUTO
page.window.width = 800; page.window.height = 600   # desktop
page.add(*controls)                    # append + auto-update
page.update()                          # flush pending state
page.go("/settings")                   # navigate
page.run_task(my_async_fn, *args)      # schedule coroutine
page.run_thread(blocking_fn, *args)    # offload blocking call
page.show_dialog(dlg); page.pop_dialog()        # 1.0+ dialog API
page.open(banner_or_snackbar)
page.login(provider, scope=[...]); page.logout()
```

`page.controls` is the top-level control list; `page.services` (1.0+) holds non-visual controls (`FilePicker`, `Audio`, `AudioRecorder`, sensors); `page.views` is the navigation stack.

**Navigation: `Page.route` change handler with View stack pattern (Chapter 16).**

```python
def main(page: ft.Page):
    def route_change(_):
        page.views.clear()
        page.views.append(ft.View("/", [
            ft.AppBar(title=ft.Text("Home")),
            ft.ElevatedButton("Settings", on_click=lambda _: page.go("/settings")),
        ]))
        if page.route == "/settings":
            page.views.append(ft.View("/settings", [ft.AppBar(title=ft.Text("Settings"))]))
        tr = ft.TemplateRoute(page.route)         # /books/:id matcher
        if tr.match("/books/:id"):
            page.views.append(ft.View(page.route, [ft.Text(f"Book {tr.id}")]))
        page.update()

    def view_pop(_):
        page.views.pop()
        page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)
```

`ft.run(main, route_url_strategy="hash")` produces `/#/foo` URLs (good for static hosting that can't rewrite). 0.85+ adds a **Declarative Router** integrated with components/hooks, plus `page.pop_views_until(route, result=...)` and the `on_views_pop_until` event.

**State storage tiers (Chapter 17).**

| Tier | API | Lifetime |
|---|---|---|
| Module / closure | plain Python | Process |
| Session | `page.session.set/get/contains_key/remove` | Until server restart, per user |
| Persistent client storage | `page.client_storage` / `page.shared_preferences` (alias) | Persistent: localStorage (web) / JSON (desktop) / NSUserDefaults (iOS) / SharedPreferences (Android) |
| Files | `FLET_APP_STORAGE_DATA` (persistent) / `FLET_APP_STORAGE_TEMP` (scratch) env-var paths | Persistent / scratch |

`page.session` is in-memory and per-user — use it for auth state and navigation context. `page.client_storage` survives restarts but **multiple Flet apps share the same store on the device — always prefix keys with `{company}.{product}.`**.

**Declarative UI and reactivity (1.0+).** `@ft.observable` wraps a dataclass so Flet auto-rerenders subscribed components when fields mutate. `@ft.component` defines function components; hooks include `use_state`, `use_effect`, `use_ref`, `use_context` (+ `create_context`), `use_memo`, and `use_dialog` (0.85+):

```python
@ft.component
def Counter():
    count, set_count = ft.use_state(0)
    return ft.Row([
        ft.Text(str(count), size=24),
        ft.ElevatedButton("+", on_click=lambda: set_count(count + 1)),
    ])
```

This coexists with the imperative subclass style — both are first-class.

**Async event handlers via `httpx.AsyncClient` (Chapter 21, Chapter 15).** Flet runs single-threaded asyncio by default; blocking calls freeze the UI:

```python
import httpx

async def fetch_user(user_id):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://api.example.com/users/{user_id}")
        r.raise_for_status()
        return r.json()
```

For sync libraries, wrap with `page.run_thread(blocking_fn, *args)` or `loop.run_in_executor(page.executor, ...)`. After each handler returns, Flet auto-diffs the control tree and pushes deltas; for batch operations, opt out with `with ft.context.disable_auto_update(): ... lv.update()` for one diff at the end.

**Services architecture (1.0+).** Non-visual controls are appended to `page.services` rather than the legacy "overlay." For example a `FilePicker`:

```python
fp = ft.FilePicker(on_result=lambda e: print(e.files or e.path))
page.services.append(fp)              # 1.0+: services list, not overlay
page.add(ft.ElevatedButton("Pick file",
    on_click=lambda _: fp.pick_files(allow_multiple=True)))
```

`Audio`, `AudioRecorder`, sensors (accelerometer, gyroscope, magnetometer, barometer, battery, connectivity, screen brightness — added Dec 2025) follow the same pattern.

**Two web modes (Chapter 2 / Chapter 25).**

| Mode | What runs where | Best for |
|---|---|---|
| Static / Pyodide (WASM) | Python in the browser via WebAssembly. No server. | GitHub Pages, S3, Cloudflare Pages, simple SPAs |
| Dynamic / FastAPI (ASGI) | Python on the server, UI streamed over WebSocket. | Multi-user, real-time, server-side data, OAuth |

Dynamic-web entry is `app = ft.run(main, export_asgi_app=True)` exposed as a FastAPI ASGI app, run with `uvicorn app:app --host 0.0.0.0 --port 8000` or `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app:app`. Embedding into an existing FastAPI uses the `flet-fastapi` package: `api.mount("/app", flet_fastapi.app(my_flet_main))`. Behind nginx the WebSocket needs upgrade headers (`Upgrade $http_upgrade`, `Connection "upgrade"`).

## Decisions & Rationale [coverage: low -- 1 source]

**Why Flet over Streamlit / Reflex / NiceGUI / Dear PyGui for the student-assistant app.** From Chapter 38's matrix, only Flet ships native iOS/Android, native Win/macOS/Linux, *and* both static-Pyodide and dynamic-FastAPI web from one Python codebase. Streamlit/Gradio target data dashboards — fine for one-off demos, not for an app students keep on their phone. Reflex and NiceGUI are web-only. Dear PyGui is desktop-only with a custom GPU UI. The handbook's explicit "**Pick Flet when** you need a real cross-platform app with one Python codebase, native-quality UI, and the ability to ship to mobile stores" matches exactly.

**Why we accept Flet's tradeoffs.** From Chapter 1's table:

| Pro | Con |
|---|---|
| One codebase, six platforms | Mobile bundle size (Python interpreter shipped) |
| 150+ controls, charts, video, maps | Web (Pyodide) is single-threaded — CPU work freezes UI |
| Material 3 + Cupertino | Mobile binary wheel catalog limited (~60 popular pkgs on `pypi.flet.dev`) |
| Imperative *and* declarative | Custom Flutter widgets need a Dart-side extension |
| Built-in OAuth, file picker, charts | True hot reload (sub-second) still on roadmap |

For a student-assistant app the UI primitives are basic (chat, lists, settings, OAuth login) — well inside the 150-control catalog — and bundle size on mobile is acceptable for a study tool. The Pyodide single-thread limitation only matters for the static-web path; if we ship a server we use the FastAPI mode.

**Why we accept "Flet 1.0 in active development" risk.** As of May 2026, 1.0 is in Beta (`0.80.0` shipped Dec 2025). The dataclass control rewrite, MessagePack protocol, services architecture, and declarative `@ft.component`/`@ft.observable` are present and used by the handbook. Active dev is on `0.85.0.devN`, which adds the declarative Router, scrollable `ResponsiveRow`, `use_dialog` hook, scrollable/pinned `NavigationRail`, AudioRecorder streaming/upload, and video playlist enhancements. The roadmap names true sub-second hot reload and end-to-end UI testing as not-yet-GA. We accept that and pin to a known-stable version (`0.84.0`) for our build, watching the 1.0 GA milestone.

**Imperative + declarative coexistence is deliberate.** Chapter 14 documents three custom-control styles: subclass with defaults (`@ft.control class MyButton(ft.Button)`), composite layout subclass with `init`/`build`/`did_mount`/`will_unmount`/`before_update` lifecycle hooks and `is_isolated=True`, and declarative function component with `@ft.component`. We can pick per-control without forcing a single paradigm.

## Operational Notes [coverage: low -- 1 source]

**Prerequisites.** Python 3.10+ (3.12 is bundled inside packaged apps). macOS 12+, Windows 10/11 64-bit, or Debian 10/11/12 / Ubuntu 20.04/22.04/24.04 LTS. Linux desktop client has `light` (default) and `full` (audio/video) flavors via `FLET_DESKTOP_FLAVOR=full`.

**Install.**

```bash
mkdir my-app && cd my-app
python -m venv .venv && source .venv/bin/activate
pip install 'flet[all]'                # or: uv add 'flet[all]'
flet --version
flet doctor
```

**Scaffold a project (`flet create`, Chapter 5).**

```bash
flet create my-app
```

Generates:

```
my-app/
├── README.md
├── pyproject.toml
├── src/
│   ├── assets/
│   │   └── icon.png
│   └── main.py
└── storage/
    ├── data/
    └── temp/
```

`pyproject.toml` essentials:

```toml
[project]
name = "myapp"
version = "1.0.0"
dependencies = ["flet", "httpx"]

[tool.flet]
product   = "My App"
artifact  = "myapp"
org       = "com.example"
bundle_id = "com.example.myapp"

[tool.flet.app]
path = "src"
module = "main"
```

`[tool.flet]` drives `flet build`. Full reference is Chapter 36.

**Minimal `app.py`.**

```python
# main.py
import flet as ft

def main(page: ft.Page):
    page.title = "Hello, Flet"
    page.add(ft.Text("Hello, world!", size=30))

ft.run(main)
```

**Run locally (`flet run` / `flet debug`, Chapter 22).**

```bash
flet run                       # desktop window (default)
flet run --web                 # browser
flet run -d main.py            # restart on save
flet run --port 8550           # specify port for web
flet run --assets assets       # custom assets dir

flet devices                                # list connected devices
flet emulators                              # list emulators
flet emulators create my-emulator
flet debug android --device-id <id> -v      # build + push + run with logs
flet debug ios --device-id <udid> -v
```

`flet debug` (0.80+) is the recommended way to test mobile features (sensors, camera, push) before a release build. `flet doctor` is the environment sanity check.

**Packaging (Chapter 23 desktop, Chapter 24 mobile, Chapter 25 web).**

```bash
# Desktop
flet build macos                              # macOS host required
flet build windows                            # Windows or macOS host
flet build linux                              # Linux host or WSL

# Mobile (Android)
flet build apk     # split-per-abi, smaller
flet build aab     # for Play Store

# Mobile (iOS) — macOS host only
flet build ipa
flet build ios-simulator

# Web
flet build web \
  --base-url "/myapp/" --route-url-strategy hash \
  --web-renderer canvaskit --pwa-background-color "#000" \
  --no-cdn                     # bundle Pyodide + CanvasKit locally
```

Common flags (desktop example):

```bash
flet build macos \
  --product "My App" --artifact myapp \
  --org com.example --bundle-id com.example.myapp \
  --build-version 1.0.0 --build-number 7 \
  --output dist/ \
  --module-name main \
  --splash-color "#fff" --splash-dark-color "#000" \
  --exclude .git .venv tests \
  --compile-app --compile-packages \
  --flutter-build-args="--dart-define=API_URL=https://api.example.com" \
  --clear-cache --verbose --yes
```

Note: there is also a legacy `flet pack` mentioned in the topic brief (older, simpler desktop packaging), but the handbook focuses on `flet build` for all targets. Use `flet build` for new work.

**Build pipeline (every target):**
1. Generate Flutter project under `build/flutter` from a template.
2. Apply icons and splash. Per-platform icons: `assets/icon_ios.png`, `icon_android.png`, `icon_web.png`, `icon_windows.ico`, `icon_macos.png`. Fallback `assets/icon.png`.
3. `serious_python package`: install deps, compile `.py → .pyc`, exclude unused files.
4. `flutter build`.
5. Copy outputs to `--output` (default `build/<target>`).

**Mobile binary wheels: `pypi.flet.dev`.** A custom PyPI index hosting **pre-built binary wheels for iOS and Android** for ~60+ popular packages: `numpy`, `pandas`, `matplotlib`, `pillow`, `opencv-python`, `cryptography`, `bcrypt`, `pynacl`, `sqlalchemy`, `pymongo`, `gdal`, `shapely`, `pyproj`. Flet's build pipeline automatically uses this index when packaging for mobile. For deps not in the index, build with **Mobile Forge**. Pure-Python deps always work without rebuilding.

**On-device debug.** `flet debug` packages and runs on a real device or emulator — required for sensors, camera, push, and any mobile-only API. List devices with `flet devices`, manage emulators with `flet emulators ...`. For Android, JDK 17 is auto-installed to `$HOME/java/<v>` and the Android SDK to `~/Android/sdk`. iOS requires macOS host (Apple Silicon needs Rosetta 2: `sudo softwareupdate --install-rosetta --agree-to-license`), Xcode 15+, CocoaPods 1.16+, an Apple Developer Program membership, and a provisioning profile + Apple Distribution signing certificate.

**OAuth helper (Chapter 20).** Built-in providers: Google, GitHub, Azure, Auth0, plus generic `OAuthProvider` for any OIDC. GitHub example:

```python
from flet.auth.providers import GitHubOAuthProvider

provider = GitHubOAuthProvider(
    client_id=os.environ["GITHUB_CLIENT_ID"],
    client_secret=os.environ["GITHUB_CLIENT_SECRET"],
    redirect_url="http://localhost:8550/oauth_callback",
)

def on_login(e):
    if not e.error:
        print("token:", page.auth.token.access_token)
        print("user:", page.auth.user.id, page.auth.user["login"])

page.on_login = on_login
page.add(ft.ElevatedButton("Login with GitHub",
    on_click=lambda _: page.login(provider, scope=["public_repo"])))

ft.run(main, port=8550, view=ft.WEB_BROWSER)
```

Persist tokens with `flet.security.encrypt`/`decrypt` (Fernet AES-128 + HMAC + PBKDF2) into `client_storage`; restore via `page.login(provider, saved_token=...)`. `page.logout()` clears `page.auth` and fires `on_logout`. Custom OIDC uses `OAuthProvider(client_id, client_secret, redirect_url, authorization_endpoint, token_endpoint, user_endpoint, user_scopes, user_id_fn)`.

**`ListView` for chat performance (Chapter 7, Chapter 28).** For >200 items **never use `Column`** — use `ListView` (or `GridView`) which only render visible items:

```python
ft.ListView(
    expand=True,
    item_extent=50,
    controls=[ft.Text(f"row {i}") for i in range(10_000)],
    auto_scroll=True,
)
```

Setting `item_extent` enables fast virtualization. For a chat history this is the right control: long, vertically growing, with `auto_scroll=True` to follow new messages. Pair with `with ft.context.disable_auto_update():` when batch-appending many messages, then a single `lv.update()` at the end. Prefer `control.update()` over `page.update()` for smaller diffs; chunk huge inserts (`if i % 500 == 0: page.update()`).

**Custom controls via the `@ft.control` dataclass pattern (Chapter 14).** Three styles:

1. **Styled control — subclass with defaults:**
   ```python
   from dataclasses import field

   @ft.control
   class MyButton(ft.Button):
       bgcolor: str = ft.Colors.ORANGE_300
       color:  str = ft.Colors.GREEN_800
       style:  ft.ButtonStyle = field(
           default_factory=lambda: ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)))
   ```
2. **Composite control — subclass a layout, use `init`/`build`/`did_mount`/`will_unmount`/`before_update` hooks, optionally `is_isolated=True` to prevent parent updates from cascading.**
3. **Declarative function component (1.0+) — `@ft.component` plus hooks (`use_state`, `use_effect`, `use_ref`, `use_context`, `use_memo`, `use_dialog`).**

**Dynamic web deployment as a FastAPI ASGI app.**

```python
# app.py
import flet as ft

def main(page: ft.Page):
    page.add(ft.Text("Hi from FastAPI mode"))

app = ft.run(main, export_asgi_app=True)
```

Run dev with `uvicorn app:app --host 0.0.0.0 --port 8000`; production with `gunicorn -k uvicorn.workers.UvicornWorker -w 4 app:app`. nginx must forward WebSocket upgrade headers. To embed in an existing FastAPI app, install `flet-fastapi` and `api.mount("/app", flet_fastapi.app(my_flet_main))`.

## Pitfalls & Known Issues [coverage: low -- 1 source]

From Chapter 39's troubleshooting table plus the inline rules in Chapters 17, 21, 24, 26, 28, 30. The points most likely to bite us:

- **Mobile packaging requires `pypi.flet.dev` for binary wheels.** Only ~60 popular packages have iOS/Android wheels on the index. A dep without a wheel fails the build with no automatic fallback. Resolution: replace with a pure-Python alternative or build via **Mobile Forge** (Chapter 26). Pure-Python deps always work without rebuilding.
- **`ListView` required for long chat histories — `Column` is O(N) layout.** "Avoid `Column` for thousands of children" is in the perf rules (Chapter 28). For a chat use `ListView` with `item_extent` and `auto_scroll=True`. Symptom of using `Column`: scrolling slow.
- **Flet 1.0 is in active development as of May 2026.** Stable line is `0.84.0`; active dev is `0.85.0.devN`. The 1.0 series introduced breaking changes vs pre-1.0:
  - Pre-1.0 `page.dialog = ...` no longer works — use `page.show_dialog(dlg)` / `page.pop_dialog()`.
  - `FilePicker` and other non-visual controls moved from `page.overlay` to `page.services`.
  - The MessagePack protocol replaced JSON+base64 (no developer-visible API change but binary transfers — images, audio — got faster).
  - Dataclass-based controls supersede the prior class hierarchy (autocomplete-friendly; `@ft.control` decorator).
  
  True sub-second hot reload, end-to-end UI testing, and the FletPad in-browser playground are still on the roadmap, not GA.
- **Signing requirements for platform publishing.**
  - **Android:** release keystore required (`keytool -genkey -v -keystore ~/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload`). `[tool.flet.android]` controls permissions, features, adaptive_icon_background, min_sdk, target_sdk.
  - **iOS:** Apple Developer Program membership, provisioning profile, Apple Distribution signing certificate, Xcode 15+, CocoaPods 1.16+, macOS host. Configure `[tool.flet.ios] team_id = "..."` and `info_plist."NSCameraUsageDescription"` etc.
  - **macOS desktop:** sign + notarize for distribution; `--build-dmg` for a .dmg.
  - **Linux desktop:** AppImage / .deb / .rpm packaging is the developer's responsibility.
  - **Windows desktop:** MSIX/installer is the developer's responsibility.
- **Async hygiene.** Never `time.sleep` or sync HTTP in handlers — the UI freezes. Use `asyncio.sleep`, `httpx.AsyncClient`, `page.run_thread()`, or `loop.run_in_executor(page.executor, ...)`.
- **Storage namespacing.** Multiple Flet apps share the same client store on a device. *"Always prefix keys with `{company}.{product}.`"*.
- **Custom font not loading** → `assets_dir` not set in `ft.run(main, assets_dir="assets")`.
- **OAuth `redirect_url` mismatch** → must match exactly the URL registered with the provider, including scheme and port.
- **Web app behind nginx loses WebSocket** → add `Upgrade` and `Connection "upgrade"` proxy headers.
- **Hot reload not picking up changes** → asset files (not `.py`) cached; stop and re-run `flet run -d`; clear `build/` cache.
- **Packaged app exits immediately** → crash in Python; log path is `os.getenv("FLET_APP_CONSOLE")` or `await ft.StoragePaths().get_console_log_filename()`. Exit code `100` opens an in-app log viewer.
- **Bundle is huge** → trim deps; use `[tool.flet] exclude` and `flet build --exclude` flags; check via `--exclude .git .venv tests` etc.
- **Pyodide app slow / blocks** → single-threaded browser CPU; move heavy work to backend (FastAPI mode).
- **`flet build ipa` fails on Linux** → not supported; build on a macOS host.
- **Pyodide bundles your `.py` source visibly.** *"Never hardcode secrets in source"* — inject via env vars at server start (FastAPI mode) or fetch from the backend at runtime. Encrypt anything sensitive before `client_storage`/`shared_preferences` using `flet.security.encrypt` / `decrypt`.
- **Material 3 widgets look "wrong"** → using `use_material3=False` somewhere; default is M3 in 1.0+; check theme + scoped themes.
- **Pre-1.0 dialog code from old tutorials** uses `page.dialog = ...`; this is removed in 1.0. Migrate to `page.show_dialog(dlg)` / `page.pop_dialog()`.

## Findings & Measurements [coverage: low -- 1 source]

This article is compiled from a single source — the in-tree `flet-handbook.md` — which is itself a self-contained reference *built from web research* (official docs at <https://flet.dev/docs/>, roadmap at <https://flet.dev/roadmap/>, blog at <https://flet.dev/blog>, GitHub at <https://github.com/flet-dev/flet>). The original web sources were not preserved alongside the handbook. **No empirical measurements have been taken from this project** — we have not yet built or shipped a Flet app under `rhelai-omni-chatter`. Numerical claims (release dates, version numbers, control counts, package counts on `pypi.flet.dev`, GitHub stars, perf claims like "6.7× faster control diffing in 0.83.0") are **second-hand** from the handbook, not measured here.

Quantitative items quoted from Chapter 1 stats and Chapter 37 release highlights, dated to the handbook's "as of May 2026" baseline:

| Claim | Source in handbook |
|---|---|
| Latest stable `0.84.0`, April 2026; active dev `0.85.0.devN` | Ch 1 stats; front matter |
| 142 total releases; ~16,000 stars / 651 forks | Ch 1 stats |
| Languages: Python 72%, Dart 24%, JS 2%, C++ 1% | Ch 1 stats |
| 150+ ready-to-use controls | Ch 1 "When to Use Flet" |
| ~60+ popular packages with mobile wheels on `pypi.flet.dev` | Ch 1 trade-offs; Ch 26 |
| 0.83.0 "6.7× faster control diffing" | Ch 37 |
| 0.80.0 (Dec 2025) shipped Flet 1.0 Beta with declarative + imperative coexistence and `flet debug` CLI | Ch 37 |
| 0.81 (Feb 2026) added Camera, CodeEditor, PageView, ColorPicker, Hero animations, Matrix4 transforms | Ch 37 |
| Dec 2025 sensors release: 10 new services (accelerometer, barometer, gyroscope, magnetometer, battery, connectivity, screen brightness, …) | Ch 37 |
| 2024 0.25 added custom packaging (replaces Kivy), Python 3.12 runtime, `pypi.flet.dev`, `Button` alias of `ElevatedButton`, AdMob | Ch 37 |

When we begin implementation we should add a sibling page (e.g. `wiki/findings.md` entry or a new `wiki/flet-implementation.md`) recording dated empirical results: TTFT for our chat UI, mobile bundle size, build times on our hardware, real packaging-step failures, and how `pypi.flet.dev` coverage holds up against our actual dep list.

## Sources [coverage: low -- 1 source]

- [flet-handbook.md](../../wiki/handbooks/flet-handbook.md) — self-contained Flet reference handbook (~70KB, 2100 lines) compiled from web research (`flet.dev/docs`, `flet.dev/roadmap`, `flet.dev/blog`, GitHub `flet-dev/flet`). Targets Flet 1.0+ (0.80–0.84+), Python 3.10+, May 2026 baseline.

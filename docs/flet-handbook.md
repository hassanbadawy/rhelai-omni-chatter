# The Flet Handbook

**A Zero-to-Hero Guide for Python Developers**

> Everything you need to design, build, package, and ship cross-platform applications — web, mobile (iOS/Android), and desktop (Windows/macOS/Linux) — from a single Python codebase, with Flutter-quality UI. From `pip install flet` to `flet build ipa`, with state management, theming, OAuth, packaging, deployment, and real-world architecture.

---

## Front Matter

### About This Book

This handbook is **self-contained**. Share it with another LLM and it has everything it needs to help you build production-grade Flet apps without external lookups.

### Conventions

- Code targets **Flet 1.0+ (0.80–0.84+)** with both imperative and declarative styles. Differences from earlier versions are flagged inline.
- All code is Python 3.10+. Flet's bundled runtime in packaged apps is Python 3.12.
- Where I write `ft`, I mean `import flet as ft`.

### Sources of Truth

- Official docs: <https://flet.dev/docs/>
- Roadmap: <https://flet.dev/roadmap/>
- Blog: <https://flet.dev/blog>
- GitHub: <https://github.com/flet-dev/flet>
- Latest stable: **0.84.0** (April 2026) · Active dev: 0.85.0.devN

---

## Table of Contents

### Part I — Foundations
- Chapter 1. What Is Flet?
- Chapter 2. Architecture
- Chapter 3. Mental Model: Controls, Pages, Sessions

### Part II — Installation & Getting Started
- Chapter 4. Install and First App
- Chapter 5. Project Layout & Tooling
- Chapter 6. The Page Object

### Part III — Building UIs
- Chapter 7. Layout Controls
- Chapter 8. Display Controls
- Chapter 9. Input Controls
- Chapter 10. Dialogs, Banners, SnackBars
- Chapter 11. Cupertino (iOS-Style) Controls
- Chapter 12. Charts and Visualization
- Chapter 13. Animations
- Chapter 14. Custom Controls and Components

### Part IV — Application Behavior
- Chapter 15. Events: Sync, Async, and Scheduling
- Chapter 16. Routing and Navigation
- Chapter 17. State Management
- Chapter 18. Theming and Styling
- Chapter 19. Persistence and Storage
- Chapter 20. Authentication (OAuth)
- Chapter 21. Networking, Files, Audio, Video, Maps

### Part V — Packaging & Deployment
- Chapter 22. `flet run` / `flet debug`
- Chapter 23. Desktop Packaging (Windows / macOS / Linux)
- Chapter 24. Mobile Packaging (Android / iOS)
- Chapter 25. Web Deployment (Pyodide / FastAPI)
- Chapter 26. Binary Packages and Mobile Forge

### Part VI — Production
- Chapter 27. Reference Architecture for a Real App
- Chapter 28. Performance Best Practices
- Chapter 29. Testing and Debugging
- Chapter 30. Security and Secrets

### Part VII — Reference
- Chapter 31. Full Controls Catalog
- Chapter 32. Page API Reference
- Chapter 33. Page Events Reference
- Chapter 34. Plugins / Extensions Catalog
- Chapter 35. CLI Reference
- Chapter 36. `pyproject.toml` / `[tool.flet]` Reference
- Chapter 37. Roadmap & Recent Releases
- Chapter 38. Comparison: Flet vs Streamlit / Reflex / NiceGUI / Dear PyGui
- Chapter 39. Troubleshooting & Pitfalls
- Chapter 40. Glossary

### Appendix A — Complete App: A Notes Application

---

# Part I — Foundations

## Chapter 1. What Is Flet?

Flet is an open-source Python framework for building **real-time, cross-platform applications** — web, mobile, desktop — from one Python codebase. The UI is rendered by **Flutter** (Google's Dart-based UI toolkit), so you get native-quality controls, animations, and gestures, but you write only Python.

### Core Idea

> **UI = f(state)** — declarative when you want it, imperative when you need it.

A Flet program is a Python script with a `main(page)` function. Inside, you compose `Control` objects (Text, Button, Row, Column, …) on a `Page`. Flet ships those controls over a binary protocol to a Flutter client which renders them natively on whatever platform you're on.

### Stats (as of May 2026)

| | |
|---|---|
| License | Apache 2.0 |
| Latest stable | `0.84.0` (April 2026) |
| Active dev | `0.85.0.devN` |
| Releases | 142 total |
| Stars / Forks | ~16,000 / 651 |
| Languages | Python 72%, Dart 24%, JS 2%, C++ 1% |

### When to Use Flet

✅ Cross-platform apps that need real, responsive UI (not script reruns).
✅ One Python codebase deploying to iOS + Android + Web + Windows + macOS + Linux.
✅ Apps that need 150+ ready-to-use controls (charts, video, maps, Lottie, drag-and-drop, gestures).
✅ Material 3 + Cupertino with adaptive switching.
✅ Real-time, multi-user web apps (FastAPI mode).

### When **Not** to Use Flet

❌ Single-purpose ML demo dashboards — Streamlit / Gradio are quicker.
❌ Heavy 3D / shader rendering — no first-class API.
❌ Apps needing arbitrary Flutter widgets without a Dart bridge.
❌ Web apps where bundle size matters more than UX (Pyodide ships a Python runtime).
❌ Mobile apps with rare native dependencies that have no pre-built wheels on `pypi.flet.dev`.

### Trade-offs at a Glance

| Pro | Con |
|---|---|
| One codebase, six platforms | Mobile bundle size (Python interpreter shipped) |
| 150+ controls, charts, video, maps | Web (Pyodide) is single-threaded — CPU work freezes UI |
| Material 3 + Cupertino | Mobile binary wheel catalog limited (~60 popular pkgs on `pypi.flet.dev`) |
| Imperative *and* declarative | Custom Flutter widgets need a Dart-side extension |
| Built-in OAuth, file picker, charts | True hot reload (sub-second) still on roadmap |

---

## Chapter 2. Architecture

```
+-------------------+        binary MessagePack       +-----------------+
|  Python runtime   |  <--------- WebSocket -------->  | Flutter client  |
|  (your main)      |  (or TCP/Unix socket on desktop) | (Dart, native)  |
+-------------------+                                   +-----------------+
        |                                                       |
   business logic,                                       renders pixels,
   state, async,                                         dispatches events
   event handlers
```

### Key Design Points (Flet 1.0)

- **Controls are Python `dataclass` objects** — strongly typed, autocomplete-friendly.
- **MessagePack binary protocol** between Python and Dart (replaced JSON+base64 in 1.0). Faster, no base64 for binary data (images, audio, files).
- **Auto-update**: After each event handler returns, Flet diffs the control tree and pushes deltas to the client. You can opt out with `with ft.context.disable_auto_update():` for batch operations.
- **Single-threaded asyncio** by default. Blocking calls (`time.sleep`, sync HTTP) freeze the UI. Use `asyncio.sleep`, `httpx.AsyncClient`, or `page.run_thread()` for blocking work.
- **Multi-client server**: in web/server modes, each connected user is a session with its own `page`.

### Two Web Modes

| Mode | What runs where | Best for |
|---|---|---|
| **Static / Pyodide (WASM)** | Python runs in the browser via WebAssembly. No server. | GitHub Pages, S3, Cloudflare Pages, simple SPAs |
| **Dynamic / FastAPI (ASGI)** | Python on the server. UI streamed over WebSocket. | Multi-user, real-time, server-side data, OAuth |

### Mobile / Desktop

The Python interpreter is bundled inside the Flutter app via the **`serious_python`** package. The same Python source ships into the iOS/Android/macOS/Windows/Linux binary.

### Hot Reload / Debug

- `flet run -d <app.py>` — auto-restart on file save (full restart, not Flutter-style hot reload).
- `flet debug` — package and run on a real device or emulator (Flet 0.80+).
- `flet devices` — list connected devices/emulators.
- `flet emulators create my-emulator` — manage emulators.
- True sub-second hot reload is on the **Flet 1.0 roadmap** but not yet GA.

---

## Chapter 3. Mental Model: Controls, Pages, Sessions

### The Three Things You'll Touch Constantly

1. **Page** — a single user's window/tab. Flet calls `main(page)` once per session.
2. **Control** — any UI element (`Text`, `Button`, `Row`, `Container`…). Compose them in a tree.
3. **Event** — user interaction (click, change, submit) → Python callback (sync or async).

### Anatomy of a Flet App

```python
import flet as ft

def main(page: ft.Page):
    page.title = "Hello"
    page.theme_mode = ft.ThemeMode.SYSTEM

    def on_click(e):
        msg.value = f"Hi {name.value}!"
        page.update()

    name = ft.TextField(label="Your name", autofocus=True)
    msg = ft.Text()
    page.add(name, ft.Button("Greet", on_click=on_click), msg)

ft.run(main)
```

That's it. Three concepts — page, controls, events — get you 80% of the way.

---

# Part II — Installation & Getting Started

## Chapter 4. Install and First App

### Prerequisites

- **Python**: 3.10+ (3.12 is bundled inside packaged apps).
- **OS**:
  - macOS 12 (Monterey) or later
  - Windows 10/11 64-bit
  - Linux: Debian 10/11/12 or Ubuntu 20.04/22.04/24.04 LTS
- **Linux desktop client variants**:
  - `light` (default) — basic.
  - `full` — adds audio/video. Toggle with `FLET_DESKTOP_FLAVOR=full`.

### Install

```bash
# pip
mkdir my-app && cd my-app
python -m venv .venv
source .venv/bin/activate
pip install 'flet[all]'

# uv (faster)
uv init --python='>=3.10'
uv venv && source .venv/bin/activate
uv add 'flet[all]'

# verify
flet --version
flet doctor
```

### Hello, Flet

```python
# main.py
import flet as ft

def main(page: ft.Page):
    page.title = "Hello, Flet"
    page.add(ft.Text("Hello, world!", size=30))

ft.run(main)
```

Run it three different ways:

```bash
flet run                    # opens a desktop window
flet run --web              # opens default browser
flet run -d main.py         # hot reload on save
```

---

## Chapter 5. Project Layout & Tooling

### Scaffold a Project

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

### `pyproject.toml` Essentials

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

The `[tool.flet]` section drives `flet build`. Detailed reference is in Chapter 36.

---

## Chapter 6. The Page Object

The `page` is the root container handed to your `main(page)`. Treat it as user-scoped — one per session.

### Most-Used Properties

```python
page.title = "My App"
page.theme_mode = ft.ThemeMode.SYSTEM         # LIGHT, DARK, SYSTEM
page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)
page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
page.padding = 20
page.scroll = ft.ScrollMode.AUTO
page.bgcolor = ft.Colors.WHITE
page.fonts = {"Kanit": "/fonts/Kanit-Bold.ttf"}

# desktop window
page.window.width = 800
page.window.height = 600
page.window.center()
page.window.title_bar_hidden = True
```

### Most-Used Methods

```python
page.add(*controls)                    # append + auto-update
page.remove(*controls)
page.clean()                           # clear all
page.update()                          # flush pending state
page.go("/settings")                   # navigate
page.run_task(my_async_fn, *args)      # schedule coroutine
page.run_thread(blocking_fn, *args)    # offload blocking call
page.show_dialog(dlg)                  # 1.0+ dialog API
page.pop_dialog()
page.open(banner_or_snackbar)
page.login(provider, scope=[...])
page.logout()
```

A full property/method/event reference is in Chapters 32 and 33.

---

# Part III — Building UIs

## Chapter 7. Layout Controls

The four containers you'll use most:

```python
# Row — horizontal flex
ft.Row(
    [ft.Text("a"), ft.Text("b")],
    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    vertical_alignment=ft.CrossAxisAlignment.CENTER,
    spacing=10,
    wrap=True,
)

# Column — vertical flex
ft.Column([...], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

# Stack — overlay
ft.Stack([
    ft.Image(src="bg.png"),
    ft.Container(ft.Text("Overlay"), top=10, left=10),
])

# Container — single-child styling
ft.Container(
    content=ft.Text("Card"),
    padding=20, margin=10,
    bgcolor=ft.Colors.AMBER_100,
    border_radius=12,
    gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                               colors=[ft.Colors.BLUE, ft.Colors.PURPLE]),
    shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK26),
    animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
)
```

### Virtualized Lists

For >200 items, **never** use `Column`. Use `ListView` or `GridView` — they only render visible items.

```python
ft.ListView(
    expand=True,
    item_extent=50,
    controls=[ft.Text(f"row {i}") for i in range(10_000)],
    auto_scroll=True,
)

ft.GridView(
    runs_count=4,             # or max_extent=200
    child_aspect_ratio=1.0,
    spacing=10,
    controls=[...],
)
```

### Responsive Layouts

```python
ft.ResponsiveRow([
    ft.Container(ft.Text("Sidebar"), col={"xs": 12, "md": 3}, bgcolor=ft.Colors.AMBER),
    ft.Container(ft.Text("Main"),    col={"xs": 12, "md": 9}, bgcolor=ft.Colors.WHITE),
])
```

Breakpoints: `xs / sm / md / lg / xl / xxl`. Bootstrap-style 12 columns. As of 0.85, `ResponsiveRow` is scrollable.

### Navigation Scaffolds

```python
page.appbar = ft.AppBar(title=ft.Text("My App"), actions=[ft.IconButton(ft.Icons.SETTINGS)])
page.navigation_bar = ft.NavigationBar(destinations=[
    ft.NavigationDestination(icon=ft.Icons.HOME,  label="Home"),
    ft.NavigationDestination(icon=ft.Icons.PERSON, label="Profile"),
])
page.drawer = ft.NavigationDrawer(controls=[...])
page.floating_action_button = ft.FloatingActionButton(icon=ft.Icons.ADD)
```

---

## Chapter 8. Display Controls

```python
# Text — rich text styling
ft.Text(
    "Hello",
    size=20, weight=ft.FontWeight.BOLD, italic=True,
    color=ft.Colors.INDIGO, font_family="Kanit",
    selectable=True,
    spans=[ft.TextSpan("world", ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE))],
    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
)

# Markdown
ft.Markdown(
    "# Heading\n```python\nprint('hi')\n```\n[link](https://flet.dev)",
    extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
    on_tap_link=lambda e: page.launch_url(e.data),
)

# Icon, Image, Avatar
ft.Icon(ft.Icons.HOME, color=ft.Colors.RED, size=40)
ft.Image(src="photo.png", fit=ft.ImageFit.COVER, width=200, height=200,
         error_content=ft.Text("failed"))
ft.CircleAvatar(content=ft.Text("HB"), bgcolor=ft.Colors.AMBER)

# Status / progress
ft.ProgressBar(value=0.42)
ft.ProgressRing(width=24, height=24, stroke_width=3)
ft.Chip(label=ft.Text("Tag"), on_select=lambda e: ..., on_delete=lambda e: ...)
ft.Badge(label="3", text_color="white", bgcolor="red")
ft.Tooltip(message="Help text", content=ft.IconButton(ft.Icons.HELP))
```

---

## Chapter 9. Input Controls

```python
# TextField
name = ft.TextField(
    label="Name",
    hint_text="Enter your name",
    helper_text="As it appears on ID",
    prefix_icon=ft.Icons.PERSON,
    suffix_icon=ft.Icons.CLEAR,
    border=ft.InputBorder.OUTLINE,
    autofocus=True,
    password=False, can_reveal_password=False,
    multiline=False, max_lines=1, min_lines=1,
    keyboard_type=ft.KeyboardType.EMAIL,
    on_change=lambda e: ...,
    on_submit=lambda e: ...,
    on_focus=lambda e: ..., on_blur=lambda e: ...,
)
# Programmatically focus
name.focus()

# Buttons
ft.ElevatedButton("Save", icon=ft.Icons.SAVE, on_click=on_save)
ft.FilledButton("Primary", on_click=...)
ft.FilledTonalButton("Tonal")
ft.OutlinedButton("Secondary")
ft.TextButton("Cancel")
ft.IconButton(ft.Icons.DELETE, on_click=...)

# Selection
ft.Checkbox(label="Subscribe", value=True, on_change=...)
ft.RadioGroup(content=ft.Column([
    ft.Radio(value="a", label="Option A"),
    ft.Radio(value="b", label="Option B"),
]), on_change=...)
ft.Switch(label="Dark mode", value=False, on_change=...)
ft.Slider(min=0, max=100, divisions=10, label="{value}%", on_change=...)
ft.RangeSlider(min=0, max=100, start_value=20, end_value=80)

# Dropdowns / pickers
ft.Dropdown(
    label="Country",
    options=[ft.dropdown.Option("US"), ft.dropdown.Option("EG")],
)
ft.AutoComplete(suggestions=[ft.AutoCompleteSuggestion(key="apple", value="Apple")])
ft.SearchBar(bar_hint_text="Search…", view_hint_text="Search anything")
ft.SegmentedButton(
    selected={"day"},
    segments=[ft.Segment(value="day",   label=ft.Text("Day")),
              ft.Segment(value="week",  label=ft.Text("Week")),
              ft.Segment(value="month", label=ft.Text("Month"))],
)

# Date/Time
ft.DatePicker(on_change=...)
ft.TimePicker(on_change=...)
```

### File Picker (Service in 1.0+)

```python
fp = ft.FilePicker(
    on_result=lambda e: print(e.files or e.path),
)
page.services.append(fp)              # 1.0+: add to services, not overlay
page.add(ft.ElevatedButton("Pick file", on_click=lambda _: fp.pick_files(allow_multiple=True)))

# Save dialog
result = await fp.save_file_async(file_name="export.json")

# Upload (web)
fp.upload([ft.FilePickerUploadFile(name=f.name, upload_url=upload_url)])
```

---

## Chapter 10. Dialogs, Banners, SnackBars

```python
# 1.0+ dialog API
def open_dlg(_):
    dlg = ft.AlertDialog(
        title=ft.Text("Delete file?"),
        content=ft.Text("This cannot be undone."),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: page.pop_dialog()),
            ft.FilledButton("Delete", on_click=do_delete),
        ],
    )
    page.show_dialog(dlg)

# SnackBar
page.open(ft.SnackBar(ft.Text("Saved!"), action="UNDO"))

# Banner
page.open(ft.Banner(
    content=ft.Text("You're offline."),
    leading=ft.Icon(ft.Icons.WIFI_OFF),
    actions=[ft.TextButton("Retry", on_click=...)],
))

# BottomSheet
page.open(ft.BottomSheet(content=ft.Container(ft.Text("Drawer"), padding=20)))
```

> ⚠️ **Pre-1.0 API** (`page.dialog = dlg; dlg.open = True; page.update()`) is removed in Flet 1.0+. Use `page.show_dialog()` / `page.pop_dialog()`.

---

## Chapter 11. Cupertino (iOS-Style) Controls

For iOS-native look:

```python
ft.CupertinoButton("Save", on_pressed=...)
ft.CupertinoFilledButton("Primary")
ft.CupertinoSwitch(value=True)
ft.CupertinoSlider(min=0, max=1, value=0.5)
ft.CupertinoActivityIndicator()
ft.CupertinoTextField(placeholder_text="Search")
ft.CupertinoSegmentedButton(selected_index=0,
    controls=[ft.Text("D"), ft.Text("W"), ft.Text("M")])
ft.CupertinoNavigationBar(middle=ft.Text("Title"))
ft.CupertinoAlertDialog(title=ft.Text("Confirm"), actions=[...])
ft.CupertinoActionSheet(title=ft.Text("Pick"), actions=[...])
```

### Adaptive Controls

Set `adaptive=True` on supporting controls to switch Material/Cupertino automatically based on platform:

```python
ft.Switch(adaptive=True)               # Material on Android, Cupertino on iOS
ft.AlertDialog(adaptive=True, ...)
ft.Slider(adaptive=True, ...)
```

---

## Chapter 12. Charts and Visualization

### Native Material Charts

```python
ft.LineChart(
    data_series=[
        ft.LineChartData(
            data_points=[ft.LineChartDataPoint(i, math.sin(i)) for i in range(50)],
            stroke_width=2,
            color=ft.Colors.BLUE,
        )
    ],
    border=ft.border.all(1, ft.Colors.GREY),
    horizontal_grid_lines=ft.ChartGridLines(interval=1),
    vertical_grid_lines=ft.ChartGridLines(interval=1),
    left_axis=ft.ChartAxis(labels_size=40),
    bottom_axis=ft.ChartAxis(labels_size=20),
    expand=True,
)

ft.BarChart(bar_groups=[ft.BarChartGroup(x=i, bar_rods=[ft.BarChartRod(to_y=v)])
                        for i, v in enumerate(values)])

ft.PieChart(sections=[ft.PieChartSection(value=30, title="A"),
                      ft.PieChartSection(value=70, title="B")])
```

### Matplotlib / Plotly

```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1,2,3], [4,5,6])
page.add(ft.MatplotlibChart(fig, expand=True))

import plotly.express as px
fig = px.scatter(x=[1,2,3], y=[4,5,6])
page.add(ft.PlotlyChart(fig, expand=True))
```

---

## Chapter 13. Animations

### Implicit Animations (Container)

```python
c = ft.Container(
    width=100, height=100, bgcolor="red",
    animate=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_OUT_CUBIC),
)
def grow(_):
    c.width = 300
    c.bgcolor = "blue"
    c.update()
page.add(c, ft.ElevatedButton("Grow", on_click=grow))
```

### Per-Property Animations

```python
ft.Container(animate_opacity=300)        # ms
ft.Container(animate_rotation=ft.Animation(500, ft.AnimationCurve.BOUNCE_OUT))
ft.Container(animate_scale=True)         # 1000ms linear
ft.Container(animate_offset=300)
ft.Container(animate_position=300)
```

### AnimatedSwitcher

```python
sw = ft.AnimatedSwitcher(
    content=ft.Text("first"),
    transition=ft.AnimatedSwitcherTransition.FADE,
    duration=300,
    switch_in_curve=ft.AnimationCurve.EASE_OUT,
)
def toggle(_):
    sw.content = ft.Text("second" if sw.content.value == "first" else "first")
    sw.update()
```

### Hero Animations (0.81+)

Shared-element transitions across routes:

```python
# View 1
ft.Hero(tag="img-1", content=ft.Image(src="thumb.png"))

# View 2 (same tag)
ft.Hero(tag="img-1", content=ft.Image(src="full.png"))
```

The element morphs smoothly between views during navigation.

### Animation End Callback

```python
ft.Container(
    animate_opacity=300,
    on_animation_end=lambda e: print("done:", e.data),
)
```

---

## Chapter 14. Custom Controls and Components

Three styles, each fitting different use cases.

### 1. Styled Control — Subclass with Defaults

```python
from dataclasses import field

@ft.control
class MyButton(ft.Button):
    bgcolor: str = ft.Colors.ORANGE_300
    color:  str = ft.Colors.GREEN_800
    style:  ft.ButtonStyle = field(
        default_factory=lambda: ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )

page.add(MyButton(text="Click me", on_click=...))
```

### 2. Composite Control — Subclass a Layout

```python
@ft.control
class Task(ft.Row):
    text: str = ""

    def init(self):
        self.text_view = ft.Text(self.text)
        self.text_edit = ft.TextField(value=self.text, visible=False)
        self.controls = [
            ft.Checkbox(),
            self.text_view,
            self.text_edit,
            ft.IconButton(ft.Icons.EDIT, on_click=self.toggle_edit),
        ]

    def toggle_edit(self, _):
        self.text_view.visible = not self.text_view.visible
        self.text_edit.visible = not self.text_edit.visible
        self.update()
```

### 3. Declarative Function Component (Flet 1.0+)

```python
@ft.component
def Counter():
    count, set_count = ft.use_state(0)
    return ft.Row([
        ft.Text(str(count), size=24),
        ft.ElevatedButton("+", on_click=lambda: set_count(count + 1)),
    ])

page.add(Counter())
```

### Lifecycle Hooks (subclassed controls)

| Hook | When |
|---|---|
| `init` | Right after construction (set defaults, build children) |
| `build` | When `self.page` is first assigned |
| `did_mount` | After insertion into the tree |
| `will_unmount` | Before removal — cancel timers, tasks |
| `before_update` | On every update (do **not** call `update()` here) |

Set `is_isolated=True` to prevent parent updates from cascading into a control.

---

# Part IV — Application Behavior

## Chapter 15. Events: Sync, Async, and Scheduling

### Sync vs Async Handlers

```python
def on_click(e):                   # sync — runs on threadpool
    e.control.text = "Clicked"
    e.control.update()

async def on_click(e):             # async — runs on asyncio loop (preferred for I/O)
    await asyncio.sleep(1)
    e.control.text = "Done"
    e.control.update()
```

> **Rule:** never call `time.sleep` or sync HTTP in async handlers. Use `await asyncio.sleep` and `httpx.AsyncClient`.

### The Event Object

```python
e.control      # control that emitted
e.data         # string payload (event-specific)
e.page         # convenience accessor
```

### Scheduling Work

```python
page.run_task(my_async_fn, *args)        # background coroutine
page.run_thread(blocking_fn, *args)      # offload CPU/blocking work to threadpool
```

### Auto-Update and Batching

After each handler returns, Flet auto-diffs the tree and pushes deltas. For bulk operations, disable it:

```python
with ft.context.disable_auto_update():
    for i in range(10_000):
        lv.controls.append(ft.Text(str(i)))
    lv.update()                           # one diff at the end
```

---

## Chapter 16. Routing and Navigation

```python
def main(page: ft.Page):
    def route_change(_):
        page.views.clear()
        page.views.append(ft.View("/", [
            ft.AppBar(title=ft.Text("Home")),
            ft.ElevatedButton("Settings", on_click=lambda _: page.go("/settings")),
        ]))
        if page.route == "/settings":
            page.views.append(ft.View("/settings", [
                ft.AppBar(title=ft.Text("Settings")),
            ]))
        # Templated route with dynamic segment
        tr = ft.TemplateRoute(page.route)
        if tr.match("/books/:id"):
            page.views.append(ft.View(page.route, [ft.Text(f"Book {tr.id}")]))
        page.update()

    def view_pop(_):
        page.views.pop()
        page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)

ft.run(main)
```

### Useful Bits

- `page.query` — query parameters dict.
- `page.pop_views_until(route, result=...)` + `on_views_pop_until`.
- `ft.run(main, route_url_strategy="hash")` — `/#/foo` URLs (good for static hosting that can't rewrite).
- **Declarative Router** (0.85+) — view-stack navigation integrated with components and hooks.

---

## Chapter 17. State Management

Flet supports several patterns; pick by app size.

### 1. Module-Level / Closure (small apps)

```python
def main(page):
    counter = {"v": 0}
    txt = ft.Text("0")
    def add(_):
        counter["v"] += 1
        txt.value = str(counter["v"])
        page.update()
    page.add(txt, ft.ElevatedButton("+", on_click=add))
```

### 2. Page Session Store (transient, per-user, server-side)

```python
page.session.set("user", {"id": 42})
user = page.session.get("user")
page.session.contains_key("user")
page.session.remove("user")
```

> Lost on server restart. Use for auth state, navigation context.

### 3. Persistent Storage

| API | Backed By | Lifetime |
|---|---|---|
| `page.client_storage` | localStorage (web) / JSON (desktop) / NSUserDefaults (iOS) / SharedPreferences (Android) | Persistent per user |
| `page.shared_preferences` | Same as above (alias name in newer versions) | Persistent per user |
| Files in `FLET_APP_STORAGE_DATA` | App's persistent dir | Persistent |
| Files in `FLET_APP_STORAGE_TEMP` | App's scratch dir | Until cleared |

```python
await page.shared_preferences.set("theme", "dark")
v = await page.shared_preferences.get("theme")
await page.shared_preferences.remove("theme")
```

> ⚠️ Multiple Flet apps share the same store on the device. **Always prefix keys** with `{company}.{product}.`.

### 4. Declarative + Observables (1.0+)

```python
from dataclasses import dataclass, field

@ft.observable
@dataclass
class Todo:
    title: str
    done: bool = False

@ft.component
def TodoItem(todo: Todo):
    return ft.Row([
        ft.Checkbox(value=todo.done,
                    on_change=lambda e: setattr(todo, "done", e.control.value)),
        ft.Text(todo.title),
    ])
```

`@ft.observable` wraps the dataclass so Flet auto-rerenders subscribed components when fields mutate.

### 5. Hooks (1.0+)

```python
@ft.component
def Profile(user_id: str):
    user, set_user = ft.use_state(None)

    def load():
        async def fetch():
            set_user(await api.get_user(user_id))
        return fetch
    ft.use_effect(load, [user_id])

    if user is None:
        return ft.ProgressRing()
    return ft.Text(user.name)
```

Available hooks: `use_state`, `use_effect`, `use_ref`, `use_context` (+ `create_context`), `use_memo`, `use_dialog` (0.85+).

### 6. Third-Party

- **FletX** — GetX-style reactive state management for Flet.

---

## Chapter 18. Theming and Styling

```python
page.theme = ft.Theme(
    color_scheme_seed=ft.Colors.INDIGO,
    use_material3=True,
    font_family="Roboto",
    text_theme=ft.TextTheme(
        body_medium=ft.TextStyle(size=16),
        headline_large=ft.TextStyle(weight=ft.FontWeight.BOLD),
    ),
    appbar_theme=ft.AppBarTheme(bgcolor=ft.Colors.INDIGO_700),
)
page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
page.theme_mode = ft.ThemeMode.SYSTEM        # LIGHT | DARK | SYSTEM
```

### Custom Fonts

```python
page.fonts = {
    "Kanit": "/fonts/Kanit-Bold.ttf",
    "Open Sans": "https://raw.githubusercontent.com/google/fonts/master/ofl/opensans/OpenSans-Regular.ttf",
}
page.theme = ft.Theme(font_family="Kanit")
ft.run(main, assets_dir="assets")
```

### Scoped Themes

Any container has a `theme` and `theme_mode` that override the parent's theme for its subtree.

### Material 3 vs 2

Flet 1.0+ defaults to **Material 3**. To opt out, set `use_material3=False`.

### Adaptive Per-Platform

```python
ft.Switch(adaptive=True)
ft.Slider(adaptive=True)
ft.AlertDialog(adaptive=True, ...)
```

Material on Android/Web/Desktop; Cupertino on iOS.

---

## Chapter 19. Persistence and Storage

See Chapter 17 for client_storage / shared_preferences / session APIs. For raw file I/O on packaged apps:

```python
import os, json
data_dir = os.getenv("FLET_APP_STORAGE_DATA")     # persistent
temp_dir = os.getenv("FLET_APP_STORAGE_TEMP")     # scratch

with open(os.path.join(data_dir, "notes.json"), "w") as f:
    json.dump(notes, f)
```

### Encrypting Sensitive Data

```python
from flet.security import encrypt, decrypt

key = "your-secret-key"     # load from env or secure store
ciphertext = encrypt(json.dumps(token), key)
await page.shared_preferences.set("token", ciphertext)

raw = await page.shared_preferences.get("token")
plaintext = decrypt(raw, key)
```

Backed by Fernet (AES-128 + HMAC) with PBKDF2 key derivation.

---

## Chapter 20. Authentication (OAuth)

Built-in providers: **Google, GitHub, Azure, Auth0**, plus generic `OAuthProvider` for any OIDC.

### GitHub Example

```python
import os
import flet as ft
from flet.auth.providers import GitHubOAuthProvider

def main(page: ft.Page):
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
    page.add(ft.ElevatedButton(
        "Login with GitHub",
        on_click=lambda _: page.login(provider, scope=["public_repo"]),
    ))

ft.run(main, port=8550, view=ft.WEB_BROWSER)
```

### Persisting Tokens

```python
# Save (encrypted)
from flet.security import encrypt
encrypted = encrypt(page.auth.token.to_json(), os.environ["TOKEN_SECRET"])
await page.client_storage.set("auth", encrypted)

# Restore
raw = await page.client_storage.get("auth")
if raw:
    page.login(provider, saved_token=decrypt(raw, os.environ["TOKEN_SECRET"]))
```

### Custom OIDC Provider

```python
from flet.auth import OAuthProvider

provider = OAuthProvider(
    client_id="...", client_secret="...",
    redirect_url="http://localhost:8550/oauth_callback",
    authorization_endpoint="https://oidc.example.com/authorize",
    token_endpoint="https://oidc.example.com/token",
    user_endpoint="https://oidc.example.com/userinfo",
    user_scopes=["openid", "profile", "email"],
    user_id_fn=lambda u: u["sub"],
)
```

### `page.logout()`

Clears `page.auth` and fires `on_logout`.

---

## Chapter 21. Networking, Files, Audio, Video, Maps

### Networking

```python
import httpx

async def fetch_user(user_id):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"https://api.example.com/users/{user_id}")
        r.raise_for_status()
        return r.json()
```

For sync libraries that you can't replace, wrap with `page.run_thread()`:

```python
def long_blocking():
    return some_sync_lib.do_work()

result = await asyncio.get_event_loop().run_in_executor(page.executor, long_blocking)
# or
page.run_thread(long_blocking)
```

### Audio

```python
audio = ft.Audio(src="https://example.com/song.mp3", autoplay=False,
                 on_state_changed=lambda e: print(e.data))
page.services.append(audio)
audio.play()
audio.pause()
audio.seek(30_000)        # ms

# Recording
rec = ft.AudioRecorder()
page.services.append(rec)
rec.start_recording("/tmp/clip.m4a")
rec.stop_recording()
# 0.85+ supports streaming and direct upload
```

### Video

```python
ft.Video(
    playlist=[ft.VideoMedia("https://example.com/clip.mp4")],
    autoplay=True, show_controls=True,
    on_completed=lambda e: ...,
    expand=True,
)
```

### WebView

```python
ft.WebView(url="https://flet.dev", expand=True,
           on_page_started=lambda e: ..., on_page_ended=lambda e: ...)
```

### Maps

```python
# Generic map
ft.Map(
    initial_center=ft.MapLatitudeLongitude(30.0444, 31.2357),
    initial_zoom=11,
    layers=[ft.TileLayer(url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png")],
)

# Google Maps (flet-google-maps package)
```

### Lottie & Rive

```python
ft.Lottie(src="https://assets.../animation.json", repeat=True, animate=True)
ft.Rive(src="https://assets.../riv.riv", animations=["idle"])
```

### Camera (0.81+)

```python
cam = ft.Camera(on_image_captured=lambda e: print(e.data))
page.add(cam)
cam.capture_image()
```

---

# Part V — Packaging & Deployment

## Chapter 22. `flet run` / `flet debug`

### `flet run`

```bash
flet run                       # desktop window (default)
flet run --web                 # browser
flet run -d main.py            # restart on save
flet run --port 8550           # specify port for web
flet run --assets assets       # custom assets dir
```

### `flet debug` (0.80+)

Package and run on a real device or emulator:

```bash
flet devices                                # list connected devices
flet emulators                              # list emulators
flet emulators create my-emulator
flet debug android --device-id <id> -v      # build + push + run with logs
flet debug ios --device-id <udid> -v
```

This is **the** way to test mobile features (sensors, camera, push) before a release build.

---

## Chapter 23. Desktop Packaging (Windows / macOS / Linux)

```bash
flet build macos                              # macOS host required
flet build windows                            # Windows or macOS host (Windows only on Windows)
flet build linux                              # Linux host required (or WSL)
```

### Outputs

| Target | Output | Notes |
|---|---|---|
| `macos` | `build/macos/<name>.app` (and dmg with `--build-dmg`) | Sign + notarize for distribution |
| `windows` | `build/windows/<name>` (folder); `.exe` inside | MSIX/installer is your responsibility |
| `linux` | `build/linux/<name>` | bundle as AppImage / .deb / .rpm via standard tools |

### Common Flags

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

---

## Chapter 24. Mobile Packaging (Android / iOS)

### Host-OS Support Matrix

| Build | macOS | Windows | Linux |
|---|---|---|---|
| `apk` / `aab` | ✅ | ✅ | ✅ |
| `ipa` / `ios-simulator` | ✅ | ✅ (via WSL) | ❌ |

### Android

Prerequisites:
- JDK 17 (auto-installed by Flet to `$HOME/java/<v>`).
- Android SDK (auto-installed to `~/Android/sdk`).
- Release keystore:
  ```bash
  keytool -genkey -v -keystore ~/upload-keystore.jks \
    -keyalg RSA -keysize 2048 -validity 10000 -alias upload
  ```

Configure in `pyproject.toml`:

```toml
[tool.flet.android]
permissions = ["android.permission.INTERNET", "android.permission.CAMERA"]
features = ["android.hardware.camera"]
adaptive_icon_background = "#ffffff"
min_sdk = 24
target_sdk = 34
```

Build:

```bash
flet build apk     # split-per-abi, smaller files
flet build aab     # for Play Store
```

### iOS

Prerequisites:
- macOS host (Apple Silicon needs Rosetta 2: `sudo softwareupdate --install-rosetta --agree-to-license`).
- Xcode 15+ and CocoaPods 1.16+.
- Apple Developer Program membership.
- Provisioning profile + Apple Distribution signing certificate.
- Any binary deps must have iOS wheels on `pypi.flet.dev` (or build via Mobile Forge — see Chapter 26).

Configure:

```toml
[tool.flet.ios]
team_id = "XXXXXXXXXX"
info_plist."NSCameraUsageDescription" = "Capture documents"
info_plist."NSPhotoLibraryUsageDescription" = "Pick photos"
```

Build:

```bash
flet build ipa
flet build ios-simulator       # for the simulator
```

### Build Pipeline (Every Target)

1. Generate Flutter project under `build/flutter` from a template.
2. Apply icons and splash screens. Per-platform icons: `assets/icon_ios.png`, `icon_android.png`, `icon_web.png`, `icon_windows.ico`, `icon_macos.png`. Fallback `assets/icon.png`.
3. Run `serious_python package`: install deps, compile `.py → .pyc`, exclude unused files.
4. Run `flutter build`.
5. Copy outputs to `--output` (default `build/<target>`).

### Console Capture in Built Apps

```python
import os
log_path = os.getenv("FLET_APP_CONSOLE")
# Or, programmatically:
log_path = await ft.StoragePaths().get_console_log_filename()
```

If the app exits with code `100`, Flet opens an in-app scrollable log viewer (great for diagnosing customer-side crashes).

---

## Chapter 25. Web Deployment (Pyodide / FastAPI)

### Static Site (Pyodide / WASM)

```bash
flet build web \
  --base-url "/myapp/" \
  --route-url-strategy hash \
  --web-renderer canvaskit \
  --pwa-background-color "#000" \
  --pwa-theme-color "#F00" \
  --no-cdn                     # bundle Pyodide + CanvasKit locally
```

- Output: `build/web/` — drop into GitHub Pages, S3, Cloudflare Pages, Netlify.
- Deps installed at build time and bundled into `assets/app/app.zip`.
- **Limits**: pure-Python or Pyodide-built wheels only; single browser thread (no CPU work); OAuth limited.
- Serve locally to test: `flet serve` (defaults to <http://localhost:8000>).

### Dynamic Site (FastAPI / ASGI)

```python
# app.py
import flet as ft

def main(page: ft.Page):
    page.add(ft.Text("Hi from FastAPI mode"))

app = ft.run(main, export_asgi_app=True)
```

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# or production
gunicorn -k uvicorn.workers.UvicornWorker -w 4 app:app
```

### Reverse Proxy (nginx)

WebSockets need upgrade headers:

```nginx
location /myapp/ {
  proxy_pass         http://127.0.0.1:8000/;
  proxy_http_version 1.1;
  proxy_set_header   Upgrade $http_upgrade;
  proxy_set_header   Connection "upgrade";
  proxy_set_header   Host $host;
  proxy_set_header   X-Forwarded-Proto $scheme;
}
```

### Embedding in Existing FastAPI

Use the `flet-fastapi` package:

```python
from fastapi import FastAPI
import flet.fastapi as flet_fastapi

api = FastAPI()

@api.get("/api/health")
def health(): return {"ok": True}

api.mount("/app", flet_fastapi.app(my_flet_main))
```

---

## Chapter 26. Binary Packages and Mobile Forge

### `pypi.flet.dev`

A custom PyPI index hosting **pre-built binary wheels for iOS and Android** for ~60+ popular packages: `numpy`, `pandas`, `matplotlib`, `pillow`, `opencv-python`, `cryptography`, `bcrypt`, `pynacl`, `sqlalchemy`, `pymongo`, `gdal`, `shapely`, `pyproj`, etc.

Flet's build pipeline automatically uses this index when packaging for mobile.

### Mobile Forge

For dependencies **not** in the index, use Mobile Forge to build your own wheels for iOS/Android. Pure-Python packages always work without rebuilding.

**Tip:** profile your final mobile bundle. Each native dep adds tens of MB.

---

# Part VI — Production

## Chapter 27. Reference Architecture for a Real App

Imagine **"FieldOps,"** a multi-tenant logistics app: drivers see jobs on mobile, dispatchers manage on web, ops uses desktop dashboards. One Flet codebase.

```
┌──────────────────────────────────────────────────────────────────┐
│                         FieldOps (Flet)                          │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │ iOS / Android│   │ Web (Pyodide │   │ Desktop dashboards   │   │
│  │  field crew │   │ static SPA)  │   │ Win/macOS/Linux      │   │
│  └──────┬──────┘   └──────┬───────┘   └─────────┬────────────┘   │
│         │                 │                     │                │
│         └─────────────────┴─── HTTPS / WS ──────┘                │
│                            │                                     │
└────────────────────────────┼─────────────────────────────────────┘
                             ↓
                   ┌──────────────────┐
                   │ Backend (FastAPI)│  ← REST + WebSocket
                   ├──────────────────┤
                   │ Postgres │ Redis │
                   └──────────────────┘
```

### Layout the Code

```
fieldops/
├── pyproject.toml
├── src/
│   ├── main.py                  # ft.run entry — chooses route
│   ├── routes/
│   │   ├── home.py              # Home view
│   │   ├── job_list.py          # /jobs
│   │   ├── job_detail.py        # /jobs/:id
│   │   └── settings.py
│   ├── components/              # @ft.component reusable bits
│   │   ├── app_shell.py
│   │   ├── job_card.py
│   │   └── connection_indicator.py
│   ├── state/
│   │   ├── store.py             # @ft.observable models
│   │   └── api.py               # httpx-based API client
│   ├── theme.py
│   └── utils.py
└── assets/
    ├── icon.png, icon_ios.png, icon_android.png, icon_web.png
    └── fonts/
```

### Single-File Routing Hub

```python
# main.py
import flet as ft
from routes import home, job_list, job_detail, settings
from theme import light_theme, dark_theme

async def main(page: ft.Page):
    page.title = "FieldOps"
    page.theme = light_theme
    page.dark_theme = dark_theme
    page.theme_mode = ft.ThemeMode.SYSTEM

    def route_change(_):
        page.views.clear()
        tr = ft.TemplateRoute(page.route)

        if page.route == "/" or tr.match("/"):
            page.views.append(home.view(page))
        elif page.route == "/jobs":
            page.views.append(job_list.view(page))
        elif tr.match("/jobs/:id"):
            page.views.append(job_detail.view(page, tr.id))
        elif page.route == "/settings":
            page.views.append(settings.view(page))
        else:
            page.views.append(ft.View(page.route, [ft.Text("404")]))
        page.update()

    page.on_route_change = route_change
    page.on_view_pop = lambda _: page.go(page.views[-2].route) if len(page.views) > 1 else None
    page.go(page.route or "/")

ft.run(main)
```

### Cross-Platform Considerations

- **Web (Pyodide)**: avoid heavy CPU; offload to backend. OAuth requires the dynamic FastAPI mode.
- **Mobile**: use `adaptive=True`; respect `SafeArea`; mind permission prompts.
- **Desktop**: enable `page.window.title_bar_hidden=True` for custom title bars.
- **All**: persist auth via `client_storage` (encrypted), keep keys per-tenant.

---

## Chapter 28. Performance Best Practices

| Rule | Why |
|---|---|
| Async everything I/O — never `time.sleep` or sync HTTP in handlers. | Frees the UI thread. |
| Use `ListView` / `GridView` (with `item_extent`) for >200 items. | Virtualization saves RAM and frame time. |
| `with ft.context.disable_auto_update():` for batch ops. | One diff instead of N. |
| Prefer `control.update()` over `page.update()`. | Smaller diff. |
| Chunk huge inserts: `if i % 500 == 0: page.update()`. | Progressive rendering. |
| Strip secrets from source — Pyodide bundles your `.py`. | Anyone can read packaged web source. |
| In custom controls, override `will_unmount()` to cancel timers/tasks. | Avoid leaks. |
| Use scoped themes on heavy subtrees rather than swapping `page.theme`. | Smaller diffs. |
| Test on real devices early via `flet debug`. | Desktop preview ≠ mobile. |
| Avoid `Column` for thousands of children. | Layout cost is O(N). |

### MVU Pattern

Flet works well with **Model-View-Update**:

```
Model    ──▶  observable @dataclass
View     ──▶  @ft.component reading model
Update   ──▶  event handlers mutating model fields
```

Components rerender automatically when observed fields change.

---

## Chapter 29. Testing and Debugging

- `flet doctor` — environment sanity check.
- `flet run -d main.py` — restart on file save.
- `flet debug` — package + run on device with logs streamed to terminal.
- Console capture (built apps): `os.getenv("FLET_APP_CONSOLE")` or `await ft.StoragePaths().get_console_log_filename()`.
- Standard Python `logging` works; in built apps, logs go to the captured console.
- Unit-test models and services like any Python code (pytest).
- E2E UI testing is on the **roadmap** but not yet first-class. Community workarounds:
  - Drive Flutter integration tests via the Dart side.
  - Stand up the FastAPI mode and use Playwright/Puppeteer.

---

## Chapter 30. Security and Secrets

- **Never hardcode secrets** in source — Pyodide builds bundle the `.py` files visibly.
- Inject via env vars at server start (FastAPI mode) or fetch from the backend at runtime.
- Encrypt anything sensitive before `client_storage` / `shared_preferences`:
  ```python
  from flet.security import encrypt, decrypt
  ```
- Multiple Flet apps share the device storage — **prefix keys** with `{company}.{product}.`.
- Lock OAuth `redirect_url` to your real production hosts.
- Use `https://` everywhere; in dev, use `http://localhost:<port>` only.
- Treat the Flet client as untrusted — validate everything server-side.

---

# Part VII — Reference

## Chapter 31. Full Controls Catalog

### Layout
Container · Row · Column · Stack · GridView · ListView · PageView · ResponsiveRow · SafeArea · Card · Divider · VerticalDivider · ExpansionTile · ExpansionPanel · ExpansionPanelList · Tabs / Tab · AppBar · BottomAppBar · NavigationBar · NavigationDestination · NavigationRail · NavigationRailDestination · NavigationDrawer · MenuBar · MenuItemButton · SubmenuButton · FloatingActionButton · Page · View · Pagelet · MultiView

### Display
Text · Markdown · Icon · Image · CircleAvatar · Badge · Chip · ProgressBar · ProgressRing · Banner · SnackBar · Tooltip · Placeholder · Shimmer

### Input / Buttons
TextField · ElevatedButton (alias `Button`) · TextButton · FilledButton · FilledTonalButton · OutlinedButton · IconButton · FilledIconButton · FilledTonalIconButton · OutlinedIconButton · Checkbox · Radio · RadioGroup · Switch · Slider · RangeSlider · Dropdown · AutoComplete · SearchBar · SegmentedButton · DatePicker · DateRangePicker · TimePicker · FilePicker · ColorPicker (0.81+) · Camera (0.81+) · CodeEditor (0.81+)

### Dialogs
AlertDialog · BottomSheet · CupertinoAlertDialog · CupertinoActionSheet · CupertinoBottomSheet

### Charts
BarChart · LineChart · PieChart · ScatterChart · MatplotlibChart · PlotlyChart

### Cupertino
CupertinoButton · CupertinoFilledButton · CupertinoTintedButton · CupertinoIconButton · CupertinoCheckbox · CupertinoSwitch · CupertinoSlider · CupertinoRadio · CupertinoActivityIndicator · CupertinoTextField · CupertinoDatePicker · CupertinoTimerPicker · CupertinoSegmentedButton · CupertinoSlidingSegmentedButton · CupertinoListTile · CupertinoNavigationBar · CupertinoAppBar · CupertinoAlertDialog · CupertinoActionSheet · CupertinoBottomSheet · CupertinoContextMenu · CupertinoDialogAction

### Animation
AnimatedContainer · AnimatedSwitcher · Hero (0.81+) · Animation · AnimationCurve

### Specialized
Audio · AudioRecorder · Video · WebView · Map · Lottie · Rive · Canvas

### Interaction
GestureDetector · Draggable · DragTarget · InteractiveViewer · KeyboardListener · SelectionArea · Dismissible · ReorderableListView · ReorderableDragHandle · WindowDragArea · TransparentPointer · MergeSemantics · Semantics · ShaderMask · AutofillGroup · RotatedBox · Screenshot

---

## Chapter 32. Page API Reference

### Properties

| Category | Property |
|---|---|
| Identity | `name`, `route`, `query`, `url` |
| Visual | `title`, `theme`, `dark_theme`, `theme_mode`, `bgcolor`, `padding`, `scroll`, `fonts` |
| Window (desktop) | `window` (object: `width`, `height`, `min_width`, `min_height`, `center()`, `maximized`, `visible`, `title_bar_hidden`, …) |
| Session | `session`, `auth`, `client_ip`, `client_user_agent` |
| Platform flags | `platform`, `platform_brightness`, `debug`, `web`, `wasm`, `pwa`, `multi_view` |
| Storage | `client_storage`, `shared_preferences` |
| Layout slots | `controls`, `views`, `overlay`, `appbar`, `bottom_appbar`, `navigation_bar`, `floating_action_button`, `drawer`, `end_drawer` |
| Concurrency | `executor`, `loop`, `pubsub` |
| Services (1.0+) | `services` (list) — for FilePicker/Audio/etc. |

### Methods

```
update()  add(*controls)  remove(*controls)  clean()
go(route)  push_route(route, **kwargs)  navigate(route)
pop_views_until(route, result)
run_task(coro_fn, *args)  run_thread(fn, *args)
show_dialog(dialog)  pop_dialog()
open(banner_or_snackbar)  close(control)
login(provider, **opts)  logout()
error(msg)  get_control(id)  get_device_info()
launch_url(url, web_window_name=None, web_popup_window=None, ...)
```

---

## Chapter 33. Page Events Reference

```
on_resize                           → e (window/viewport size changed)
on_close                            → session expired
on_disconnect / on_connect          → web client disconnected/connected
on_route_change                     → page.go() or browser nav
on_view_pop                         → back-press on a View
on_views_pop_until                  → pop_views_until reached target
on_keyboard_event                   → KeyboardEvent (key, shift, ctrl, alt, meta)
on_login / on_logout                → OAuth flow result
on_error                            → unhandled exception
on_locale_change                    → OS locale change (0.81+)
on_platform_brightness_change       → light/dark mode toggle
on_app_lifecycle_state_change       → mobile foreground/background
on_multi_view_add / on_multi_view_remove
on_scroll                           → page-level scroll
on_window_event                     → desktop window events (close, focus, …)
```

---

## Chapter 34. Plugins / Extensions Catalog

| Package | Purpose |
|---|---|
| `flet[all]` | Meta-package; pulls common extras |
| `flet-audio` | Audio playback |
| `flet-audio-recorder` | Microphone recording |
| `flet-video` | Video player |
| `flet-webview` | Embedded WebView |
| `flet-lottie` | Lottie JSON animations |
| `flet-rive` | Rive animations |
| `flet-map` | Generic interactive map |
| `flet-google-maps` | Google Maps tiles |
| `flet-flashlight` | Toggle device torch |
| `flet-geolocator` | GPS / heading |
| `flet-permission-handler` | Runtime permissions |
| `flet-fastapi` | Embed Flet inside FastAPI |
| `flet-mobile-ads` | AdMob banners + interstitials |
| `flet-charts` | Extended chart types |
| `flet-sensor-*` | accelerometer / gyroscope / barometer / magnetometer |
| `FletX` (community) | GetX-style reactive state mgmt |

---

## Chapter 35. CLI Reference

```
flet --version                       # show CLI version
flet doctor                          # environment sanity check

flet create <name>                   # scaffold a project

flet run [FILE]                      # run app (desktop default)
  --web                              # open in browser
  -d / --hot-reload                  # restart on save
  --port PORT
  --assets DIR

flet serve [FILE]                    # serve as ASGI on local dev port

flet build TARGET [opts]             # build for target
  TARGET ∈ apk | aab | ipa | ios-simulator | macos | windows | linux | web

flet debug TARGET [opts]             # package + run on device/emulator
flet devices                         # list connected devices
flet emulators                       # manage emulators
flet emulators create <name>
flet pack                            # legacy desktop packaging (PyInstaller)
```

`flet build` flags (subset): `--project`, `--product`, `--artifact`, `--org`, `--bundle-id`, `--build-version`, `--build-number`, `--output`, `--module-name`, `--splash-color`, `--splash-dark-color`, `--no-android-splash`, `--no-ios-splash`, `--permissions`, `--arch`, `--deep-linking-scheme`, `--deep-linking-host`, `--exclude`, `--compile-app`, `--compile-packages`, `--cleanup-app-files`, `--flutter-build-args`, `--clear-cache`, `--verbose`, `--yes`, `--web-renderer`, `--route-url-strategy`, `--pwa-background-color`, `--pwa-theme-color`, `--no-cdn`, `--info-plist KEY=VALUE`, `--build-dmg`.

---

## Chapter 36. `pyproject.toml` / `[tool.flet]` Reference

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
company   = "Example Inc."
copyright = "© 2026 Example"
permissions = ["location", "microphone"]

[tool.flet.app]
path = "src"
module = "main"

[tool.flet.android]
permissions = ["android.permission.INTERNET"]
features = ["android.hardware.camera"]
adaptive_icon_background = "#ffffff"
min_sdk = 24
target_sdk = 34

[tool.flet.ios]
team_id = "XXXXXXXXXX"
info_plist."NSCameraUsageDescription" = "Capture documents"
info_plist."NSPhotoLibraryUsageDescription" = "Pick photos"

[tool.flet.web]
base_url = "/myapp/"
route_url_strategy = "hash"            # path | hash
web_renderer = "canvaskit"             # html | canvaskit | auto

[tool.flet.splash]
color = "#fff"
dark_color = "#222"
android = false
ios = true
web = true

[tool.flet.compile]
app = true
packages = true

[tool.flet.flutter.pubspec.dependencies]
some_pub_pkg = "^1.2.3"
```

---

## Chapter 37. Roadmap & Recent Releases

### Roadmap (2026, from `flet.dev/roadmap`)

| Status | Item |
|---|---|
| In progress (1.0 GA) | Long-term maintainability via dataclass-based controls + auto-generated docs |
| In progress | Optimized binary protocol (eliminates base64 conversions) |
| Planned | Community gallery for apps, extensions, education |
| Planned | **FletPad** in-browser playground |
| Planned | End-to-end UI testing |
| Planned | Binary package test suite |
| Planned | **MCP server for Flet** (AI integrations) |
| Planned | **Flet Packaging and Publishing Service (FPS)** |
| Planned | PyCon US 2026 attendance |

### Release Highlights (2025–2026)

| Date | Release | Highlights |
|---|---|---|
| Apr 2026 | **0.84.0** | Docs migrated to Docusaurus + CrocoDocs; 466 examples migrated to standalone projects; build templates moved to monorepo. |
| Mar 2026 | **0.83.0** | 6.7× faster control diffing; declarative field validation via `Annotated`; desktop binaries moved from PyPI to GitHub Releases; customizable scrollbars. |
| Mar 2026 | 0.82.2 | Build-template UTF-8 fixes; lazy-loaded auth deps for web/Pyodide startup. |
| Feb 2026 | **0.81.0** | New: Camera, CodeEditor, PageView, ColorPicker; **Hero animations**; Matrix4 transforms; clipboard for images/files; platform locale support. |
| Dec 2025 | **0.80.0 (Flet 1.0 Beta)** | Imperative + declarative co-existence; new docs; integration tests; **`flet debug` CLI**. |
| Dec 2025 | Sensors & system services | 10 new services: accelerometer, barometer, gyroscope, magnetometer, battery, connectivity, screen brightness. |
| 2025 | Declarative UI launch | `@ft.component`, hooks (`use_state`, `use_effect`, `use_ref`, `use_context`, `use_memo`), `@ft.observable`. |
| 2025 | Flet 1.0 Alpha | Re-architecture: dataclass controls, MessagePack protocol, services architecture. |
| 2024 | 0.25 | Custom packaging (replaces Kivy); Python 3.12 runtime; `pypi.flet.dev`; `Button` alias of `ElevatedButton`; redesigned `Badge`; AdMob support. |

Active dev (May 2026): `0.85.0.devN` — declarative Router, `page.pop_views_until()`, scrollable `ResponsiveRow`, `use_dialog` hook, scrollable/pinned NavigationRail, AudioRecorder streaming/upload, video playlist enhancements.

---

## Chapter 38. Comparison: Flet vs Streamlit / Reflex / NiceGUI / Dear PyGui

| Framework | UI tech | Web | Mobile | Desktop | Realtime | Best at |
|---|---|---|---|---|---|---|
| **Flet** | Flutter | ✅ (Pyodide or FastAPI) | ✅ iOS/Android native | ✅ Win/macOS/Linux | ✅ | One codebase, six platforms; rich UI |
| **Streamlit** | HTML re-render | ✅ | ❌ | ❌ | partial | Data dashboards, ML demos |
| **Gradio** | HTML | ✅ | ❌ | ❌ | partial | ML model UIs |
| **Reflex** | React + FastAPI | ✅ | ❌ | ❌ | ✅ | React-style web apps in Python |
| **NiceGUI** | HTML/Quasar | ✅ | ❌ | ❌ | ✅ | FastAPI dashboards/admin |
| **PyWebIO** | HTML | ✅ | ❌ | ❌ | ✅ | Quick interactive forms |
| **Dear PyGui** | Custom GPU UI | ❌ | ❌ | ✅ | ✅ | Performant local desktop tools |
| **Anvil** | Custom (hosted) | ✅ | ❌ | ❌ | ✅ | SaaS apps with cloud backend |

**Pick Flet when**: you need a real cross-platform app with one Python codebase, native-quality UI, and the ability to ship to mobile stores.
**Pick Streamlit/Gradio when**: you need a quick data UI and can live with a single-page-app dashboard model.
**Pick Reflex/NiceGUI when**: web-only is fine and you want React/Quasar look.

---

## Chapter 39. Troubleshooting & Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| UI freezes during operation | `time.sleep` or sync HTTP in handler | Use `asyncio.sleep` / `httpx.AsyncClient` or wrap with `page.run_thread()` |
| `page.dialog = ...` no longer works | Pre-1.0 dialog API removed | Use `page.show_dialog(dlg)` / `page.pop_dialog()` |
| Mobile build fails on a binary dep | No iOS/Android wheel on `pypi.flet.dev` | Replace with pure-Python alternative or build via Mobile Forge |
| Pyodide app slow / blocks | Single-threaded browser CPU | Move heavy work to backend (FastAPI mode) |
| Storage values appearing in another app | Multiple Flet apps share device store | **Always** prefix keys with `{company}.{product}.` |
| `flet build ipa` fails on Linux | Not supported | Build on macOS host |
| OAuth `redirect_url` mismatch | Wrong host/port | Match exactly the URL registered with provider, including scheme & port |
| Web app behind nginx loses WebSocket | Missing upgrade headers | Add `Upgrade` and `Connection "upgrade"` proxy headers |
| Custom font not loading | `assets_dir` not set | `ft.run(main, assets_dir="assets")` |
| ListView scrolling slow | `Column` used instead | Switch to `ListView` / `GridView` with `item_extent` |
| Hot reload not picking up changes | Asset files (not .py) cached | Stop and re-run `flet run -d`; clear `build/` cache |
| Packaged app exits immediately | Crash in Python; check log | `os.getenv("FLET_APP_CONSOLE")` for log path; exit code 100 opens in-app log viewer |
| `flet debug` can't see device | Driver / authorization | `adb devices` (Android) or trust dialog on iOS; `flet doctor` |
| Material 3 widgets look "wrong" | Using `use_material3=False` somewhere | Check theme + scoped themes; default is M3 in 1.0+ |
| Bundle is huge | Includes unused deps | Trim deps; use `[tool.flet] exclude` and `--exclude` flags |

---

## Chapter 40. Glossary

| Term | Meaning |
|---|---|
| **Page** | The user's session root — one per connected client. Has controls, views, theme, storage. |
| **View** | A page-stack entry (think browser-history page). Push/pop with `page.go()` / `page.views.pop()`. |
| **Control** | Any UI element. Composed in a tree under a `Page` or `View`. |
| **Service** | Non-visual control attached to `page.services` (FilePicker, Audio, AudioRecorder…). |
| **Component** | A function decorated with `@ft.component` that returns a control tree, with hooks. |
| **Observable** | A `@ft.observable` dataclass; mutating fields rerenders subscribed components. |
| **Hook** | `use_state`, `use_effect`, `use_ref`, `use_context`, `use_memo`, `use_dialog`. |
| **Pyodide** | CPython compiled to WebAssembly — runs in the browser, no server. |
| **Mobile Forge** | Tool for building custom binary wheels for iOS/Android beyond what `pypi.flet.dev` ships. |
| **`pypi.flet.dev`** | Flet-maintained index of pre-built mobile wheels (numpy, pandas, pillow, …). |
| **`serious_python`** | Library that bundles a Python interpreter inside Flutter apps. |
| **MessagePack** | Binary serialization between Python ↔ Dart in Flet 1.0+ (replaces JSON+base64). |
| **Adaptive control** | Auto-switches Material/Cupertino based on platform when `adaptive=True`. |
| **TemplateRoute** | Route matcher: `ft.TemplateRoute("/users/:id").match("/users/:id")` exposes `.id`. |

---

# Appendix A — Complete App: A Notes Application

A note-taking app with theming, routes, FilePicker (export), and `shared_preferences` persistence. Mixes imperative routing with declarative components — typical for real Flet apps.

```python
# main.py
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import List

import flet as ft


# ------------- Persistent model ---------------------------------------------
@ft.observable
@dataclass
class Note:
    id: str
    title: str
    body: str = ""

@ft.observable
@dataclass
class AppState:
    notes: List[Note] = field(default_factory=list)
    dark: bool = False

STORAGE_KEY = "com.example.notes.state.v1"


async def load_state(page: ft.Page) -> AppState:
    raw = await page.shared_preferences.get(STORAGE_KEY)
    if not raw:
        return AppState()
    data = json.loads(raw)
    return AppState(
        notes=[Note(**n) for n in data.get("notes", [])],
        dark=data.get("dark", False),
    )


async def save_state(page: ft.Page, state: AppState):
    payload = json.dumps({
        "notes": [n.__dict__ for n in state.notes],
        "dark": state.dark,
    })
    await page.shared_preferences.set(STORAGE_KEY, payload)


# ------------- Components ---------------------------------------------------
@ft.component
def NoteRow(note: Note, on_open, on_delete):
    return ft.ListTile(
        title=ft.Text(note.title or "(untitled)", weight=ft.FontWeight.BOLD),
        subtitle=ft.Text(note.body[:80], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        trailing=ft.IconButton(ft.Icons.DELETE, on_click=lambda _: on_delete(note)),
        on_click=lambda _: on_open(note),
    )


@ft.component
def HomeView(state: AppState, on_open, on_new, on_delete, on_export, on_toggle_theme):
    return ft.View(
        "/",
        controls=[
            ft.AppBar(
                title=ft.Text("My Notes"),
                actions=[
                    ft.IconButton(
                        ft.Icons.DARK_MODE if not state.dark else ft.Icons.LIGHT_MODE,
                        on_click=lambda _: on_toggle_theme(),
                    ),
                    ft.IconButton(ft.Icons.DOWNLOAD, on_click=lambda _: on_export()),
                ],
            ),
            ft.ListView(
                expand=True,
                controls=[NoteRow(n, on_open, on_delete) for n in state.notes]
                or [ft.Text("No notes yet — tap + to add one.", italic=True)],
            ),
        ],
        floating_action_button=ft.FloatingActionButton(
            icon=ft.Icons.ADD, on_click=lambda _: on_new()
        ),
    )


# ------------- App ----------------------------------------------------------
async def main(page: ft.Page):
    page.title = "Notes"
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO, use_material3=True)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)

    state = await load_state(page)
    page.theme_mode = ft.ThemeMode.DARK if state.dark else ft.ThemeMode.LIGHT

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def persist():
        await save_state(page, state)

    def new_note():
        n = Note(id=str(uuid.uuid4()), title="New note")
        state.notes.append(n)
        page.run_task(persist)
        page.go(f"/note/{n.id}")

    def delete_note(n: Note):
        state.notes.remove(n)
        page.run_task(persist)
        page.update()

    def open_note(n: Note):
        page.go(f"/note/{n.id}")

    def toggle_theme():
        state.dark = not state.dark
        page.theme_mode = ft.ThemeMode.DARK if state.dark else ft.ThemeMode.LIGHT
        page.run_task(persist)
        page.update()

    async def export_notes():
        result = await file_picker.save_file_async(
            dialog_title="Export notes",
            file_name="notes.json",
            allowed_extensions=["json"],
        )
        if result:
            with open(result, "w") as f:
                json.dump([n.__dict__ for n in state.notes], f, indent=2)
            page.open(ft.SnackBar(ft.Text(f"Exported {len(state.notes)} notes")))

    def route_change(_):
        page.views.clear()
        page.views.append(
            HomeView(state, open_note, new_note, delete_note,
                     lambda: page.run_task(export_notes), toggle_theme)
        )

        tr = ft.TemplateRoute(page.route)
        if tr.match("/note/:id"):
            note = next((n for n in state.notes if n.id == tr.id), None)
            if note:
                title_field = ft.TextField(label="Title", value=note.title, autofocus=True)
                body_field = ft.TextField(
                    label="Body", value=note.body, multiline=True, min_lines=10, expand=True
                )

                def save_and_back(_):
                    note.title = title_field.value
                    note.body = body_field.value
                    page.run_task(persist)
                    page.go("/")

                page.views.append(
                    ft.View(
                        f"/note/{note.id}",
                        controls=[
                            ft.AppBar(
                                title=ft.Text("Edit"),
                                leading=ft.IconButton(
                                    ft.Icons.ARROW_BACK, on_click=save_and_back
                                ),
                            ),
                            ft.Column([title_field, body_field], expand=True, spacing=12),
                        ],
                    )
                )
        page.update()

    def view_pop(_):
        page.views.pop()
        page.go(page.views[-1].route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route or "/")


ft.run(main)
```

### Run / Package

```bash
flet run main.py                                # desktop
flet run --web main.py                          # browser
flet build apk                                  # Android
flet build ipa                                  # iOS (macOS host + Apple Dev account)
flet build web --route-url-strategy hash        # static site for GitHub Pages
flet build macos                                # macOS .app
flet build windows                              # Windows .exe
flet build linux                                # Linux bundle
```

You now have a real, multi-platform app: theming, routing, persistent storage, file export, all from one Python file.

— *End of Handbook* —

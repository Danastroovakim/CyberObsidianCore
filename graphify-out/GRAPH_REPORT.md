# Graph Report - CyberObsidianCore  (2026-11-14)

## Corpus Check
- 8 files · ~18,764 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 4, .toml 1)

## Summary
- 320 nodes · 744 edges · 12 communities (7 shown, 5 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 63 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e0cd2a83`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- core_engine.py
- CyberObsidianMainWindow
- UltimateDownloaderModule
- BootstrapperDialog
- FramelessTitleBar
- LocalAILabModule
- MediaStudioModule
- UniversalConverterModule
- AsyncTaskWorker
- HoloCard

## God Nodes (most connected - your core abstractions)
1. `CyberObsidianMainWindow` - 37 edges
2. `resolve_tool()` - 36 edges
3. `LocalAILabModule` - 32 edges
4. `MediaStudioModule` - 31 edges
5. `HoloCard` - 30 edges
6. `UniversalConverterModule` - 29 edges
7. `TaskSpec` - 26 edges
8. `BatchProcessEngine` - 24 edges
9. `UltimateDownloaderModule` - 21 edges
10. `get_bin_dir()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `LocalAILabModule` --uses--> `OutputDirectoryManager`  [INFERRED]
  mod_ai_lab.py → core_engine.py
- `UniversalConverterModule` --uses--> `OutputDirectoryManager`  [INFERRED]
  mod_converter.py → core_engine.py
- `UltimateDownloaderModule` --uses--> `OutputDirectoryManager`  [INFERRED]
  mod_downloader.py → core_engine.py
- `MediaStudioModule` --uses--> `OutputDirectoryManager`  [INFERRED]
  mod_studio.py → core_engine.py
- `OutputDirectoryBar` --uses--> `OutputDirectoryManager`  [INFERRED]
  ui_cyber_widgets.py → core_engine.py

## Import Cycles
- None detected.

## Communities (12 total, 5 thin omitted)

### Community 0 - "core_engine.py"
Cohesion: 0.08
Nodes (23): bundle_portable_distribution(), copy_tool_with_companions(), detect_gpu_encoders(), elevate_to_admin(), get_base_dir(), get_bin_dir(), get_tools_status(), _heal_7zip_in_bin() (+15 more)

### Community 2 - "UltimateDownloaderModule"
Cohesion: 0.09
Nodes (9): build_cookie_cli_args(), CookieAssistantDialog, find_running_browser_exe(), get_runtime_cookie_copy_path(), get_universal_cached_cookies_path(), gracefully_close_browser(), UltimateDownloaderModule, UrlProbeWorker (+1 more)

### Community 3 - "BootstrapperDialog"
Cohesion: 0.11
Nodes (3): AutoBootstrapperThread, BootstrapperDialog, NeonProgressBar

### Community 4 - "FramelessTitleBar"
Cohesion: 0.08
Nodes (6): animate_widget_fade_in(), CyberEmblemWidget, CyberGaugeWidget, CyberWaveformHUD, draw_obsidian_crystal(), FramelessTitleBar

### Community 5 - "LocalAILabModule"
Cohesion: 0.09
Nodes (3): TaskSpec, LocalAILabModule, native_img_job()

### Community 9 - "AsyncTaskWorker"
Cohesion: 0.14
Nodes (3): AsyncTaskWorker, _decode_console_bytes(), RegexStreamParser

### Community 10 - "HoloCard"
Cohesion: 0.10
Nodes (5): _clean_text(), sanitize_ui_emojis(), DropZoneBanner, HoloCard, OutputDirectoryBar

## Knowledge Gaps
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CyberObsidianMainWindow` connect `CyberObsidianMainWindow` to `core_engine.py`, `UltimateDownloaderModule`, `BootstrapperDialog`, `FramelessTitleBar`, `LocalAILabModule`, `MediaStudioModule`, `UniversalConverterModule`, `HoloCard`?**
  _High betweenness centrality (0.158) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `CyberObsidianMainWindow` (e.g. with `BatchProcessEngine` and `TaskSpec`) actually correct?**
  _`CyberObsidianMainWindow` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `core_engine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07863849765258216 - nodes in this community are weakly interconnected._
- **Why does `HoloCard` connect `HoloCard` to `core_engine.py`, `CyberObsidianMainWindow`, `UltimateDownloaderModule`, `LocalAILabModule`, `MediaStudioModule`, `UniversalConverterModule`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `LocalAILabModule` (e.g. with `CyberObsidianMainWindow` and `BatchProcessEngine`) actually correct?**
  _`LocalAILabModule` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Should `CyberObsidianMainWindow` be split into smaller, more focused modules?**
  _Cohesion score 0.08901515151515152 - nodes in this community are weakly interconnected._
- **Why does `MediaStudioModule` connect `MediaStudioModule` to `core_engine.py`, `CyberObsidianMainWindow`, `HoloCard`, `LocalAILabModule`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
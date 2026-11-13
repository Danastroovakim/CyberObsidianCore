# Graph Report - CyberObsidianCore  (2026-11-09)

## Corpus Check
- 8 files · ~17,072 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 3, .toml 1, .lnk 1)

## Summary
- 297 nodes · 670 edges · 12 communities (6 shown, 6 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- core_engine.py
- CyberObsidianMainWindow
- UltimateDownloaderModule
- BootstrapperDialog
- FramelessTitleBar
- resolve_tool
- MediaStudioModule
- LocalAILabModule
- UniversalConverterModule
- AsyncTaskWorker
- HoloCard

## God Nodes (most connected - your core abstractions)
1. `resolve_tool()` - 33 edges
2. `CyberObsidianMainWindow` - 30 edges
3. `MediaStudioModule` - 30 edges
4. `UniversalConverterModule` - 28 edges
5. `TaskSpec` - 25 edges
6. `BatchProcessEngine` - 24 edges
7. `LocalAILabModule` - 23 edges
8. `HoloCard` - 22 edges
9. `UltimateDownloaderModule` - 20 edges
10. `BootstrapperDialog` - 15 edges

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

## Communities (12 total, 6 thin omitted)

### Community 0 - "core_engine.py"
Cohesion: 0.08
Nodes (18): bundle_portable_distribution(), copy_tool_with_companions(), detect_gpu_encoders(), elevate_to_admin(), get_base_dir(), get_bin_dir(), _heal_7zip_in_bin(), is_admin() (+10 more)

### Community 2 - "UltimateDownloaderModule"
Cohesion: 0.10
Nodes (7): CookieAssistantDialog, find_running_browser_exe(), get_universal_cached_cookies_path(), gracefully_close_browser(), UltimateDownloaderModule, UrlProbeWorker, verify_cookie_file_authenticity()

### Community 3 - "BootstrapperDialog"
Cohesion: 0.12
Nodes (4): AutoBootstrapperThread, get_tools_status(), refresh_system_path_from_registry(), BootstrapperDialog

### Community 4 - "FramelessTitleBar"
Cohesion: 0.09
Nodes (5): CyberEmblemWidget, CyberGaugeWidget, CyberWaveformHUD, FramelessTitleBar, NeonProgressBar

### Community 5 - "resolve_tool"
Cohesion: 0.17
Nodes (5): resolve_tool(), TaskSpec, native_img_job(), build_cookie_cli_args(), get_runtime_cookie_copy_path()

### Community 10 - "HoloCard"
Cohesion: 0.12
Nodes (3): DropZoneBanner, HoloCard, OutputDirectoryBar

## Knowledge Gaps
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CyberObsidianMainWindow` connect `CyberObsidianMainWindow` to `core_engine.py`, `UltimateDownloaderModule`, `BootstrapperDialog`, `resolve_tool`, `UniversalConverterModule`, `HoloCard`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `CyberObsidianMainWindow` (e.g. with `BatchProcessEngine` and `TaskSpec`) actually correct?**
  _`CyberObsidianMainWindow` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `core_engine.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07987711213517665 - nodes in this community are weakly interconnected._
- **Why does `MediaStudioModule` connect `MediaStudioModule` to `core_engine.py`, `CyberObsidianMainWindow`, `HoloCard`, `resolve_tool`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `MediaStudioModule` (e.g. with `BatchProcessEngine` and `OutputDirectoryManager`) actually correct?**
  _`MediaStudioModule` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Should `CyberObsidianMainWindow` be split into smaller, more focused modules?**
  _Cohesion score 0.0855614973262032 - nodes in this community are weakly interconnected._
- **Why does `UniversalConverterModule` connect `UniversalConverterModule` to `core_engine.py`, `CyberObsidianMainWindow`, `HoloCard`, `resolve_tool`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
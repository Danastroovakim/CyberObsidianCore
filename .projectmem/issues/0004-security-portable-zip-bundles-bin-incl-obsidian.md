# #0004 Security: portable ZIP bundles ./bin incl. obsidian_cookies*.txt; 7z password shown in CLI HUD; tarfile.extractall without filter

- 2026-11-09T15:49:30Z `issue`: Security: portable ZIP bundles ./bin incl. obsidian_cookies*.txt; 7z password shown in CLI HUD; tarfile.extractall without filter [core_engine.py:771]
- 2026-11-09T16:04:30Z `fix`: Excluded *cookies*.txt from portable ZIP bundle, masked -p password in CLI preview/stream logs, and added filter='data' to tarfile.extractall [core_engine.py:773]

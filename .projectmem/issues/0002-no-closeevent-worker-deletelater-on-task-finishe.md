# #0002 No closeEvent; worker deleteLater on task_finished emitted inside run(); probe_worker overwritten while running: QThread destroyed while running

- 2026-11-09T15:49:30Z `issue`: No closeEvent; worker deleteLater on task_finished emitted inside run(); probe_worker overwritten while running: QThread destroyed while running [core_engine.py:1092]
- 2026-11-09T16:04:24Z `fix`: Bound worker.deleteLater to QThread.finished with parent=self, added MainWindow.closeEvent thread/process cleanup, and guarded probe_worker with isRunning() check [core_engine.py:1095]

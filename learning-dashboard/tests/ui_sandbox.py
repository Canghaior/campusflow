"""为浏览器验证提供隔离的学习记录，避免污染真实进度。"""
import importlib.util
import tempfile
from pathlib import Path

script = Path(__file__).resolve().parents[1] / "server.py"
spec = importlib.util.spec_from_file_location("dashboard_ui_test", script)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
progress_text = dashboard.PROGRESS.read_text(encoding="utf-8")
plan_text = dashboard.PLAN.read_text(encoding="utf-8")

with tempfile.TemporaryDirectory(prefix="campusflow-dashboard-ui-test-") as directory:
    sandbox = Path(directory).resolve()
    assert sandbox.is_relative_to(Path(tempfile.gettempdir()).resolve())
    dashboard.ROOT = sandbox
    dashboard.PROGRESS = sandbox / "LEARNING_PROGRESS.md"
    dashboard.PLAN = sandbox / "LEARNING_PLAN.md"
    dashboard.JOURNAL = sandbox / "LEARNING_JOURNAL.json"
    dashboard.PROGRESS.write_text(progress_text, encoding="utf-8")
    dashboard.PLAN.write_text(plan_text, encoding="utf-8")
    server = dashboard.ThreadingHTTPServer(("127.0.0.1", 8766), dashboard.Handler)
    server.csrf_token = "isolated-browser-test-token"
    print("UI test sandbox: http://127.0.0.1:8766/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

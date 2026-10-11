"""使用隔离目录和真实 HTTP 请求检查进度读取与记录持久化。"""
import copy
import importlib.util
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SCRIPT = Path(__file__).resolve().parents[1] / "server.py"
spec = importlib.util.spec_from_file_location("dashboard", SCRIPT)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)
ORIGINAL_PROGRESS = dashboard.PROGRESS.read_text(encoding="utf-8")
ORIGINAL_PLAN = dashboard.PLAN.read_text(encoding="utf-8")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="campusflow-dashboard-test-")
        self.root = Path(self.directory.name).resolve()
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.original_paths = dashboard.ROOT, dashboard.PROGRESS, dashboard.PLAN, dashboard.JOURNAL
        dashboard.ROOT = self.root
        dashboard.PROGRESS = self.root / "LEARNING_PROGRESS.md"
        dashboard.PLAN = self.root / "LEARNING_PLAN.md"
        dashboard.JOURNAL = self.root / "LEARNING_JOURNAL.json"
        dashboard.PROGRESS.write_text(ORIGINAL_PROGRESS, encoding="utf-8")
        dashboard.PLAN.write_text(ORIGINAL_PLAN, encoding="utf-8")
        self.server = dashboard.ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        self.server.csrf_token = "isolated-test-token"
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        dashboard.ROOT, dashboard.PROGRESS, dashboard.PLAN, dashboard.JOURNAL = self.original_paths
        self.directory.cleanup()

    def request(self, path, payload=None, headers=None):
        standard = {"Content-Type": "application/json", "Origin": self.url, "X-Learning-Token": self.server.csrf_token}
        standard.update(headers or {})
        request = Request(self.url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=standard)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def entry(self):
        return {"requestId": str(uuid.uuid4()), "taskId": "W1-T1.1", "date": dashboard.snapshot()["today"],
                "minutes": 30, "note": "仅用于隔离测试：完成一次 Git 操作练习。", "evidence": "临时测试数据"}

    def test_reads_documents_and_reflects_file_updates(self):
        code, before = self.request("/api/progress")
        self.assertEqual(code, 200)
        self.assertEqual(len(before["weeks"]), 12)
        self.assertEqual(len(before["fundamentals"]), 6)
        self.assertTrue(before["weeks"][3]["checklist"])
        current_verified = before["meta"]["已验证成果"]
        changed = ORIGINAL_PROGRESS.replace(
            f"| 已验证成果 | {current_verified} |",
            "| 已验证成果 | 隔离测试的新增验收证据 |", 1)
        self.assertNotEqual(changed, ORIGINAL_PROGRESS)
        dashboard.PROGRESS.write_text(changed, encoding="utf-8")
        code, after = self.request("/api/progress")
        self.assertEqual(after["meta"]["已验证成果"], "隔离测试的新增验收证据")
        self.assertNotEqual(before["version"], after["version"])

    def test_persists_self_report_without_changing_acceptance(self):
        before_tasks = dashboard.snapshot()["tasks"]
        payload = self.entry()
        self.assertEqual(self.request("/api/journal", payload)[0], 201)
        saved = json.loads(dashboard.JOURNAL.read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual(saved["status"], "pending_review")
        code, state = self.request("/api/progress")
        self.assertEqual(len(state["entries"]), 1)
        self.assertEqual(state["entries"][0]["minutes"], 30)
        self.assertEqual(state["tasks"], before_tasks)
        self.assertEqual(dashboard.PROGRESS.read_text(encoding="utf-8"), ORIGINAL_PROGRESS)

    def test_duplicate_save_is_idempotent(self):
        payload = self.entry()
        self.assertEqual(self.request("/api/journal", payload)[0], 201)
        self.assertEqual(self.request("/api/journal", payload)[0], 200)
        self.assertEqual(len(dashboard.read_journal()), 1)
        payload["note"] = "相同编号的不同内容"
        self.assertEqual(self.request("/api/journal", payload)[0], 400)
        self.assertEqual(len(dashboard.read_journal()), 1)

    def test_rejects_invalid_or_forged_records(self):
        for field, value in [("minutes", -1), ("minutes", True), ("minutes", 1441), ("note", "  "), ("taskId", "not-a-task"), ("date", "2999-01-01")]:
            with self.subTest(field=field, value=value):
                payload = self.entry()
                payload[field] = value
                self.assertEqual(self.request("/api/journal", payload)[0], 400)
        payload = self.entry()
        payload["status"] = "reviewed"
        self.assertEqual(self.request("/api/journal", payload)[0], 400)
        self.assertFalse(dashboard.JOURNAL.exists())

    def test_restricts_writes_and_does_not_serve_repository_files(self):
        self.assertEqual(self.request("/api/journal", self.entry(), {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.request("/api/journal", self.entry(), {"X-Learning-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("/.git/config")[0], 404)
        self.assertEqual(self.request("/../LEARNING_JOURNAL.json")[0], 404)
        self.assertFalse(dashboard.JOURNAL.exists())


if __name__ == "__main__":
    unittest.main()

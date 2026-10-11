"""本机学习进度页：从 Markdown 读取验收进度，将学习自述持久化到文件。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import tempfile
import threading
import uuid
import webbrowser
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = Path(__file__).resolve().parent / "dist"
PROGRESS = ROOT / "LEARNING_PROGRESS.md"
PLAN = ROOT / "LEARNING_PLAN.md"
JOURNAL = ROOT / "LEARNING_JOURNAL.json"
SHANGHAI = timezone(timedelta(hours=8))
LOCK = threading.Lock()


def section(text: str, heading: str) -> str:
    match = re.search(r"^## " + re.escape(heading) + r"\s*$", text, re.M)
    if not match:
        return ""
    end = re.search(r"^## ", text[match.end():], re.M)
    return text[match.end():match.end() + end.start()] if end else text[match.end():]


def table_blocks(text: str) -> list[str]:
    blocks, current = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line.strip())
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def table(text: str) -> list[dict[str, str]]:
    blocks = table_blocks(text)
    lines = blocks[0].splitlines() if blocks else []
    if len(lines) < 2:
        return []
    cells = lambda line: [item.strip().replace("\\|", "|") for item in re.split(r"(?<!\\)\|", line)[1:-1]]
    headers = cells(lines[0])
    return [dict(zip(headers, cells(line))) for line in lines[2:] if len(cells(line)) == len(headers)]


def status(value: str) -> str:
    if "已验收" in value or "已完成" in value:
        return "done"
    if "待验收" in value:
        return "review"
    if "进行中" in value:
        return "active"
    return "todo"


def read_journal() -> list[dict]:
    if not JOURNAL.exists():
        return []
    data = json.loads(JOURNAL.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("学习记录文件格式不正确，请保留文件并联系导师检查。")
    return data["entries"]


def snapshot() -> dict:
    text = PROGRESS.read_text(encoding="utf-8-sig")
    plan_text = PLAN.read_text(encoding="utf-8-sig")
    meta = {row["项目"]: row["当前状态"] for row in table(section(text, "当前学习位置"))}
    weeks = [{"id": row["周次"], "topics": row["学习内容"], "outcome": row["必须拿出的成果与验收"],
              "status": status(row["当前进度"]), "statusText": row["当前进度"]}
             for row in table(section(text, "全程学习路线"))]
    current_match = re.search(r"W\d+", meta.get("当前阶段", ""))
    current_week = current_match.group() if current_match else "W1"
    for week in weeks:
        match = re.search(r"^### " + re.escape(week["id"]) + r"[：:].*$", plan_text, re.M)
        excerpt = plan_text[match.end():] if match else ""
        end = re.search(r"^#{1,3} ", excerpt, re.M)
        if end:
            excerpt = excerpt[:end.start()]
        week["checklist"] = [{"text": item[1], "checked": item[0].lower() == "x"}
                             for item in re.findall(r"^- \[([ xX])\] (.+)$", excerpt, re.M)]
    tasks = [{"id": row["子任务"], "title": row["目标"], "criteria": row["最低验收"],
              "status": status(row["状态"]), "statusText": row["状态"]}
             for row in table(section(text, current_week + " 当前任务拆分"))]
    gates = [{"id": row["阶段"].split()[0], "title": row["阶段"], "when": row["时间位置"],
              "criteria": row["进入下一阶段前必须证明"], "status": status(row["当前状态"])}
             for row in table(section(text, "阶段验收"))]
    if not weeks or not gates or not meta:
        raise ValueError("未能读取学习路线，请检查 LEARNING_PROGRESS.md 的表格结构。")
    with LOCK:
        entries = read_journal()
    digest = hashlib.sha256((text + plan_text + json.dumps(entries, ensure_ascii=False)).encode()).hexdigest()[:16]
    current_task_match = re.search(r"W\d+-T\d+(?:\.\d+)?", meta.get("当前子任务", ""))
    budget_tables = table_blocks(section(text, "每周时间安排"))
    return {"version": digest, "meta": meta, "weeks": weeks, "tasks": tasks, "gates": gates,
            "currentWeek": current_week, "currentTask": current_task_match.group() if current_task_match else "",
            "budget": table(budget_tables[0]) if budget_tables else [],
            "fundamentals": table(budget_tables[1]) if len(budget_tables) > 1 else [],
            "jobs": table(section(text, "求职准备")),
            "history": table(section(text, "学习记录")), "entries": entries,
            "today": datetime.now(SHANGHAI).date().isoformat()}


def validate_entry(payload: object, data: dict) -> dict:
    fields = {"requestId", "taskId", "date", "minutes", "note", "evidence"}
    if not isinstance(payload, dict) or set(payload) != fields:
        raise ValueError("学习记录字段不完整，或包含不支持的字段。")
    try:
        request_id = str(uuid.UUID(payload["requestId"]))
        entry_date = date.fromisoformat(payload["date"]).isoformat()
    except (ValueError, TypeError, AttributeError):
        raise ValueError("日期或记录编号格式不正确。") from None
    if entry_date > data["today"]:
        raise ValueError("学习日期不能晚于今天。")
    known_tasks = {item["id"] for item in data["tasks"]} | {item["id"] for item in data["weeks"]}
    if payload["taskId"] not in known_tasks:
        raise ValueError("所选任务不存在，请刷新页面后重试。")
    minutes = payload["minutes"]
    if type(minutes) is not int or not 0 <= minutes <= 1440:
        raise ValueError("学习用时需要是 0–1440 之间的整数分钟。")
    if not isinstance(payload["note"], str) or not 1 <= len(payload["note"].strip()) <= 4000:
        raise ValueError("请填写学习心得，最多 4000 字。")
    if not isinstance(payload["evidence"], str) or len(payload["evidence"]) > 2000:
        raise ValueError("成果或待解决问题最多 2000 字。")
    return {"id": request_id, "taskId": payload["taskId"], "date": entry_date, "minutes": minutes,
            "note": payload["note"].strip(), "evidence": payload["evidence"].strip(),
            "status": "pending_review", "createdAt": datetime.now(SHANGHAI).isoformat()}


def save_entry(entry: dict) -> tuple[dict, bool]:
    with LOCK:
        entries = read_journal()
        existing = next((item for item in entries if item["id"] == entry["id"]), None)
        if existing:
            if any(existing.get(key) != entry.get(key) for key in ("taskId", "date", "minutes", "note", "evidence")):
                raise ValueError("这个编号已用于另一条记录，请重新打开记录窗口。")
            return existing, False
        entries.append(entry)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=ROOT, prefix=".learning-journal-", suffix=".tmp", delete=False) as target:
                temp_path = Path(target.name)
                json.dump({"schemaVersion": 1, "entries": entries}, target, ensure_ascii=False, indent=2)
                target.write("\n")
            temp_path.replace(JOURNAL)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
    return entry, True


class Handler(BaseHTTPRequestHandler):
    server_version = "CampusFlowLocal/1.0"

    def allowed_host(self) -> bool:
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def send(self, code: int, body: bytes, kind: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, code: int, data: dict) -> None:
        self.send(code, json.dumps(data, ensure_ascii=False).encode())

    def do_GET(self) -> None:
        if not self.allowed_host():
            self.json_response(403, {"error": "请使用本机页面地址打开。"})
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/progress":
                data = snapshot()
                data["csrfToken"] = self.server.csrf_token
                self.json_response(200, data)
                return
            documents = {"/api/documents/progress": PROGRESS, "/api/documents/plan": PLAN}
            if path in documents:
                self.send(200, documents[path].read_bytes(), "text/plain; charset=utf-8")
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/index.html": ("index.html", "text/html; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/favicon.svg": ("favicon.svg", "image/svg+xml")}
            if path not in assets:
                self.json_response(404, {"error": "页面或资源不存在。"})
                return
            filename, kind = assets[path]
            self.send(200, (PUBLIC / filename).read_bytes(), kind)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            self.json_response(503, {"error": str(error)})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/journal":
            self.json_response(404, {"error": "接口不存在。"})
            return
        allowed_origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if not self.allowed_host() or self.headers.get("Origin") not in allowed_origins or not secrets.compare_digest(self.headers.get("X-Learning-Token", ""), self.server.csrf_token):
            self.json_response(403, {"error": "请在本机页面里保存学习记录。"})
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.json_response(415, {"error": "请使用 JSON 格式提交记录。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                self.json_response(413, {"error": "记录内容过长或为空。"})
                return
            payload = json.loads(self.rfile.read(length))
            entry = validate_entry(payload, snapshot())
            saved, created = save_entry(entry)
            self.json_response(201 if created else 200, {"entry": saved, "created": created})
        except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
            self.json_response(400, {"error": str(error)})
        except OSError:
            self.json_response(503, {"error": "记录未能保存，请保留输入并检查文件权限后重试。"})


def main() -> None:
    parser = argparse.ArgumentParser(description="CampusFlow 本机学习进度页")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as error:
        if args.open_browser:
            try:
                with urlopen(f"http://127.0.0.1:{args.port}/api/progress", timeout=2) as response:
                    if response.headers.get("Server", "").startswith("CampusFlowLocal/"):
                        webbrowser.open(f"http://127.0.0.1:{args.port}/")
                        return
            except (URLError, OSError):
                pass
        print(f"页面未能启动：{error}", flush=True)
        print(f"如已打开，请访问 http://127.0.0.1:{args.port}/；也可用 --port 指定其他端口。", flush=True)
        raise SystemExit(1)
    server.csrf_token = secrets.token_urlsafe(32)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"CampusFlow 学习进度：{url}", flush=True)
    print("本机运行，按 Ctrl+C 关闭。", flush=True)
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

import json
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = os.getenv("GITHUB_REPOSITORY", "twyran/Daily-Paper")
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
EXPECTED_OPEN_ID = os.getenv("FEISHU_OPEN_ID", "")
VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")


def json_request(url, method="GET", body=None, headers=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Daily-Paper-Feishu-Callback/1.0",
    }
    if headers:
        h.update(headers)
    req = Request(url, data=data, method=method, headers=h)
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e


def github_headers():
    if not GITHUB_PAT:
        raise RuntimeError("GITHUB_PAT is not configured")
    return {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def extract_action(payload):
    action = payload.get("action") or (payload.get("event") or {}).get("action") or {}
    value = action.get("value") or {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = {}
    return value


def extract_operator_open_id(payload):
    candidates = [
        (payload.get("operator") or {}).get("open_id"),
        (((payload.get("event") or {}).get("operator") or {}).get("operator_id") or {}).get("open_id"),
        ((payload.get("event") or {}).get("operator") or {}).get("open_id"),
    ]
    return next((x for x in candidates if x), None)


def mark_read(paper_id, issue_url):
    m = re.search(r"/issues/(\d+)", issue_url or "")
    if not m:
        raise RuntimeError("Cannot find GitHub issue number from card payload")
    issue_number = int(m.group(1))

    issue = json_request(
        f"https://api.github.com/repos/{REPO}/issues/{issue_number}",
        headers=github_headers(),
    )
    body = issue.get("body") or ""

    pattern = re.compile(
        rf"^- \[ \](.*?<!-- foundation_id:{re.escape(paper_id)} -->)$",
        flags=re.MULTILINE,
    )
    new_body, count = pattern.subn(r"- [x]\1", body, count=1)
    if count == 0:
        if f"foundation_id:{paper_id}" in body and "- [x]" in body:
            return "这篇论文已经标记为已读"
        raise RuntimeError("Progress checkbox not found in Foundation issue")

    json_request(
        f"https://api.github.com/repos/{REPO}/issues/{issue_number}",
        method="PATCH",
        body={"body": new_body},
        headers=github_headers(),
    )
    return "已标记为已读，以后不会再主动推荐这篇"


def reroll(exclude_ids):
    ids = [x.strip() for x in (exclude_ids or "").split(",") if x.strip()]
    json_request(
        f"https://api.github.com/repos/{REPO}/actions/workflows/foundation.yml/dispatches",
        method="POST",
        body={
            "ref": "main",
            "inputs": {"exclude_ids": ",".join(ids)},
        },
        headers=github_headers(),
    )
    return "正在重新推荐，新的一组论文稍后会发到这个会话"


class handler(BaseHTTPRequestHandler):
    def _reply(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

            if payload.get("challenge"):
                self._reply(200, {"challenge": payload["challenge"]})
                return

            if VERIFICATION_TOKEN and payload.get("token") and payload.get("token") != VERIFICATION_TOKEN:
                self._reply(403, {"error": "verification token mismatch"})
                return

            operator = extract_operator_open_id(payload)
            if EXPECTED_OPEN_ID and operator and operator != EXPECTED_OPEN_ID:
                self._reply(403, {"error": "operator not allowed"})
                return

            value = extract_action(payload)
            action = value.get("action")

            if action == "mark_read":
                message = mark_read(value.get("paper_id", ""), value.get("issue_url", ""))
            elif action == "reroll":
                message = reroll(value.get("exclude_ids", ""))
            else:
                self._reply(200, {"toast": {"type": "warning", "content": "未知操作"}})
                return

            self._reply(200, {"toast": {"type": "success", "content": message}})
        except Exception as e:
            self._reply(200, {"toast": {"type": "error", "content": f"操作失败：{e}"}})

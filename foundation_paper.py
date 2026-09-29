import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.zhizengzeng.com/v1")
FOUNDATION_TOP_N = int(os.getenv("FOUNDATION_TOP_N", "2"))
LOCAL_TZ = ZoneInfo("Asia/Singapore")
FOUNDATION_FILE = Path("foundation_papers.json")


def request_json(url: str, headers: dict | None = None, method: str = "GET", body: dict | None = None):
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "Daily-Paper-Foundation/1.0",
    }
    if headers:
        request_headers.update(headers)

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"

    req = Request(url, data=data, method=method, headers=request_headers)
    try:
        with urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"Request failed for {url}: {e}") from e


def github_request(method: str, url: str, token: str, body: dict | None = None):
    return request_json(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
        body=body,
    )


def load_foundation_papers() -> list[dict]:
    data = json.loads(FOUNDATION_FILE.read_text(encoding="utf-8"))
    return data.get("papers", [])


def fetch_recent_daily_issues(repo: str, token: str, days: int = 7) -> list[dict]:
    issues = github_request(
        "GET",
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100",
        token,
    )
    cutoff = datetime.now(LOCAL_TZ).date() - timedelta(days=days)
    result = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        title = issue.get("title", "")
        if not title.startswith("Daily LLM Paper Digest — "):
            continue
        date_str = title.split("—", 1)[-1].strip()
        try:
            issue_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if issue_date >= cutoff:
            result.append({
                "title": title,
                "body": issue.get("body", ""),
                "date": date_str,
            })
    return sorted(result, key=lambda x: x["date"], reverse=True)


def fetch_previous_foundation_ids(repo: str, token: str) -> set[str]:
    issues = github_request(
        "GET",
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100",
        token,
    )
    seen = set()
    marker = "<!-- foundation_ids:"
    for issue in issues:
        if "pull_request" in issue:
            continue
        body = issue.get("body") or ""
        idx = body.find(marker)
        if idx == -1:
            continue
        end = body.find("-->", idx)
        if end == -1:
            continue
        raw = body[idx + len(marker):end].strip()
        for paper_id in raw.split(","):
            paper_id = paper_id.strip()
            if paper_id:
                seen.add(paper_id)
    return seen


def select_foundation_papers(papers: list[dict], recent_issues: list[dict], seen_ids: set[str]) -> list[dict]:
    available = [p for p in papers if p.get("id") not in seen_ids]
    if not available:
        available = papers

    client = OpenAI(base_url=BASE_URL)
    recent_context = "\n\n".join(
        f"### {x['date']}\n{x['body'][:7000]}"
        for x in recent_issues[:7]
    ) or "No recent Daily Digest issues were found."

    prompt = f"""
You are designing a weekly foundation-paper curriculum for a second-year master's student targeting LLM algorithm internships and new-grad roles.

Goal:
Choose {FOUNDATION_TOP_N} foundational papers that best reinforce the student's recent frontier reading and improve interview/job readiness.

Job-relevant priority areas:
1. Post-training: SFT, RLHF/RLAIF, DPO, RL/RLVR, reward models, verifiers, graders, synthetic data, evals
2. Agents: tool use, coding agents, computer use, long-horizon agents, planning, multi-agent, environments/trajectories/rewards, agent memory, personalization
3. Reasoning: CoT, process supervision, verifier/search, test-time scaling, self-correction
4. Retrieval/context/memory: RAG, retrieval, long context, context engineering, external memory
5. LLM systems: serving, KV cache, speculative decoding, quantization, distributed inference
6. Architecture/pretraining/data when especially foundational

Selection principles:
- Prefer papers that explain prerequisites behind topics appearing in the recent Daily Digest.
- Prefer must-read papers over optional ones when both fit.
- Build technical foundations, not just topical similarity.
- Avoid selecting two papers that are nearly redundant.
- If recent topics are diverse, cover two complementary foundations.
- Do not choose already-recommended IDs unless the available pool is exhausted.
- Use only the provided metadata and recent issue text.

Recent frontier reading:
{recent_context}

Available foundation papers:
{json.dumps(available, ensure_ascii=False)}

Return valid JSON only:
{{
  "selected": [
    {{
      "id": "paper id",
      "why_now": "用中文解释为什么这周适合补这篇",
      "learning_goals": ["...", "...", "..."],
      "prerequisites": ["...", "..."],
      "interview_questions": ["...", "...", "..."],
      "reading_plan": "用中文给一个 45-90 分钟的阅读建议"
    }}
  ]
}}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    text = (response.choices[0].message.content or "").strip()
    fence = chr(96) * 3
    if text.startswith(fence + "json"):
        text = text[7:]
    elif text.startswith(fence):
        text = text[3:]
    if text.endswith(fence):
        text = text[:-3]

    parsed = json.loads(text.strip())
    by_id = {p["id"]: p for p in papers}
    result = []
    for item in parsed.get("selected", [])[:FOUNDATION_TOP_N]:
        paper = by_id.get(item.get("id"))
        if paper:
            result.append({**paper, **item})
    return result


def render_markdown(run_date: str, selected: list[dict]) -> str:
    ids = ",".join(p["id"] for p in selected)
    lines = [
        f"# Foundation Papers — {run_date}",
        "",
        f"<!-- foundation_ids:{ids} -->",
        "",
        f"> 根据最近一周 Daily Digest 自动匹配；模型：{MODEL}",
        "",
    ]
    for i, p in enumerate(selected, start=1):
        lines += [
            f"## {i}. {p['title']} ({p.get('year', '')})",
            "",
            f"- **方向**：{p.get('track')}",
            f"- **优先级**：{p.get('priority')}",
            f"- **为什么现在读**：{p.get('why_now', '')}",
            f"- **就业价值**：{p.get('why_for_jobs', '')}",
            f"- **链接**：{p.get('arxiv')}",
            "",
            "**本次阅读目标**：",
        ]
        for x in p.get("learning_goals", []):
            lines.append(f"- {x}")
        lines += ["", "**建议先会**："]
        for x in p.get("prerequisites", []):
            lines.append(f"- {x}")
        lines += ["", "**面试可能追问**："]
        for x in p.get("interview_questions", []):
            lines.append(f"- {x}")
        lines += [
            "",
            f"**阅读计划**：{p.get('reading_plan', '')}",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)


def get_feishu_tenant_access_token() -> str:
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID or FEISHU_APP_SECRET is not set")

    result = request_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    if result.get("code") != 0 or not result.get("tenant_access_token"):
        raise RuntimeError(f"Failed to obtain Feishu tenant_access_token: {result}")
    return result["tenant_access_token"]


def render_feishu_card(run_date: str, selected: list[dict]) -> dict:
    elements = []
    for i, p in enumerate(selected, start=1):
        goals = "\n".join(f"• {x}" for x in p.get("learning_goals", [])[:4])
        qs = "\n".join(f"{idx}. {x}" for idx, x in enumerate(p.get("interview_questions", [])[:3], start=1))
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**{i}. {p['title']} ({p.get('year', '')})**\n"
                    f"**方向：** {p.get('track')} · **{p.get('priority')}**\n"
                    f"**为什么这周读：** {p.get('why_now', '')}\n"
                    f"**阅读目标：**\n{goals}\n"
                    f"**面试追问：**\n{qs}\n"
                    f"**阅读计划：** {p.get('reading_plan', '')}"
                ),
            },
        })
        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "打开论文"},
                "type": "primary",
                "url": p.get("arxiv"),
            }],
        })
        if i != len(selected):
            elements.append({"tag": "hr"})

    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": "Foundation Track · 根据最近一周前沿阅读补基础",
        }],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "purple",
            "title": {"tag": "plain_text", "content": f"Foundation Papers · {run_date}"},
        },
        "elements": elements,
    }


def send_feishu(run_date: str, selected: list[dict]) -> None:
    open_id = os.getenv("FEISHU_OPEN_ID")
    if not open_id:
        raise RuntimeError("FEISHU_OPEN_ID is not set")

    token = get_feishu_tenant_access_token()
    result = request_json(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
        body={
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": json.dumps(render_feishu_card(run_date, selected), ensure_ascii=False),
        },
    )
    if result.get("code") != 0:
        raise RuntimeError(f"Feishu message send failed: {result}")
    print("Foundation Track sent to Feishu successfully.")


def issue_exists(repo: str, token: str, title: str) -> bool:
    issues = github_request(
        "GET",
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100",
        token,
    )
    return any(x.get("title") == title for x in issues if "pull_request" not in x)


def create_issue(repo: str, token: str, title: str, body: str):
    return github_request(
        "POST",
        f"https://api.github.com/repos/{repo}/issues",
        token,
        {"title": title, "body": body},
    )


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(2)

    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        raise RuntimeError("GITHUB_REPOSITORY / GITHUB_TOKEN are required")

    papers = load_foundation_papers()
    recent = fetch_recent_daily_issues(repo, token, days=7)
    seen = fetch_previous_foundation_ids(repo, token)
    selected = select_foundation_papers(papers, recent, seen)

    run_date = datetime.now(LOCAL_TZ).date().isoformat()
    body = render_markdown(run_date, selected)
    Path("foundation_digest.md").write_text(body, encoding="utf-8")
    print(body)

    send_feishu(run_date, selected)

    title = f"Foundation Papers — {run_date}"
    if issue_exists(repo, token, title):
        print(f"Issue already exists: {title}")
    else:
        issue = create_issue(repo, token, title, body)
        print(f"Created issue: {issue.get('html_url')}")


if __name__ == "__main__":
    main()

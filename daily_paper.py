import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from openai import OpenAI

FEED_URL = "https://raw.githubusercontent.com/xianshang33/llm-paper-daily/main/feed-papers.json"
TOP_N = int(os.getenv("TOP_N", "3"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")\nBASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.zhizengzeng.com/v1")

USER_PROFILE = """
You are ranking papers for a second-year master's student preparing for LLM algorithm internships.

Primary interests:
1. LLM reasoning
2. post-training / RLHF / DPO / RL
3. agent / tool use
4. RAG
5. efficient LLM / inference

Prefer papers that:
- introduce a meaningful training or inference idea
- are useful for understanding current LLM research directions
- are likely to support technical interview discussion
- have solid experiments or open-source code
- come from credible research teams, when that signal is available

Down-rank papers that:
- are mainly narrow benchmark papers
- show only small metric improvements without a meaningful idea
- are peripheral to core LLM research
- are application-heavy with limited methodological novelty

Return at most TOP_N papers.
For each paper, produce concise Chinese fields:
- why_recommended
- core_contribution
- reading_level: one of 精读 / 快速读 / 只看摘要
- interview_questions: 2-3 likely follow-up questions

Do not invent facts beyond the provided metadata and summaries.
"""

def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "Daily-Paper/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        raise RuntimeError(f"Failed to fetch feed: {e}") from e

def build_candidates(feed: dict) -> list[dict]:
    out = []
    for x in feed.get("items", []):
        links = x.get("links") or {}
        out.append({
            "id": x.get("id"),
            "date": x.get("date"),
            "title": x.get("title"),
            "topic": x.get("topic"),
            "authors": x.get("authors", []),
            "institution": x.get("institution"),
            "summary_zh": (x.get("summary") or {}).get("zh"),
            "summary_en": (x.get("summary") or {}).get("en"),
            "abs_url": links.get("abs"),
            "pdf_url": links.get("pdf"),
            "github": links.get("github"),
            "priority_keyword": (x.get("signals") or {}).get("priority_keyword"),
        })
    return out

def rank_papers(candidates: list[dict]) -> list[dict]:
    client = OpenAI(base_url=BASE_URL)
    payload = json.dumps(candidates, ensure_ascii=False)
    prompt = f"""
{USER_PROFILE}

TOP_N = {TOP_N}

Candidate papers JSON:
{payload}

Return valid JSON only with this exact structure:
{{
  "selected": [
    {{
      "id": "paper id",
      "why_recommended": "...",
      "core_contribution": "...",
      "reading_level": "精读",
      "interview_questions": ["...", "..."]
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
    data = json.loads(text.strip())
    by_id = {p["id"]: p for p in candidates}
    merged = []
    for rec in data.get("selected", [])[:TOP_N]:
        paper = by_id.get(rec.get("id"))
        if paper:
            merged.append({**paper, **rec})
    return merged

def md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else ""

def render_digest(feed: dict, selected: list[dict]) -> str:
    run_date = feed.get("run_date") or datetime.utcnow().date().isoformat()
    lines = [
        f"# Daily LLM Paper Digest — {run_date}",
        "",
        f"> 数据源：llm-paper-daily；二次筛选模型：{MODEL}；候选数：{len(feed.get('items', []))}",
        "",
    ]
    if not selected:
        return "\n".join(lines + ["今天没有筛出符合偏好的论文。", ""])

    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(selected, start=1):
        prefix = medals[i - 1] if i <= 3 else f"#{i}"
        lines += [
            f"## {prefix} {p['title']}",
            "",
            f"- **主题**：{p.get('topic') or '未标注'}",
            f"- **阅读建议**：{p.get('reading_level', '快速读')}",
            f"- **机构**：{p.get('institution') or '未提供'}",
            f"- **作者**：{', '.join(p.get('authors') or [])}",
            f"- **为什么推荐**：{p.get('why_recommended', '')}",
            f"- **核心贡献**：{p.get('core_contribution', '')}",
            "",
            "**面试可能追问**：",
        ]
        for q in p.get("interview_questions", []):
            lines.append(f"- {q}")
        links = [md_link("arXiv", p.get("abs_url")), md_link("PDF", p.get("pdf_url"))]
        gh = p.get("github")
        if gh:
            gh_url = gh if gh.startswith("http") else f"https://github.com/{gh}"
            links.append(md_link("GitHub", gh_url))
        lines += [
            "",
            " | ".join(x for x in links if x),
            "",
            f"> 原始摘要：{p.get('summary_zh') or p.get('summary_en') or '无'}",
            "",
            "---",
            "",
        ]
    return "\n".join(lines)

def github_request(method: str, url: str, token: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Daily-Paper/1.0",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def issue_exists(repo: str, token: str, title: str) -> bool:
    items = github_request("GET", f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100", token)
    return any(x.get("title") == title for x in items if "pull_request" not in x)

def create_issue(repo: str, token: str, title: str, body: str):
    return github_request("POST", f"https://api.github.com/repos/{repo}/issues", token, {"title": title, "body": body})

def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(2)

    feed = fetch_json(FEED_URL)
    candidates = build_candidates(feed)
    selected = rank_papers(candidates)
    digest = render_digest(feed, selected)
    Path("daily_digest.md").write_text(digest, encoding="utf-8")
    print(digest)

    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    run_date = feed.get("run_date") or datetime.utcnow().date().isoformat()
    title = f"Daily LLM Paper Digest — {run_date}"

    if repo and token:
        if issue_exists(repo, token, title):
            print(f"Issue already exists: {title}")
            return
        issue = create_issue(repo, token, title, digest)
        print(f"Created issue: {issue.get('html_url')}")

if __name__ == "__main__":
    main()

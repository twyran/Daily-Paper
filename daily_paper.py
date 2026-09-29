import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from openai import OpenAI

HF_DAILY_API = "https://huggingface.co/api/daily_papers"
TOP_N = int(os.getenv("TOP_N", "3"))
HF_LIMIT = int(os.getenv("HF_LIMIT", "100"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.zhizengzeng.com/v1")
LOCAL_TZ = ZoneInfo("Asia/Singapore")

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
- have meaningful Hugging Face community interest, but do not blindly rank by upvotes

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


def request_json(url: str, headers: dict | None = None, method: str = "GET", body: dict | None = None):
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "Daily-Paper/2.0",
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


def fetch_hf_daily_papers() -> dict:
    today = datetime.now(LOCAL_TZ).date().isoformat()
    params = {"p": 0, "limit": HF_LIMIT, "date": today, "sort": "publishedAt"}
    headers = {}

    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    url = HF_DAILY_API + "?" + urlencode(params)
    items = request_json(url, headers=headers)

    if not isinstance(items, list):
        raise RuntimeError("Unexpected Hugging Face Daily Papers response shape")

    source_date = today
    if not items:
        fallback = HF_DAILY_API + "?" + urlencode(
            {"p": 0, "limit": HF_LIMIT, "sort": "publishedAt"}
        )
        items = request_json(fallback, headers=headers)
        if not isinstance(items, list):
            raise RuntimeError("Unexpected Hugging Face fallback response shape")

        dates = []
        for item in items:
            published = item.get("publishedAt") or (item.get("paper") or {}).get("publishedAt")
            if isinstance(published, str) and len(published) >= 10:
                dates.append(published[:10])
        if dates:
            source_date = max(dates)

    return {
        "source": "Hugging Face Daily Papers",
        "date": source_date,
        "requested_date": today,
        "items": items,
    }


def normalize_authors(raw_authors) -> list[str]:
    result = []
    for author in raw_authors or []:
        if isinstance(author, dict):
            name = author.get("name") or author.get("fullname") or author.get("user")
        else:
            name = str(author)
        if name:
            result.append(name)
    return result


def build_candidates(feed: dict) -> list[dict]:
    candidates = []
    for item in feed.get("items", []):
        paper = item.get("paper") or {}
        paper_id = paper.get("id") or paper.get("arxivId") or item.get("id")
        if not paper_id:
            continue

        keywords = paper.get("ai_keywords") or []
        if isinstance(keywords, list):
            topic = ", ".join(str(x) for x in keywords[:8])
        else:
            topic = str(keywords)

        organization = paper.get("organization") or paper.get("submittedOnDailyBy")
        if isinstance(organization, dict):
            organization = organization.get("name") or organization.get("fullname")

        github_repo = paper.get("githubRepo")
        project_page = paper.get("projectPage")
        published_at = item.get("publishedAt") or paper.get("publishedAt")

        candidates.append(
            {
                "id": paper_id,
                "date": published_at[:10] if isinstance(published_at, str) else feed.get("date"),
                "title": paper.get("title") or item.get("title"),
                "topic": topic,
                "authors": normalize_authors(paper.get("authors")),
                "institution": organization,
                "summary_en": paper.get("ai_summary") or paper.get("summary") or item.get("summary"),
                "upvotes": paper.get("upvotes", 0),
                "hf_url": f"https://huggingface.co/papers/{paper_id}",
                "abs_url": f"https://arxiv.org/abs/{paper_id}",
                "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
                "github": github_repo,
                "project_page": project_page,
            }
        )
    return candidates


def rank_papers(candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []

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
    selected = []
    for rec in data.get("selected", [])[:TOP_N]:
        paper = by_id.get(rec.get("id"))
        if paper:
            selected.append({**paper, **rec})
    return selected


def md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else ""


def render_digest(feed: dict, selected: list[dict]) -> str:
    run_date = feed.get("date") or datetime.now(LOCAL_TZ).date().isoformat()
    lines = [
        f"# Daily LLM Paper Digest — {run_date}",
        "",
        f"> 数据源：Hugging Face Daily Papers；二次筛选模型：{MODEL}；候选数：{len(feed.get('items', []))}",
        "",
    ]
    if feed.get("requested_date") != run_date:
        lines += [
            f"> 注意：{feed.get('requested_date')} 的 Daily Papers 暂无数据，本次使用最近一期 {run_date}。",
            "",
        ]

    if not selected:
        return "\n".join(lines + ["今天没有筛出符合偏好的论文。", ""])

    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(selected, start=1):
        prefix = medals[i - 1] if i <= 3 else f"#{i}"
        lines += [
            f"## {prefix} {p.get('title') or p['id']}",
            "",
            f"- **阅读建议**：{p.get('reading_level', '快速读')}",
            f"- **HF Upvotes**：{p.get('upvotes', 0)}",
            f"- **主题**：{p.get('topic') or '未标注'}",
            f"- **作者**：{', '.join((p.get('authors') or [])[:12]) or '未提供'}",
            f"- **为什么推荐**：{p.get('why_recommended', '')}",
            f"- **核心贡献**：{p.get('core_contribution', '')}",
            "",
            "**面试可能追问**：",
        ]
        for q in p.get("interview_questions", []):
            lines.append(f"- {q}")

        links = [
            md_link("Hugging Face", p.get("hf_url")),
            md_link("arXiv", p.get("abs_url")),
            md_link("PDF", p.get("pdf_url")),
        ]
        if p.get("github"):
            links.append(md_link("GitHub", p.get("github")))
        if p.get("project_page"):
            links.append(md_link("Project", p.get("project_page")))

        lines += ["", " | ".join(x for x in links if x), "", "---", ""]

    return "\n".join(lines)


def render_feishu_card(run_date: str, selected: list[dict]) -> dict:
    elements = []

    if not selected:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "今天没有筛出符合偏好的论文。"},
        })
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, paper in enumerate(selected, start=1):
            prefix = medals[i - 1] if i <= 3 else f"#{i}"
            title = paper.get("title") or paper["id"]
            authors = ", ".join((paper.get("authors") or [])[:6]) or "未提供"
            questions = "\n".join(
                f"{idx}. {q}"
                for idx, q in enumerate(paper.get("interview_questions", [])[:3], start=1)
            ) or "暂无"

            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**{prefix} {title}**\n"
                        f"**阅读建议：** {paper.get('reading_level', '快速读')}    "
                        f"**HF 👍：** {paper.get('upvotes', 0)}\n"
                        f"**作者：** {authors}\n"
                        f"**推荐理由：** {paper.get('why_recommended', '')}\n"
                        f"**核心贡献：** {paper.get('core_contribution', '')}\n"
                        f"**面试可能追问：**\n{questions}"
                    ),
                },
            })

            actions = []
            if paper.get("hf_url"):
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "Hugging Face"},
                    "type": "primary",
                    "url": paper["hf_url"],
                })
            if paper.get("abs_url"):
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "arXiv"},
                    "type": "default",
                    "url": paper["abs_url"],
                })
            if paper.get("pdf_url"):
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "PDF"},
                    "type": "default",
                    "url": paper["pdf_url"],
                })
            if actions:
                elements.append({"tag": "action", "actions": actions})

            if i != len(selected):
                elements.append({"tag": "hr"})

    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"Hugging Face Daily Papers → {MODEL} 二次筛选 · Top {len(selected)}",
        }],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"Daily LLM Papers · {run_date}"},
        },
        "elements": elements,
    }

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


def send_feishu(run_date: str, selected: list[dict]) -> None:
    open_id = os.getenv("FEISHU_OPEN_ID")
    if not open_id:
        raise RuntimeError("FEISHU_OPEN_ID is not set")

    token = get_feishu_tenant_access_token()
    card = render_feishu_card(run_date, selected)
    result = request_json(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
        body={
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
    )
    if result.get("code") != 0:
        raise RuntimeError(f"Feishu message send failed: {result}")
    message_id = ((result.get("data") or {}).get("message_id"))
    print(f"Feishu rich card sent successfully: {message_id or 'ok'}")

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


def issue_exists(repo: str, token: str, title: str) -> bool:
    items = github_request(
        "GET",
        f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100",
        token,
    )
    return any(x.get("title") == title for x in items if "pull_request" not in x)


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

    feed = fetch_hf_daily_papers()
    candidates = build_candidates(feed)
    print(f"Fetched {len(candidates)} normalized candidates from Hugging Face Daily Papers.")

    selected = rank_papers(candidates)
    digest = render_digest(feed, selected)
    Path("daily_digest.md").write_text(digest, encoding="utf-8")
    print(digest)

    run_date = feed.get("date") or datetime.now(LOCAL_TZ).date().isoformat()
    send_feishu(run_date, selected)

    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    title = f"Daily LLM Paper Digest — {run_date}"

    if repo and token:
        if issue_exists(repo, token, title):
            print(f"Issue already exists: {title}")
        else:
            issue = create_issue(repo, token, title, digest)
            print(f"Created issue: {issue.get('html_url')}")


if __name__ == "__main__":
    main()

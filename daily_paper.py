import json
import os
import sys
from datetime import datetime, timedelta
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
You are ranking papers for a second-year master's student targeting LLM algorithm internships and new-grad roles.
The goal is employment relevance first, while still preserving long-term technical depth.

Primary job-relevant directions, roughly in priority order:

1. Post-training and alignment
- SFT
- RLHF / RLAIF
- DPO and other preference optimization
- RL / RLVR for reasoning and agents
- reward models, verifiers, graders
- synthetic data
- data curation, data mixture, data pipelines
- evaluation and post-training infrastructure

2. Agent systems
- tool use / function calling
- coding agents
- computer use
- long-horizon agents
- planning and execution
- multi-agent systems
- agent environments, trajectories and rewards
- agent memory
- personalization
- context management for agents
- self-reflection / self-improvement

3. Reasoning
- reasoning models
- process supervision
- test-time scaling
- inference-time compute
- search / verifier-guided reasoning
- self-correction and reflection
- mathematical / code reasoning

4. Retrieval, context and memory
- RAG
- retrieval and reranking
- long context
- context engineering
- external memory
- knowledge integration

5. LLM systems
- inference optimization
- serving
- KV cache
- speculative decoding
- quantization
- distributed inference
- training efficiency
- model serving for agents

6. Pretraining / architecture / data
- important work on model architecture, scaling, data, or pretraining
- prioritize only when it has clear relevance to modern LLM practice or hiring

Rank with these hidden considerations:
- JD relevance: how directly the paper maps to work commonly mentioned in current LLM algorithm / agent / post-training roles
- interview value: whether it supports meaningful technical discussion in interviews
- research novelty: whether it introduces a non-trivial new idea
- practical relevance: whether it affects real training, evaluation, agent, retrieval, or inference workflows
- evidence quality: whether the experiments and comparisons described in the provided metadata look substantive
- community signal: Hugging Face interest is useful but must not dominate the ranking

Strongly prefer papers that combine multiple job-relevant themes, for example:
- agent memory + post-training
- tool use + RL
- reasoning + verifier / reward model
- coding agents + environment / trajectory generation
- RAG + long-context / memory
- inference systems + agent serving

Down-rank papers that:
- are mainly narrow benchmarks
- show only small metric gains without a meaningful idea
- are peripheral applications with weak methodological contribution
- are mostly opinion / position pieces unless unusually influential
- are interesting academically but have little connection to likely LLM algorithm work

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
    today = datetime.now(LOCAL_TZ).date()
    target_date = today - timedelta(days=2)
    headers = {}

    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    # Prefer D-2 so the daily list is complete and community upvotes have had
    # roughly two days to accumulate. If that date has no Daily Papers, walk
    # backward to the most recent available issue.
    items = []
    source_date = target_date
    for offset in range(0, 8):
        candidate_date = target_date - timedelta(days=offset)
        params = {
            "p": 0,
            "limit": HF_LIMIT,
            "date": candidate_date.isoformat(),
            "sort": "publishedAt",
        }
        url = HF_DAILY_API + "?" + urlencode(params)
        candidate_items = request_json(url, headers=headers)
        if not isinstance(candidate_items, list):
            raise RuntimeError("Unexpected Hugging Face Daily Papers response shape")
        if candidate_items:
            items = candidate_items
            source_date = candidate_date
            break

    return {
        "source": "Hugging Face Daily Papers",
        "date": source_date.isoformat(),
        "requested_date": target_date.isoformat(),
        "delivery_date": today.isoformat(),
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



def select_hot_papers(candidates: list[dict], selected_ids: set[str]) -> list[dict]:
    ranked = sorted(
        [p for p in candidates if p.get("id") not in selected_ids],
        key=lambda x: (x.get("upvotes", 0), x.get("title") or ""),
        reverse=True,
    )
    return ranked[:TOP_N]


def annotate_hot_papers(hot_papers: list[dict]) -> list[dict]:
    if not hot_papers:
        return []

    client = OpenAI(base_url=BASE_URL)
    payload = json.dumps(hot_papers, ensure_ascii=False)
    prompt = f"""
You are explaining the most popular Hugging Face Daily Papers to a second-year master's student preparing for LLM algorithm internships.

These papers were selected deterministically by Hugging Face upvotes, not by you.
Do not reorder or replace them.

For each paper, provide concise Chinese fields:
- heat_reason: based only on the provided metadata/summary, explain what likely makes the paper attention-worthy without claiming causal knowledge about why people upvoted it
- core_contribution: the main technical contribution
- reading_level: one of 精读 / 快速读 / 只看摘要
- interview_questions: 1-2 useful technical follow-up questions

Do not invent facts beyond the provided metadata and summaries.

Papers JSON:
{payload}

Return valid JSON only:
{{
  "items": [
    {{
      "id": "paper id",
      "heat_reason": "...",
      "core_contribution": "...",
      "reading_level": "快速读",
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

    parsed = json.loads(text.strip())
    by_id = {p["id"]: p for p in hot_papers}
    result = []
    for item in parsed.get("items", []):
        paper = by_id.get(item.get("id"))
        if paper:
            result.append({**paper, **item})

    # Preserve deterministic popularity order even if the model returns a
    # different ordering.
    enriched = {p["id"]: p for p in result}
    return [enriched.get(p["id"], p) for p in hot_papers]

def md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else ""


def render_digest(feed: dict, selected: list[dict], hot_papers: list[dict]) -> str:
    source_date = feed.get("date") or datetime.now(LOCAL_TZ).date().isoformat()
    delivery_date = feed.get("delivery_date") or datetime.now(LOCAL_TZ).date().isoformat()
    lines = [
        f"# Daily LLM Paper Digest — {source_date}",
        "",
        f"> 推送日期：{delivery_date}；论文批次：{source_date}（D-2 优先）；数据源：Hugging Face Daily Papers",
        f"> 二次筛选模型：{MODEL}；候选数：{len(feed.get('items', []))}",
        "",
    ]
    if feed.get("requested_date") != source_date:
        lines += [
            f"> 注意：目标日期 {feed.get('requested_date')} 无 Daily Papers，本次回退到最近一期 {source_date}。",
            "",
        ]

    lines += ["# 🎯 就业相关 Top 3", ""]
    if not selected:
        lines += ["没有筛出符合偏好的论文。", ""]
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, paper in enumerate(selected, start=1):
            prefix = medals[i - 1] if i <= 3 else f"#{i}"
            lines += [
                f"## {prefix} {paper.get('title') or paper['id']}",
                "",
                f"- **阅读建议**：{paper.get('reading_level', '快速读')}",
                f"- **HF Upvotes**：{paper.get('upvotes', 0)}",
                f"- **主题**：{paper.get('topic') or '未标注'}",
                f"- **作者**：{', '.join((paper.get('authors') or [])[:12]) or '未提供'}",
                f"- **为什么推荐**：{paper.get('why_recommended', '')}",
                f"- **核心贡献**：{paper.get('core_contribution', '')}",
                "",
                "**面试可能追问**：",
            ]
            for q in paper.get("interview_questions", []):
                lines.append(f"- {q}")
            links = [
                md_link("Hugging Face", paper.get("hf_url")),
                md_link("arXiv", paper.get("abs_url")),
                md_link("PDF", paper.get("pdf_url")),
            ]
            if paper.get("github"):
                links.append(md_link("GitHub", paper.get("github")))
            if paper.get("project_page"):
                links.append(md_link("Project", paper.get("project_page")))
            lines += ["", " | ".join(x for x in links if x), "", "---", ""]

    lines += ["# 🔥 HF 热度 Top 3（与就业 Top 3 去重）", ""]
    for i, paper in enumerate(hot_papers, start=1):
        lines += [
            f"## 🔥{i} {paper.get('title') or paper['id']}",
            "",
            f"- **HF Upvotes**：{paper.get('upvotes', 0)}",
            f"- **阅读建议**：{paper.get('reading_level', '快速读')}",
            f"- **为什么值得关注**：{paper.get('heat_reason', '')}",
            f"- **核心贡献**：{paper.get('core_contribution', '')}",
            "",
            "**可延伸追问**：",
        ]
        for q in paper.get("interview_questions", []):
            lines.append(f"- {q}")
        links = [
            md_link("Hugging Face", paper.get("hf_url")),
            md_link("arXiv", paper.get("abs_url")),
            md_link("PDF", paper.get("pdf_url")),
        ]
        if paper.get("github"):
            links.append(md_link("GitHub", paper.get("github")))
        if paper.get("project_page"):
            links.append(md_link("Project", paper.get("project_page")))
        lines += ["", " | ".join(x for x in links if x), "", "---", ""]

    return "\n".join(lines)

def render_feishu_card(source_date: str, selected: list[dict], hot_papers: list[dict]) -> dict:
    elements = [{
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**论文批次：{source_date} · 优先使用 D-2 数据**\n就业相关 Top 3 + HF 热度 Top 3，共 {len(selected) + len(hot_papers)} 篇。",
        },
    }]

    medals = ["🥇", "🥈", "🥉"]
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**🎯 就业相关 Top 3**"},
    })
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
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "Hugging Face"},"type": "primary","url": paper["hf_url"]})
        if paper.get("abs_url"):
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "arXiv"},"type": "default","url": paper["abs_url"]})
        if paper.get("pdf_url"):
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "PDF"},"type": "default","url": paper["pdf_url"]})
        if actions:
            elements.append({"tag": "action", "actions": actions})
        elements.append({"tag": "hr"})

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**🔥 HF 热度 Top 3（与就业 Top 3 去重）**"},
    })
    for i, paper in enumerate(hot_papers, start=1):
        title = paper.get("title") or paper["id"]
        questions = "\n".join(
            f"{idx}. {q}"
            for idx, q in enumerate(paper.get("interview_questions", [])[:2], start=1)
        ) or "暂无"
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**🔥{i} {title}**\n"
                    f"**HF 👍：** {paper.get('upvotes', 0)}    "
                    f"**阅读建议：** {paper.get('reading_level', '快速读')}\n"
                    f"**为什么值得关注：** {paper.get('heat_reason', '')}\n"
                    f"**核心贡献：** {paper.get('core_contribution', '')}\n"
                    f"**可延伸追问：**\n{questions}"
                ),
            },
        })
        actions = []
        if paper.get("hf_url"):
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "Hugging Face"},"type": "primary","url": paper["hf_url"]})
        if paper.get("abs_url"):
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "arXiv"},"type": "default","url": paper["abs_url"]})
        if paper.get("pdf_url"):
            actions.append({"tag": "button","text": {"tag": "plain_text", "content": "PDF"},"type": "default","url": paper["pdf_url"]})
        if actions:
            elements.append({"tag": "action", "actions": actions})
        if i != len(hot_papers):
            elements.append({"tag": "hr"})

    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"HF Daily Papers · {MODEL} · 就业筛选 + 热度榜",
        }],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": f"Daily LLM Papers · {source_date}"},
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


def send_feishu(source_date: str, selected: list[dict], hot_papers: list[dict]) -> None:
    open_id = os.getenv("FEISHU_OPEN_ID")
    if not open_id:
        raise RuntimeError("FEISHU_OPEN_ID is not set")

    token = get_feishu_tenant_access_token()
    card = render_feishu_card(source_date, selected, hot_papers)
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
    source_date = feed.get("date") or datetime.now(LOCAL_TZ).date().isoformat()
    delivery_date = feed.get("delivery_date") or datetime.now(LOCAL_TZ).date().isoformat()

    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    title = f"Daily LLM Paper Digest — {delivery_date}"

    # Idempotency is keyed by delivery date. The source batch is D-2 and may
    # collide with legacy issues created before the D-2 strategy was introduced.
    if repo and token and issue_exists(repo, token, title):
        Path("daily_digest.md").write_text(
            f"# Daily LLM Paper Digest — {delivery_date}\n\n"
            f"> Duplicate scheduled retry skipped. Source batch: {source_date}.\n",
            encoding="utf-8",
        )
        print(f"Issue already exists; skipping duplicate delivery: {title}")
        return

    candidates = build_candidates(feed)
    print(f"Fetched {len(candidates)} normalized candidates from Hugging Face Daily Papers ({source_date}).")

    selected = rank_papers(candidates)
    selected_ids = {p.get("id") for p in selected if p.get("id")}

    # Popularity list is deterministic: highest HF upvotes among papers not
    # already chosen for the employment-oriented list.
    hot_raw = select_hot_papers(candidates, selected_ids)
    hot_papers = annotate_hot_papers(hot_raw)

    digest = render_digest(feed, selected, hot_papers)
    Path("daily_digest.md").write_text(digest, encoding="utf-8")
    print(digest)

    send_feishu(source_date, selected, hot_papers)

    if repo and token:
        issue = create_issue(repo, token, title, digest)
        print(f"Created issue: {issue.get('html_url')}")


if __name__ == "__main__":
    main()

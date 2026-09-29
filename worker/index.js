function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function githubRequest(env, path, options = {}) {
  if (!env.GITHUB_PAT) throw new Error("GITHUB_PAT is not configured");
  const url = "https://api.github.com/repos/" + env.GITHUB_REPOSITORY + "/" + path;
  const res = await fetch(url, {
    ...options,
    headers: {
      "accept": "application/vnd.github+json",
      "authorization": "Bearer " + env.GITHUB_PAT,
      "x-github-api-version": "2022-11-28",
      "user-agent": "Daily-Paper-Feishu-Callback/1.0",
      "content-type": "application/json; charset=utf-8",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = {};
  if (text) {
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
  }
  if (!res.ok) throw new Error("GitHub HTTP " + res.status + ": " + text);
  return data;
}

function extractAction(payload) {
  const action = (payload && payload.action) || (payload && payload.event && payload.event.action) || {};
  let value = action.value || {};
  if (typeof value === "string") {
    try { value = JSON.parse(value); } catch { value = {}; }
  }
  return value || {};
}

function extractOperatorOpenId(payload) {
  return (payload && payload.open_id) ||
    (payload && payload.operator && payload.operator.open_id) ||
    (payload && payload.event && payload.event.operator && payload.event.operator.operator_id && payload.event.operator.operator_id.open_id) ||
    (payload && payload.event && payload.event.operator && payload.event.operator.open_id) || null;
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function markRead(env, paperId, issueUrl) {
  const match = String(issueUrl || "").match(/\/issues\/(\d+)/);
  if (!match) throw new Error("Cannot find GitHub issue number from card payload");
  const issueNumber = Number(match[1]);
  const issue = await githubRequest(env, "issues/" + issueNumber);
  const body = issue.body || "";
  const escaped = escapeRegExp(paperId);
  const pattern = new RegExp("^- \\[ \\](.*?<!-- foundation_id:" + escaped + " -->)$", "m");
  if (!pattern.test(body)) {
    const checkedPattern = new RegExp("^- \\[x\\](.*?<!-- foundation_id:" + escaped + " -->)$", "m");
    if (checkedPattern.test(body)) return "这篇论文已经标记为已读";
    throw new Error("Progress checkbox not found in Foundation issue");
  }
  const newBody = body.replace(pattern, "- [x]$1");
  await githubRequest(env, "issues/" + issueNumber, {
    method: "PATCH",
    body: JSON.stringify({ body: newBody }),
  });
  return "已标记为已读，以后不会再主动推荐这篇";
}

async function reroll(env, excludeIds) {
  const ids = String(excludeIds || "").split(",").map((x) => x.trim()).filter(Boolean);
  await githubRequest(env, "actions/workflows/foundation.yml/dispatches", {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: { exclude_ids: ids.join(",") } }),
  });
  return "正在重新推荐，新的一组论文稍后会发到这个会话";
}

export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return jsonResponse({ ok: true, service: "Daily-Paper Feishu callback" });
    }
    if (request.method !== "POST") return jsonResponse({ error: "method not allowed" }, 405);
    try {
      const payload = await request.json();
      const verificationToken = payload?.header?.token || payload?.token;
      if (env.FEISHU_VERIFICATION_TOKEN && verificationToken !== env.FEISHU_VERIFICATION_TOKEN) {
        return jsonResponse({ error: "verification token mismatch" }, 403);
      }
      if (payload && payload.challenge) return jsonResponse({ challenge: payload.challenge });
      const operator = extractOperatorOpenId(payload);
      if (!env.FEISHU_OPEN_ID || operator !== env.FEISHU_OPEN_ID) {
        return jsonResponse({ error: "operator not allowed" }, 403);
      }
      const value = extractAction(payload);
      let message;
      if (value.action === "mark_read") {
        message = await markRead(env, value.paper_id || "", value.issue_url || "");
      } else if (value.action === "reroll") {
        message = await reroll(env, value.exclude_ids || "");
      } else {
        return jsonResponse({ toast: { type: "warning", content: "未知操作" } });
      }
      return jsonResponse({ toast: { type: "success", content: message } });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ toast: { type: "error", content: "操作失败：" + msg } });
    }
  },
};

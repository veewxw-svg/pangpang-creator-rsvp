import { createServer } from "node:http";
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 8787);
const runFile = promisify(execFile);
const dataDir = process.env.DATA_DIR || join(root, "data");
const recordsPath = join(dataDir, "records.json");
const outputDir = process.env.OUTPUT_DIR || join(root, "output");
const reportPath = join(outputDir, "pangpang_creator_report.png");
const reportScript = join(root, "generate_live_report_png.py");
const bundledPython = "/Users/Vee/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const pythonBin = process.env.PYTHON_BIN || (existsSync(bundledPython) ? bundledPython : "python3");

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png"
};

createServer(async (req, res) => {
  try {
    if (req.method === "OPTIONS") {
      writeCors(res, 204, { "Content-Type": "text/plain; charset=utf-8" });
      res.end();
      return;
    }

    const url = new URL(req.url || "/", `http://${req.headers.host}`);
    if (url.pathname === "/api/resolve-profile") {
      const target = url.searchParams.get("url") || "";
      const payload = await resolveProfile(target);
      sendJson(res, payload);
      return;
    }

    if (url.pathname === "/api/records" && req.method === "GET") {
      sendJson(res, { ok: true, records: await readRecords() });
      return;
    }

    if (url.pathname === "/api/records" && req.method === "POST") {
      const body = await readJsonBody(req);
      const records = Array.isArray(body.records) ? body.records : [];
      await writeRecords(records);
      const notification = body.silent ? { skipped: true, reason: "silent update" } : await maybeSendNotification(records);
      sendJson(res, { ok: true, count: records.length, reportUrl: "/api/report.png", notification });
      return;
    }

    if (url.pathname === "/api/report.png") {
      const records = await readRecords();
      await generateReportPng(records);
      const body = await readFile(reportPath);
      writeCors(res, 200, {
        "Content-Type": "image/png",
        "Cache-Control": "no-store"
      });
      res.end(body);
      return;
    }

    const pathname = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
    const safePath = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(root, safePath);
    if (!filePath.startsWith(root)) throw new Error("Forbidden");
    const body = await readFile(filePath);
    writeCors(res, 200, { "Content-Type": mime[extname(filePath)] || "application/octet-stream" });
    res.end(body);
  } catch (error) {
    writeCors(res, 404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(String(error.message || error));
  }
}).listen(port, () => {
  console.log(`PangPang RSVP system: http://127.0.0.1:${port}/`);
});

async function readRecords() {
  try {
    const data = await readFile(recordsPath, "utf8");
    const records = JSON.parse(data);
    return Array.isArray(records) ? records : [];
  } catch {
    return [];
  }
}

async function writeRecords(records) {
  await mkdir(dataDir, { recursive: true });
  await writeFile(recordsPath, JSON.stringify(records, null, 2), "utf8");
}

async function generateReportPng(records) {
  await mkdir(outputDir, { recursive: true });
  await writeRecords(records);
  await runFile(pythonBin, [reportScript], {
    env: {
      ...process.env,
      PANGPANG_RECORDS_JSON: recordsPath,
      PANGPANG_REPORT_OUT: reportPath
    },
    maxBuffer: 1024 * 1024
  });
}

async function maybeSendNotification(records) {
  if (process.env.SEND_EMAILS !== "1") {
    return { sent: false, reason: "email disabled" };
  }
  if (!process.env.RESEND_API_KEY || !process.env.NOTIFY_TO || !process.env.NOTIFY_FROM) {
    return { sent: false, reason: "missing email env" };
  }

  await generateReportPng(records);
  const image = await readFile(reportPath);
  const subject = process.env.NOTIFY_SUBJECT || "PangPang 博主探店预约更新";
  const siteUrl = process.env.PUBLIC_URL || "";
  const to = process.env.NOTIFY_TO.split(",").map((item) => item.trim()).filter(Boolean);
  const payload = {
    from: process.env.NOTIFY_FROM,
    to,
    subject,
    html: [
      "<div style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1d1d1f\">",
      "<h2>PangPang 博主探店预约更新</h2>",
      "<p>最新全局表已附在邮件里。浅蓝=新增预约，浅绿=发帖更新，浅红=取消。</p>",
      siteUrl ? `<p><a href="${escapeAttribute(siteUrl)}">打开预约系统</a></p>` : "",
      "</div>"
    ].join(""),
    attachments: [
      {
        filename: "PangPang_博主探店预约全局表.png",
        content: image.toString("base64")
      }
    ]
  };

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) return { sent: false, status: response.status, result };
  return { sent: true, result };
}

function escapeAttribute(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  return JSON.parse(raw);
}

async function resolveProfile(target) {
  if (!/^https?:\/\//i.test(target)) {
    return { ok: false, message: "不是有效链接" };
  }

  try {
    const page = await fetchPage(target);
    const finalUrl = page.finalUrl || target;
    const instagramJson = await fetchInstagramProfileJson(target, finalUrl);
    if (page.status >= 400) {
      if (instagramJson.name || instagramJson.followers || instagramJson.engagement) {
        return {
          ok: true,
          finalUrl,
          profileUrl: instagramJson.profileUrl || finalUrl,
          postUrl: "",
          platform: instagramJson.platform || "Instagram",
          handle: instagramJson.handle || "",
          name: instagramJson.name || "",
          followers: instagramJson.followers || "",
          engagement: instagramJson.engagement || "",
          following: instagramJson.following || "",
          postCount: instagramJson.postCount || "",
          postLikes: "",
          postCollects: "",
          postComments: "",
          postShares: "",
          postMetricsText: "",
          redId: "",
          description: instagramJson.description || "",
          postTitle: "",
          publishedAt: "",
          sourceTitle: ""
        };
      }
      return {
        ok: false,
        finalUrl,
        status: page.status,
        message: `网页打开失败：HTTP ${page.status}。这个链接可能过期、不完整，或平台没有给公开页面。`
      };
    }
    const html = page.html;
    const meta = collectMeta(html);
    const ssr = parseXhsSsr(html);
    const xhsPost = parseXhsPost(html, meta, finalUrl);
    const instagram = parseInstagramMeta(meta, html, finalUrl);
    const isXhs = /xiaohongshu\.com|xhslink\.com/i.test(finalUrl);
    const publishedAt = instagram.publishedAt || xhsPost.publishedAt || (isXhs ? "" : parsePublishedAt(html, meta));
    const combined = [meta.title, meta.description, meta.ogTitle, meta.ogDescription, stripTags(html).slice(0, 3000)].filter(Boolean).join("\n");
    const parsed = parseSharedText(combined, finalUrl);
    const titleName = cleanXhsTitle(meta.title || meta.ogTitle || "");

    return {
      ok: true,
      finalUrl,
      profileUrl: instagramJson.profileUrl || instagram.profileUrl || xhsPost.profileUrl || parsed.profileUrl || finalUrl,
      postUrl: instagram.postUrl || xhsPost.postUrl || parsed.postUrl || "",
      platform: instagramJson.platform || instagram.platform || parsed.platform,
      handle: instagramJson.handle || instagram.handle || xhsPost.handle || parsed.handle,
      name: instagramJson.name || instagram.name || xhsPost.name || ssr.name || parsed.name || titleName,
      followers: instagramJson.followers || instagram.followers || ssr.followers || (parsed.followers && parsed.followers !== "1" ? parsed.followers : ""),
      engagement: instagramJson.engagement || instagram.engagement || ssr.engagement || parsed.engagement,
      following: instagramJson.following || instagram.following || "",
      postCount: instagramJson.postCount || instagram.postCount || "",
      postLikes: xhsPost.postLikes || instagram.postLikes || "",
      postCollects: xhsPost.postCollects || "",
      postComments: xhsPost.postComments || instagram.postComments || "",
      postShares: xhsPost.postShares || "",
      postMetricsText: xhsPost.postMetricsText || instagram.postMetricsText || "",
      redId: ssr.redId || "",
      description: instagramJson.description || instagram.description || xhsPost.description || ssr.description || "",
      postTitle: instagram.postTitle || xhsPost.postTitle || parsed.postTitle,
      publishedAt,
      sourceTitle: meta.title || meta.ogTitle || ""
    };
  } catch (error) {
    return { ok: false, message: `打开网页失败：${error.message || error}` };
  }
}

async function fetchPage(target) {
  if (/instagram\.com|instagr\.am/i.test(target)) {
    return fetchPageWithCurl(target, { minimal: true });
  }

  try {
    const response = await fetch(target, {
      redirect: "follow",
      headers: {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
      }
    });
    return {
      status: response.status,
      finalUrl: response.url || target,
      html: await response.text()
    };
  } catch {
    return fetchPageWithCurl(target);
  }
}

async function fetchPageWithCurl(target, options = {}) {
  const args = [
    "-L",
    "-sS",
    "--max-time",
    "15",
  ];
  if (!options.minimal) {
    args.push(
      "-A",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "-H",
      "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8"
    );
  }
  args.push("-w", "\n__FINAL_URL__%{url_effective}\n__HTTP_CODE__%{http_code}", target);
  const { stdout } = await runFile("curl", args, { maxBuffer: 4 * 1024 * 1024 });
  const finalUrl = stdout.match(/\n__FINAL_URL__(.*)\n__HTTP_CODE__/)?.[1]?.trim() || target;
  const status = Number(stdout.match(/\n__HTTP_CODE__(\d+)/)?.[1] || 0);
  const html = stdout.replace(/\n__FINAL_URL__.*\n__HTTP_CODE__\d+\s*$/s, "");
  return { status, finalUrl, html };
}

function collectMeta(html) {
  const get = (pattern) => (html.match(pattern)?.[1] || "").trim();
  return {
    title: decodeEntities(get(/<title[^>]*>([\s\S]*?)<\/title>/i)),
    description: decodeEntities(get(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["'][^>]*>/i) || get(/<meta[^>]+content=["']([^"']*)["'][^>]+name=["']description["'][^>]*>/i)),
    ogTitle: decodeEntities(get(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']*)["'][^>]*>/i) || get(/<meta[^>]+content=["']([^"']*)["'][^>]+property=["']og:title["'][^>]*>/i)),
    ogDescription: decodeEntities(get(/<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']*)["'][^>]*>/i) || get(/<meta[^>]+content=["']([^"']*)["'][^>]+property=["']og:description["'][^>]*>/i)),
    articlePublishedTime: decodeEntities(get(/<meta[^>]+property=["']article:published_time["'][^>]+content=["']([^"']*)["'][^>]*>/i) || get(/<meta[^>]+content=["']([^"']*)["'][^>]+property=["']article:published_time["'][^>]*>/i))
  };
}

function parseSharedText(text, finalUrl) {
  const compact = text.replace(/\s+/g, " ").trim();
  const lower = compact.toLowerCase();
  const source = lower + finalUrl.toLowerCase();
  let platform = "";
  if (/xiaohongshu|xhslink|小红书/.test(source)) platform = "小红书";
  else if (/instagram\.com|instagr\.am|instagram/.test(source)) platform = "Instagram";
  const handleMatch = compact.match(/@([^\s:：,，的]+)/);
  const homeMatch = compact.match(/([^\s,，。|｜]{2,24})的个人主页/);
  const followerMatch = compact.match(/(?:粉丝|followers?)\s*[:：]?\s*([\d,.]+)\s*([万kKmM]?)/i)
    || compact.match(/([\d,.]+)\s*([万kKmM]?)\s*(?:粉丝|followers?)/i);
  const followingMatch = compact.match(/([\d,.]+)\s*([万kKmM]?)\s*following/i);
  const postsMatch = compact.match(/([\d,.]+)\s*([万kKmM]?)\s*posts?/i);
  const engagementMatch = compact.match(/(?:获赞与收藏|赞藏|获赞|总赞|likes?)\s*[:：]?\s*([\d,.]+)\s*([万kKmM]?)/i);
  const title = compact.split(/[-|｜]/)[0].trim().slice(0, 80);

  return {
    platform,
    profileUrl: /\/user\/profile\//.test(finalUrl) ? finalUrl : "",
    postUrl: /\/explore\/|\/discovery\/item|note/i.test(finalUrl) ? finalUrl : "",
    handle: handleMatch ? `@${handleMatch[1]}` : "",
    name: homeMatch ? homeMatch[1].replace(/^@/, "") : "",
    followers: followerMatch ? normalizeNumber(followerMatch[1], followerMatch[2]) : "",
    engagement: platform === "Instagram" && (postsMatch || followingMatch)
      ? `${postsMatch ? normalizeNumber(postsMatch[1], postsMatch[2]) : "0"} posts · ${followingMatch ? normalizeNumber(followingMatch[1], followingMatch[2]) : "0"} following`
      : (engagementMatch ? normalizeNumber(engagementMatch[1], engagementMatch[2]) : ""),
    postTitle: title
  };
}

function parseInstagramMeta(meta, html, finalUrl) {
  if (!/instagram\.com|instagr\.am/i.test(finalUrl)) return {};
  const read = (pattern) => decodeEntities((html.match(pattern)?.[1] || "").trim());
  const title = meta.ogTitle || meta.title || read(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']*)["'][^>]*>/i) || read(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const description = meta.ogDescription || meta.description || read(/<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']*)["'][^>]*>/i) || read(/<meta[^>]+content=["']([^"']*)["'][^>]+name=["']description["'][^>]*>/i);
  const fallback = meta.description || description || read(/<meta[^>]+content=["']([^"']*)["'][^>]+name=["']description["'][^>]*>/i);
  const isPost = /\/(?:p|reel|reels)\//i.test(finalUrl);
  const titleMatch = title.match(/^(.+?)\s+\(@([^)]+)\)/);
  const descMatch = description.match(/-\s*(.+?)\s+\(@([^)]+)\)\s+on Instagram/i);
  const postTitleMatch = title.match(/^(.+?)\s+on Instagram\s*:/i) || description.match(/-\s*(.+?)\s+on Instagram\s*:/i);
  const stats = readInstagramStats([description, fallback, title, stripTags(html).slice(0, 3000)].filter(Boolean));
  const bioMatch = description.match(/on Instagram:\s*"([^"]*)"/i);
  const urlHandle = finalUrl.match(/instagram\.com\/([^/?#]+)/i)?.[1] || "";
  const handle = titleMatch?.[2] || descMatch?.[2] || urlHandle;
  const following = stats.following || "";
  const postCount = stats.postCount || "";
  const publishedAt = parsePublishedAt(html, meta);
  const likeMatch = description.match(/([\d,.KMkm]+)\s+likes?/i);
  const commentMatch = description.match(/([\d,.KMkm]+)\s+comments?/i);
  const profileUrl = handle ? `https://www.instagram.com/${handle.replace(/^@/, "")}/` : finalUrl;

  return {
    platform: "Instagram",
    profileUrl,
    postUrl: isPost ? finalUrl : "",
    handle: handle ? `@${handle.replace(/^@/, "")}` : "",
    name: decodeEntities(titleMatch?.[1] || descMatch?.[1] || postTitleMatch?.[1] || ""),
    followers: stats.followers || "",
    following,
    postCount,
    postLikes: likeMatch ? normalizeNumber(likeMatch[1], "") : "",
    postComments: commentMatch ? normalizeNumber(commentMatch[1], "") : "",
    postMetricsText: [
      likeMatch ? `点赞 ${normalizeNumber(likeMatch[1], "")}` : "",
      commentMatch ? `评论 ${normalizeNumber(commentMatch[1], "")}` : ""
    ].filter(Boolean).join(" · "),
    engagement: (postCount || following) ? `${postCount || "0"} posts · ${following || "0"} following` : "",
    description: decodeEntities(bioMatch?.[1] || ""),
    postTitle: title.replace(/\s*•\s*Instagram.*/i, "").trim(),
    publishedAt
  };
}

async function fetchInstagramProfileJson(target, finalUrl) {
  const username = extractInstagramUsername(target) || extractInstagramUsername(finalUrl);
  if (!username) return {};
  try {
    const apiUrl = `https://www.instagram.com/api/v1/users/web_profile_info/?username=${encodeURIComponent(username)}`;
    const json = await fetchInstagramJson(apiUrl);
    const user = json?.data?.user;
    if (!user) return {};
    const followers = user.edge_followed_by?.count;
    const following = user.edge_follow?.count;
    const postCount = user.edge_owner_to_timeline_media?.count;
    return {
      platform: "Instagram",
      profileUrl: `https://www.instagram.com/${user.username || username}/`,
      handle: user.username ? `@${user.username}` : `@${username}`,
      name: user.full_name || user.username || username,
      followers: Number.isFinite(followers) ? normalizeNumber(followers, "") : "",
      following: Number.isFinite(following) ? normalizeNumber(following, "") : "",
      postCount: Number.isFinite(postCount) ? normalizeNumber(postCount, "") : "",
      engagement: `${Number.isFinite(postCount) ? normalizeNumber(postCount, "") : "0"} posts · ${Number.isFinite(following) ? normalizeNumber(following, "") : "0"} following`,
      description: user.biography || ""
    };
  } catch {
    return {};
  }
}

async function fetchInstagramJson(apiUrl) {
  const headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept": "application/json",
    "x-ig-app-id": "936619743392459"
  };
  try {
    const response = await fetch(apiUrl, { headers });
    if (response.ok) return await response.json();
  } catch {
    // Fall through to curl. Instagram sometimes treats server fetch and curl differently.
  }
  const { stdout } = await runFile("curl", [
    "-L",
    "-sS",
    "--max-time",
    "15",
    "-A",
    headers["User-Agent"],
    "-H",
    `Accept: ${headers.Accept}`,
    "-H",
    `x-ig-app-id: ${headers["x-ig-app-id"]}`,
    apiUrl
  ], { maxBuffer: 4 * 1024 * 1024 });
  return JSON.parse(stdout);
}

function extractInstagramUsername(value) {
  const match = String(value || "").match(/instagram\.com\/([^/?#]+)/i);
  const username = match?.[1]?.replace(/^@/, "") || "";
  if (!username || ["accounts", "p", "reel", "reels", "explore", "stories"].includes(username.toLowerCase())) return "";
  return decodeURIComponent(username);
}

function readInstagramStats(sources) {
  const sourceList = Array.isArray(sources) ? sources : [sources];
  let compact = "";
  const readLabel = (label) => {
    const after = compact.match(new RegExp(`([\\d,.]+)\\s*([KkMm]?)\\s*${label}`, "i"));
    const before = compact.match(new RegExp(`${label}\\s*[:：]?\\s*([\\d,.]+)\\s*([KkMm]?)`, "i"));
    const match = after || before;
    return match ? normalizeNumber(match[1], match[2]) : "";
  };
  for (const source of sourceList) {
    compact = String(source || "").replace(/\s+/g, " ");
    const stats = {
      followers: readLabel("followers?"),
      following: readLabel("following"),
      postCount: readLabel("posts?")
    };
    if ([stats.followers, stats.following, stats.postCount].filter(Boolean).length >= 2) return stats;
  }
  return { followers: "", following: "", postCount: "" };
}

function parseXhsPost(html, meta, finalUrl) {
  if (!/xiaohongshu\.com|xhslink\.com/i.test(finalUrl) || !/\/explore\/|\/discovery\/item|note/i.test(finalUrl)) return {};
  const read = (pattern) => decodeEscaped(html.match(pattern)?.[1] || "");
  const postTitle = cleanXhsTitle(meta.ogTitle || meta.title || "");
  const name = read(/"user":\{[\s\S]{0,800}?"nickname":"((?:\\.|[^"])*)"/)
    || read(/"author":\{[\s\S]{0,800}?"nickname":"((?:\\.|[^"])*)"/)
    || read(/"nickname":"((?:\\.|[^"])*)","avatar"/)
    || postTitle.split(/[｜|-]/)[0].trim();
  const userId = read(/"user":\{[\s\S]{0,800}?"userId":"([^"]+)"/)
    || read(/"author":\{[\s\S]{0,800}?"userId":"([^"]+)"/);
  const publishedAt = parseXhsPublishedAt(html, meta);
  const counts = parseXhsPostCounts(html);
  return {
    name,
    handle: userId ? `@${userId}` : "",
    profileUrl: userId ? `https://www.xiaohongshu.com/user/profile/${userId}` : "",
    postUrl: finalUrl,
    postTitle,
    publishedAt,
    ...counts,
    description: meta.description || meta.ogDescription || ""
  };
}

function parseXhsPostCounts(html) {
  const source = decodeEntities(html);
  const readCount = (keys) => {
    for (const key of keys) {
      const patterns = [
        new RegExp(`"${key}"\\s*:\\s*"?([\\d,.万kKmM+]+)"?`, "i"),
        new RegExp(`"${key}"\\s*:\\s*\\{[^}]*"count"\\s*:\\s*"?([\\d,.万kKmM+]+)"?`, "i")
      ];
      for (const pattern of patterns) {
        const match = source.match(pattern);
        if (match?.[1]) return normalizeSocialCount(match[1]);
      }
    }
    return "";
  };
  const postLikes = readCount(["likedCount", "likeCount", "liked_count", "likes", "likesCount"]);
  const postCollects = readCount(["collectedCount", "collectCount", "collected_count", "favoriteCount", "favCount", "collects"]);
  const postComments = readCount(["commentCount", "commentsCount", "comment_count", "comments"]);
  const postShares = readCount(["shareCount", "share_count", "shares"]);
  return {
    postLikes,
    postCollects,
    postComments,
    postShares,
    postMetricsText: [
      postLikes ? `点赞 ${postLikes}` : "",
      postCollects ? `收藏 ${postCollects}` : "",
      postComments ? `评论 ${postComments}` : "",
      postShares ? `转发 ${postShares}` : ""
    ].filter(Boolean).join(" · ")
  };
}

function parseXhsPublishedAt(html, meta = {}) {
  const direct = [
    meta.articlePublishedTime,
    html.match(/<meta[^>]+itemprop=["']datePublished["'][^>]+content=["']([^"']+)["'][^>]*>/i)?.[1],
    html.match(/"datePublished"\s*:\s*"([^"]+)"/i)?.[1],
    html.match(/"uploadDate"\s*:\s*"([^"]+)"/i)?.[1]
  ].filter(Boolean).map(decodeEntities).find(Boolean);
  if (direct) return direct;

  const explicitTextDate = parseXhsExplicitPublishedText(html);
  if (explicitTextDate) return explicitTextDate;

  const keys = [
    "noteCreateTime",
    "createTime",
    "create_time",
    "createdTime",
    "created_at",
    "firstPublishTime",
    "notePublishTime",
    "publishDateTime",
    "publishDate",
    "publish_time"
  ];
  for (const key of keys) {
    const match = findXhsNoteTimestamp(html, key);
    if (match) return timestampToIso(match);
  }
  return "";
}

function parseXhsExplicitPublishedText(html) {
  const source = decodeEntities(stripTags(html)).replace(/\s+/g, " ");
  const patterns = [
    /(?:发布于|发表于|发布时间|发布)\s*[:：]?\s*(20\d{2})[年./-]\s*(\d{1,2})[月./-]\s*(\d{1,2})(?:日)?(?:\s+(\d{1,2}):(\d{2}))?/i,
    /(?:发布于|发表于|发布时间|发布)\s*[:：]?\s*(\d{1,2})[月./-]\s*(\d{1,2})(?:日)?(?:\s+(\d{1,2}):(\d{2}))?/i
  ];
  for (const pattern of patterns) {
    const match = source.match(pattern);
    if (!match) continue;
    const hasYear = match[1]?.length === 4;
    const year = hasYear ? Number(match[1]) : new Date().getFullYear();
    const month = Number(hasYear ? match[2] : match[1]);
    const day = Number(hasYear ? match[3] : match[2]);
    const hour = Number(hasYear ? match[4] || 12 : match[3] || 12);
    const minute = Number(hasYear ? match[5] || 0 : match[4] || 0);
    const iso = datePartsToIso(year, month, day, hour, minute);
    if (iso) return iso;
  }
  return "";
}

function findXhsNoteTimestamp(html, key) {
  const pattern = new RegExp(`"${key}"\\s*:\\s*"?([0-9]{10,13})"?`, "ig");
  let match;
  while ((match = pattern.exec(html))) {
    const start = Math.max(0, match.index - 900);
    const end = Math.min(html.length, match.index + 900);
    const context = html.slice(start, end);
    if (/lastUpdate|updateTime|updated|editTime|edited|更新时间|编辑于|修改/i.test(context)) continue;
    if (!/note|笔记|explore|desc|title|interact|liked|collect|comment|share/i.test(context)) continue;
    return match[1];
  }
  return "";
}

function datePartsToIso(year, month, day, hour = 12, minute = 0) {
  if (!year || !month || !day) return "";
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return "";
  return date.toISOString();
}

function parsePublishedAt(html, meta = {}) {
  const direct = [
    meta.articlePublishedTime,
    html.match(/<meta[^>]+itemprop=["']datePublished["'][^>]+content=["']([^"']+)["'][^>]*>/i)?.[1],
    html.match(/<meta[^>]+property=["']video:release_date["'][^>]+content=["']([^"']+)["'][^>]*>/i)?.[1],
    html.match(/<time[^>]+datetime=["']([^"']+)["'][^>]*>/i)?.[1],
    html.match(/"datePublished"\s*:\s*"([^"]+)"/i)?.[1],
    html.match(/"uploadDate"\s*:\s*"([^"]+)"/i)?.[1]
  ].filter(Boolean).map(decodeEntities).find(Boolean);
  if (direct) return direct;

  const timestamp = [
    html.match(/"taken_at_timestamp"\s*:\s*(\d{10,13})/i)?.[1],
    html.match(/"taken_at"\s*:\s*(\d{10,13})/i)?.[1],
    html.match(/"publishTime"\s*:\s*(\d{10,13})/i)?.[1]
  ].find(Boolean);
  if (!timestamp) return "";
  return timestampToIso(timestamp);
}

function timestampToIso(timestamp) {
  const ms = String(timestamp).length === 10 ? Number(timestamp) * 1000 : Number(timestamp);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : "";
}

function parseXhsSsr(html) {
  const read = (pattern) => decodeEscaped(html.match(pattern)?.[1] || "");
  const readInteraction = (label, type) => {
    const byLabel = html.match(new RegExp(`"name":"${label}","count":"([^"]+)"`));
    if (byLabel) return decodeEscaped(byLabel[1]);
    const byType = html.match(new RegExp(`"count":"([^"]+)","i18nCount":"[^"]*","type":"${type}"`));
    return byType ? decodeEscaped(byType[1]) : "";
  };

  return {
    name: read(/"basicInfo":\{[\s\S]*?"nickname":"([^"]+)"/),
    redId: read(/"basicInfo":\{[\s\S]*?"redId":"([^"]+)"/),
    description: read(/"basicInfo":\{[\s\S]*?"desc":"((?:\\.|[^"])*)"/),
    followers: readInteraction("粉丝", "fans"),
    engagement: readInteraction("获赞与收藏", "interaction")
  };
}

function decodeEscaped(text) {
  if (!text) return "";
  try {
    return JSON.parse(`"${text.replace(/"/g, '\\"')}"`);
  } catch {
    return text.replace(/\\u002F/g, "/").replace(/\\n/g, "\n");
  }
}

function cleanXhsTitle(title) {
  return title
    .replace(/\s*[-｜|]\s*小红书.*/i, "")
    .replace(/\s*小红书.*/i, "")
    .trim();
}

function normalizeNumber(value, unit) {
  const number = Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(number)) return `${value}${unit || ""}`;
  if (unit === "万") return String(Math.round(number * 10000)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  if (/k/i.test(unit)) return String(Math.round(number * 1000)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  if (/m/i.test(unit)) return String(Math.round(number * 1000000)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return String(Math.round(number)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function normalizeSocialCount(value) {
  const raw = String(value || "").trim();
  const match = raw.match(/^([\d,.]+)\s*([万kKmM+]*)$/);
  if (!match) return raw;
  const unit = match[2] || "";
  if (unit.includes("+")) return `${normalizeNumber(match[1], unit.replace("+", ""))}+`;
  return normalizeNumber(match[1], unit);
}

function stripTags(html) {
  return decodeEntities(html.replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " "));
}

function decodeEntities(text) {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCodePoint(parseInt(code, 16)));
}

function sendJson(res, payload) {
  writeCors(res, 200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function writeCors(res, status, headers = {}) {
  res.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Accept, Content-Type",
    ...headers
  });
}

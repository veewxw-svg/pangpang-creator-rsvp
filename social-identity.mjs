const XHS_HOSTS = new Set([
  "xiaohongshu.com",
  "xhslink.com",
  "xhslink.cn",
  "rnote.com",
  "rednote.com"
]);

const INSTAGRAM_HOSTS = new Set(["instagram.com", "instagr.am"]);
const IG_RESERVED = new Set([
  "p", "reel", "reels", "explore", "accounts", "direct", "stories", "share"
]);

const TRACKING_PARAMS = new Set([
  "appuid", "apptime", "share_id", "wechatwid", "wechatorigin",
  "xhsshare", "appshare", "shareredid", "source", "utm_source",
  "utm_medium", "utm_campaign", "igsh"
]);

export const SOCIAL_IDENTITY_VERSION = "2026-07-unified-v2";

export function extractFirstHttpUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const match = raw.match(/https?:\/\/[^\s<>'"）)]+/i);
  return (match?.[0] || raw).replace(/[，。；;！!？?]+$/, "");
}

export function normalizedHost(hostname) {
  return String(hostname || "").replace(/^www\./i, "").toLowerCase();
}

export function isXhsHost(hostname) {
  const host = normalizedHost(hostname);
  return [...XHS_HOSTS].some((item) => host === item || host.endsWith(`.${item}`));
}

export function isInstagramHost(hostname) {
  const host = normalizedHost(hostname);
  return [...INSTAGRAM_HOSTS].some((item) => host === item || host.endsWith(`.${item}`));
}

export function unwrapRedirectUrl(value) {
  const raw = extractFirstHttpUrl(value);
  if (!raw) return "";
  try {
    let current = new URL(raw);
    for (let depth = 0; depth < 4; depth += 1) {
      let nested = "";
      for (const key of ["redirectPath", "redirect", "target", "target_url", "url", "redirect_uri"]) {
        const candidate = current.searchParams.get(key) || "";
        if (/^https?:\/\//i.test(candidate)) {
          nested = candidate;
          break;
        }
      }
      if (!nested) break;
      const next = new URL(nested);
      if (!["http:", "https:"].includes(next.protocol)) break;
      current = next;
    }
    current.hash = "";
    return current.href;
  } catch {
    return "";
  }
}

export function normalizePlatform(value, ...urls) {
  const explicit = String(value || "").trim().toLowerCase();
  if (/小红书|rednote|xiaohongshu|xhs/.test(explicit)) return "小红书";
  if (/instagram|instagr/.test(explicit)) return "Instagram";
  if (/tiktok|抖音/.test(explicit)) return "TikTok";
  if (/facebook|fb/.test(explicit)) return "Facebook";

  for (const value of urls) {
    const raw = unwrapRedirectUrl(value) || extractFirstHttpUrl(value);
    try {
      const host = normalizedHost(new URL(raw).hostname);
      if (isXhsHost(host)) return "小红书";
      if (isInstagramHost(host)) return "Instagram";
      if (/(^|\.)tiktok\.com$/.test(host)) return "TikTok";
      if (/(^|\.)facebook\.com$/.test(host)) return "Facebook";
    } catch {}
  }
  return value || "";
}

function urlCandidates(record = {}) {
  return [
    record.canonicalProfileUrl,
    record.profileUrl,
    record.link,
    record.canonicalPostUrl,
    record.postUrl,
    record.finalUrl,
    record.requestedUrl,
    record.rawUrl
  ].map(unwrapRedirectUrl).filter(Boolean);
}

function pathParts(value) {
  try {
    const url = new URL(value);
    return {
      url,
      host: normalizedHost(url.hostname),
      parts: url.pathname.split("/").filter(Boolean)
    };
  } catch {
    return null;
  }
}

export function xhsCreatorIdFromUrl(value) {
  const parsed = pathParts(unwrapRedirectUrl(value));
  if (!parsed || !isXhsHost(parsed.host)) return "";
  const index = parsed.parts.findIndex((part, i) => part.toLowerCase() === "user" && parsed.parts[i + 1]?.toLowerCase() === "profile");
  return index >= 0 ? decodeURIComponent(parsed.parts[index + 2] || "").toLowerCase() : "";
}

export function xhsPostIdFromUrl(value) {
  const parsed = pathParts(unwrapRedirectUrl(value));
  if (!parsed || !isXhsHost(parsed.host)) return "";
  const first = parsed.parts[0]?.toLowerCase() || "";
  if (first === "explore") return decodeURIComponent(parsed.parts[1] || "").toLowerCase();
  if (first === "discovery" && parsed.parts[1]?.toLowerCase() === "item") {
    return decodeURIComponent(parsed.parts[2] || "").toLowerCase();
  }
  return "";
}

export function instagramCreatorIdFromUrl(value) {
  const parsed = pathParts(unwrapRedirectUrl(value));
  if (!parsed || !isInstagramHost(parsed.host)) return "";
  const segment = decodeURIComponent(parsed.parts[0] || "").replace(/^@/, "").toLowerCase();
  return segment && !IG_RESERVED.has(segment) ? segment : "";
}

export function instagramPostIdFromUrl(value) {
  const parsed = pathParts(unwrapRedirectUrl(value));
  if (!parsed || !isInstagramHost(parsed.host)) return "";
  const kind = parsed.parts[0]?.toLowerCase() || "";
  if (!["p", "reel", "reels"].includes(kind)) return "";
  return decodeURIComponent(parsed.parts[1] || "").toLowerCase();
}

export function normalizeCreatorName(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/^@/, "")
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

export function normalizeHandle(value) {
  return String(value || "").normalize("NFKC").trim().toLowerCase().replace(/^@/, "");
}

export function socialIdentity(record = {}) {
  const candidates = urlCandidates(record);
  const platform = normalizePlatform(record.platform, ...candidates);
  let creatorId = normalizeHandle(record.creatorId);
  let postId = normalizeHandle(record.postId);

  if (platform === "小红书") {
    creatorId ||= candidates.map(xhsCreatorIdFromUrl).find(Boolean) || "";
    postId ||= candidates.map(xhsPostIdFromUrl).find(Boolean) || "";
    const handle = normalizeHandle(record.handle);
    if (!creatorId && /^[a-f0-9]{20,}$/i.test(handle)) creatorId = handle;
  } else if (platform === "Instagram") {
    creatorId ||= candidates.map(instagramCreatorIdFromUrl).find(Boolean) || "";
    postId ||= candidates.map(instagramPostIdFromUrl).find(Boolean) || "";
    if (!creatorId) creatorId = normalizeHandle(record.handle);
  }

  const creatorKey = platform && creatorId ? `${platform.toLowerCase()}:${creatorId}` : "";
  const postKey = platform && postId ? `${platform.toLowerCase()}:${postId}` : "";
  const canonicalProfileUrl = platform === "小红书" && creatorId
    ? `https://www.xiaohongshu.com/user/profile/${creatorId}`
    : platform === "Instagram" && creatorId
      ? `https://www.instagram.com/${creatorId}/`
      : "";
  const canonicalPostUrl = platform === "小红书" && postId
    ? `https://www.xiaohongshu.com/discovery/item/${postId}`
    : "";

  return {
    platform,
    creatorId,
    postId,
    creatorKey,
    postKey,
    canonicalProfileUrl,
    canonicalPostUrl,
    nameKey: normalizeCreatorName(record.name),
    handleKey: normalizeHandle(record.handle)
  };
}

export function withSocialIdentity(record = {}) {
  const identity = socialIdentity(record);
  return {
    ...record,
    platform: identity.platform || record.platform || "",
    creatorId: identity.creatorId,
    postId: identity.postId,
    creatorKey: identity.creatorKey,
    postKey: identity.postKey,
    canonicalProfileUrl: identity.canonicalProfileUrl,
    canonicalPostUrl: identity.canonicalPostUrl
  };
}

export function withPreservedSocialIdentity(preferred = {}, fallback = {}) {
  const merged = { ...preferred };
  for (const field of [
    "creatorId", "postId", "canonicalProfileUrl", "canonicalPostUrl",
    "identityLastAttemptAt", "identityResolvedAt"
  ]) {
    merged[field] = preferred[field] || fallback[field] || "";
  }
  return withSocialIdentity(merged);
}

export function creatorIdentityKey(record = {}) {
  const identity = socialIdentity(record);
  if (identity.creatorKey) return `id:${identity.creatorKey}`;
  if (identity.platform && identity.handleKey) return `handle:${identity.platform.toLowerCase()}:${identity.handleKey}`;
  if (identity.platform && identity.nameKey) return `name:${identity.platform.toLowerCase()}:${identity.nameKey}`;
  return "";
}

export function postIdentityKey(record = {}) {
  const identity = socialIdentity(record);
  if (identity.postKey) return `id:${identity.postKey}`;
  const raw = record.postUrl || "";
  try {
    const url = new URL(unwrapRedirectUrl(raw));
    [...url.searchParams.keys()].forEach((key) => {
      if (TRACKING_PARAMS.has(key.toLowerCase())) url.searchParams.delete(key);
    });
    url.hash = "";
    return `url:${normalizedHost(url.hostname)}${url.pathname.replace(/\/+$/, "").toLowerCase()}`;
  } catch {
    return "";
  }
}

export function sameCreatorIdentity(a = {}, b = {}) {
  const left = socialIdentity(a);
  const right = socialIdentity(b);
  if (left.creatorKey && right.creatorKey) return left.creatorKey === right.creatorKey;
  if (left.platform && right.platform && left.platform !== right.platform) return false;
  if (left.handleKey && right.handleKey && left.handleKey === right.handleKey) return true;
  return Boolean(left.nameKey && right.nameKey && left.nameKey === right.nameKey);
}

export function selectBestCreatorMatch(candidates = [], postRecord = {}, options = {}) {
  const matches = (Array.isArray(candidates) ? candidates : []).filter((item) => sameCreatorIdentity(item, postRecord));
  if (!matches.length) return null;
  if (matches.length === 1) return matches[0];

  const selectedDate = normalizeIsoDate(options.selectedDate);
  if (selectedDate) {
    const selectedMatches = matches.filter((item) => normalizeIsoDate(item.dateISO) === selectedDate);
    if (selectedMatches.length) return sortBookings(selectedMatches, "desc")[0];
  }

  const postDate = normalizeIsoDate(postRecord.postPublishedAt || postRecord.postDateText);
  const referenceDate = postDate || normalizeIsoDate(options.todayISO);
  const datedMatches = matches.filter((item) => normalizeIsoDate(item.dateISO));
  if (referenceDate && datedMatches.length) {
    const pastOrToday = datedMatches.filter((item) => normalizeIsoDate(item.dateISO) <= referenceDate);
    if (pastOrToday.length) return sortBookings(pastOrToday, "desc")[0];
  }
  if (datedMatches.length) return sortBookings(datedMatches, "asc")[0];
  return matches[0];
}

function normalizeIsoDate(value) {
  const raw = String(value || "").trim();
  const direct = raw.match(/^\d{4}-\d{2}-\d{2}/)?.[0] || "";
  if (direct) return direct;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString().slice(0, 10) : "";
}

function sortBookings(records, direction) {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...records].sort((a, b) => {
    const left = `${normalizeIsoDate(a.dateISO)}T${timeSortValue(a.timeText)}`;
    const right = `${normalizeIsoDate(b.dateISO)}T${timeSortValue(b.timeText)}`;
    return left.localeCompare(right) * multiplier;
  });
}

function timeSortValue(value) {
  const raw = String(value || "").trim().toLowerCase();
  const match = raw.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/);
  if (!match) return "00:00";
  let hour = Number(match[1]);
  const minute = Number(match[2] || 0);
  if (match[3] === "am" && hour === 12) hour = 0;
  if (match[3] === "pm" && hour < 12) hour += 12;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

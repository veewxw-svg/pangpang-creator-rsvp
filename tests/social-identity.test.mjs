import test from "node:test";
import assert from "node:assert/strict";
import {
  creatorIdentityKey,
  normalizeCreatorName,
  postIdentityKey,
  sameCreatorIdentity,
  selectBestCreatorMatch,
  socialIdentity,
  unwrapRedirectUrl,
  withPreservedSocialIdentity,
  withSocialIdentity,
  xhsCreatorIdFromUrl,
  xhsPostIdFromUrl
} from "../social-identity.mjs";

const XHS_LOGIN_REDIRECT = "https://www.xiaohongshu.com/login?redirectPath=https%3A%2F%2Fwww.xiaohongshu.com%2Fuser%2Fprofile%2F5aae5b63e8ac2b1829f5bbd0%3Fxsec_token%3Dtoken%26xsec_source%3Dapp_share";

test("unwraps the Xiaohongshu login redirect before reading identity", () => {
  assert.match(unwrapRedirectUrl(XHS_LOGIN_REDIRECT), /\/user\/profile\/5aae5b63e8ac2b1829f5bbd0/);
  assert.equal(xhsCreatorIdFromUrl(XHS_LOGIN_REDIRECT), "5aae5b63e8ac2b1829f5bbd0");
});

test("normalizes Xiaohongshu, rnote and rednote profile hosts to one creator id", () => {
  const urls = [
    "https://www.xiaohongshu.com/user/profile/658d6fd9000000002200be0a?xsec_token=a",
    "https://www.rnote.com/user/profile/658d6fd9000000002200be0a?xsec_token=b",
    "https://www.rednote.com/user/profile/658d6fd9000000002200be0a?xsec_token=c"
  ];
  const keys = urls.map((link) => creatorIdentityKey({ platform: "小红书", link }));
  assert.deepEqual(new Set(keys).size, 1);
  assert.equal(keys[0], "id:小红书:658d6fd9000000002200be0a");
});

test("normalizes explore and discovery post URLs to one post id", () => {
  const explore = "https://www.xiaohongshu.com/explore/6a6c5567000000003302c340?xsec_token=a&share_id=one";
  const discovery = "https://www.xiaohongshu.com/discovery/item/6a6c5567000000003302c340?xsec_token=b&share_id=two";
  assert.equal(xhsPostIdFromUrl(explore), "6a6c5567000000003302c340");
  assert.equal(postIdentityKey({ platform: "小红书", postUrl: explore }), postIdentityKey({ platform: "小红书", postUrl: discovery }));
});

test("matches the same creator by stable id even when names and links differ", () => {
  const booking = {
    platform: "小红书",
    name: "小茄子mm",
    link: XHS_LOGIN_REDIRECT
  };
  const post = {
    platform: "小红书",
    name: "小茄子mm🍆",
    profileUrl: "https://www.rednote.com/user/profile/5aae5b63e8ac2b1829f5bbd0"
  };
  assert.equal(sameCreatorIdentity(booking, post), true);
});

test("does not match two different stable ids even if the visible names are equal", () => {
  const a = { platform: "小红书", name: "同名博主", creatorId: "aaaaaaaaaaaaaaaaaaaaaaaa" };
  const b = { platform: "小红书", name: "同名博主", creatorId: "bbbbbbbbbbbbbbbbbbbbbbbb" };
  assert.equal(sameCreatorIdentity(a, b), false);
});

test("uses emoji-insensitive name matching only when no stable id exists", () => {
  assert.equal(normalizeCreatorName("小茄子mm🍆"), normalizeCreatorName(" 小茄子 mm "));
  assert.equal(
    sameCreatorIdentity({ platform: "小红书", name: "小茄子mm" }, { platform: "小红书", name: "小茄子mm🍆" }),
    true
  );
});

test("keeps unresolved short links unresolved instead of inventing an id", () => {
  const identity = socialIdentity({ link: "https://xhslink.cn/m/5QU5z8eeiHE", platform: "小红书" });
  assert.equal(identity.creatorId, "");
  assert.equal(identity.postId, "");
});

test("normalizes Instagram profile and reel identity", () => {
  const profile = withSocialIdentity({
    platform: "Instagram",
    link: "https://www.instagram.com/fooddiary._.sg/?utm_source=share"
  });
  const reelA = { platform: "Instagram", postUrl: "https://www.instagram.com/reel/DaR7EIkpGTB/?utm_source=share" };
  const reelB = { platform: "Instagram", postUrl: "https://instagram.com/reels/DaR7EIkpGTB/?igsh=abc" };
  assert.equal(profile.creatorId, "fooddiary._.sg");
  assert.equal(profile.creatorKey, "instagram:fooddiary._.sg");
  assert.equal(postIdentityKey(reelA), postIdentityKey(reelB));
});

test("decorates records with durable keys without replacing display URLs", () => {
  const link = "https://www.rednote.com/user/profile/5a98f57f11be10259c1b4bfd?xsec_token=token";
  const record = withSocialIdentity({ platform: "小红书", link, name: "Morain今天没吃胖" });
  assert.equal(record.link, link);
  assert.equal(record.creatorId, "5a98f57f11be10259c1b4bfd");
  assert.equal(record.creatorKey, "小红书:5a98f57f11be10259c1b4bfd");
  assert.equal(record.canonicalProfileUrl, "https://www.xiaohongshu.com/user/profile/5a98f57f11be10259c1b4bfd");
});

test("does not let an older client erase a server-confirmed creator id", () => {
  const existing = withSocialIdentity({
    platform: "小红书",
    link: "https://xhslink.cn/m/7ZQuF5qoGRh",
    creatorId: "5aabbf2511be10578c33b2e9",
    identityResolvedAt: "2026-07-31T11:00:00.000Z"
  });
  const staleClient = { ...existing, creatorId: "", creatorKey: "", canonicalProfileUrl: "" };
  const merged = withPreservedSocialIdentity(staleClient, existing);
  assert.equal(merged.creatorId, "5aabbf2511be10578c33b2e9");
  assert.equal(merged.creatorKey, "小红书:5aabbf2511be10578c33b2e9");
  assert.equal(merged.identityResolvedAt, "2026-07-31T11:00:00.000Z");
});

test("selects the latest matching visit on or before the post date", () => {
  const creatorId = "5aabbf2511be10578c33b2e9";
  const candidates = [
    { id: "past", platform: "小红书", creatorId, dateISO: "2026-07-29", timeText: "3:00 pm" },
    { id: "future", platform: "小红书", creatorId, dateISO: "2026-08-10", timeText: "7:00 pm" }
  ];
  const post = { platform: "小红书", creatorId, postPublishedAt: "2026-07-31T08:00:00+08:00" };
  assert.equal(selectBestCreatorMatch(candidates, post, { todayISO: "2026-07-31" })?.id, "past");
});

test("uses the selected date when the same creator has several unmatched visits", () => {
  const creatorId = "5aabbf2511be10578c33b2e9";
  const candidates = [
    { id: "one", platform: "小红书", creatorId, dateISO: "2026-07-29", timeText: "3:00 pm" },
    { id: "two", platform: "小红书", creatorId, dateISO: "2026-08-10", timeText: "7:00 pm" }
  ];
  assert.equal(selectBestCreatorMatch(candidates, { platform: "小红书", creatorId }, { selectedDate: "2026-08-10" })?.id, "two");
});

test("chooses the nearest upcoming visit when no matching past visit exists", () => {
  const creatorId = "5aabbf2511be10578c33b2e9";
  const candidates = [
    { id: "later", platform: "小红书", creatorId, dateISO: "2026-08-12", timeText: "7:00 pm" },
    { id: "next", platform: "小红书", creatorId, dateISO: "2026-08-10", timeText: "7:00 pm" }
  ];
  assert.equal(selectBestCreatorMatch(candidates, { platform: "小红书", creatorId }, { todayISO: "2026-07-31" })?.id, "next");
});

import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from PIL import Image, ImageDraw, ImageFont


RECORDS = Path(os.environ.get("PANGPANG_RECORDS_JSON", "data/records.json"))
OUT = Path(os.environ.get("PANGPANG_REPORT_OUT", "output/pangpang_creator_report.png"))
HIGHLIGHT_IDS = {item.strip() for item in os.environ.get("PANGPANG_HIGHLIGHT_IDS", "").split(",") if item.strip()}
FONT_REG_CANDIDATES = [
    os.environ.get("PANGPANG_FONT_REG", ""),
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_BOLD_CANDIDATES = [
    os.environ.get("PANGPANG_FONT_BOLD", ""),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size, bold=False):
    for path in (FONT_BOLD_CANDIDATES if bold else FONT_REG_CANDIDATES):
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def normalize_status(value):
    if value == "已发布":
        return "已发布"
    if value == "取消":
        return "取消"
    return "新增"


def normalize_loose(value):
    return "".join(str(value or "").strip().lower().split())


def canonical_web_parts(value):
    raw = str(value or "").strip()
    if not raw:
        return "", ""
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "", ""
        host = parsed.netloc.lower().removeprefix("www.")
        query = parse_qs(parsed.query)
        redirect_path = (query.get("redirectPath") or [""])[0]
        if is_domain(host, "xiaohongshu.com") and parsed.path.rstrip("/").lower() == "/login" and redirect_path:
            nested = urlparse(redirect_path)
            nested_host = nested.netloc.lower().removeprefix("www.")
            if nested.scheme in {"http", "https"} and is_domain(nested_host, "xiaohongshu.com"):
                parsed = nested
                host = nested_host
        path = parsed.path.rstrip("/").lower()
        return host, path
    except Exception:
        return "", ""


def is_domain(host, domain):
    return host == domain or host.endswith(f".{domain}")


def creator_identity(record):
    host, path = canonical_web_parts(record.get("link") or record.get("profileUrl") or "")
    is_creator_url = (
        (is_domain(host, "xiaohongshu.com") and path.startswith("/user/profile/") and len(path.split("/")) == 4)
        or (is_domain(host, "instagram.com") and instagram_creator_path(path))
        or (is_domain(host, "tiktok.com") and path.startswith("/@") and len(path.split("/")) == 2)
        or (is_domain(host, "facebook.com") and path and not path.startswith(("/share", "/watch", "/reel", "/photo")))
    )
    if is_creator_url:
        return f"url:{host}{path}"
    platform = normalize_loose(record.get("platform"))
    handle = normalize_loose(str(record.get("handle") or "").lstrip("@"))
    if platform and handle:
        return f"handle:{platform}:{handle}"
    name = normalize_loose(record.get("name"))
    return f"name:{platform}:{name}" if platform and name else ""


def instagram_creator_path(path):
    segment = next((part for part in path.split("/") if part), "")
    return bool(segment and segment not in {"p", "reel", "reels", "explore", "accounts", "direct", "stories", "share"})


def post_identity(value):
    host, path = canonical_web_parts(value)
    is_post_url = (
        (is_domain(host, "xiaohongshu.com") and (path.startswith("/explore/") or path.startswith("/discovery/item/")))
        or (is_domain(host, "xhslink.com") and bool(path))
        or (is_domain(host, "instagram.com") and path.startswith(("/p/", "/reel/", "/reels/")))
        or (is_domain(host, "tiktok.com") and "/video/" in path)
    )
    return f"{host}{path}" if is_post_url else ""


def duplicate_keys(record):
    if not record or normalize_status(record.get("status")) == "取消":
        return []
    keys = []
    post = post_identity(record.get("postUrl") or "")
    if post:
        keys.append(f"post:{post}")
    creator = creator_identity(record)
    date = normalize_loose(record.get("dateISO") or record.get("dateText") or "")
    visit_time = normalize_loose(record.get("timeText") or "")
    if creator and record.get("type") != "post" and date and visit_time:
        keys.append(f"booking:{creator}:{date}:{visit_time}")
    return keys


def duplicate_ids(records):
    counts = {}
    for record in records:
        for key in duplicate_keys(record):
            counts[key] = counts.get(key, 0) + 1
    return {
        str(record.get("id") or "")
        for record in records
        if any(counts.get(key, 0) > 1 for key in duplicate_keys(record))
    }


def sort_minutes(value):
    raw = str(value or "").lower().strip()
    if not raw:
        return 9999
    parts = raw.replace("am", "").replace("pm", "").strip().split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return 9999
    if "pm" in raw and hour < 12:
        hour += 12
    if "am" in raw and hour == 12:
        hour = 0
    return hour * 60 + minute


def status_sort_rank(record):
    return 1 if normalize_status(record.get("status")) == "已发布" else 0


def is_invalid_draft(record):
    return (
        not record.get("dateISO")
        and not record.get("timeText")
        and not record.get("phone")
        and (not record.get("name") or record.get("name") == "待补")
        and not record.get("followers")
        and not record.get("engagement")
    )


def display_name(record):
    name = record.get("name") or ""
    handle = str(record.get("handle") or "").lstrip("@")
    if name:
        return name
    if handle and not (len(handle) >= 20 and all(c in "0123456789abcdefABCDEF" for c in handle)):
        return f"@{handle}"
    return "待补"


def link_status(record):
    if record.get("postUrl") and record.get("link"):
        return "查看主页 / 查看帖子"
    if record.get("postUrl"):
        return "查看帖子"
    if record.get("link"):
        return "查看主页"
    return "待补"


def payment_text(record):
    visit_type = record.get("visitType") or ""
    if not visit_type:
        return ""
    if visit_type != "付费探店":
        return visit_type
    amount = record.get("feeAmount") or ""
    return f"付费探店：{amount}" if amount else "付费探店"


def is_highlighted(record):
    record_id = str(record.get("id") or "")
    return record_id in HIGHLIGHT_IDS


def short_text(value, max_chars):
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"


def wrap_text(draw, text, font_obj, max_width, max_lines=2):
    raw = str(text or "")
    if not raw:
        return [""]
    if " " in raw:
        lines = []
        current = ""
        for word in raw.split(" "):
            test = f"{current} {word}".strip()
            if draw.textlength(test, font=font_obj) <= max_width or not current:
                current = test
            else:
                lines.append(current)
                current = word
                if len(lines) >= max_lines - 1:
                    break
        if len(lines) >= max_lines - 1:
            remaining = " ".join(raw.split(" ")[sum(len(line.split(" ")) for line in lines):])
            current = remaining or current
            while current and draw.textlength(current, font=font_obj) > max_width:
                current = " ".join(current.split(" ")[:-1]) or current[:-1]
        if current:
            lines.append(current)
        return lines[:max_lines]
    lines = []
    current = ""
    for char in raw:
        test = current + char
        if draw.textlength(test, font=font_obj) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = char
            if len(lines) >= max_lines - 1:
                break
    if len(lines) >= max_lines - 1:
        remaining = raw[sum(len(line) for line in lines):]
        current = remaining
        while current and draw.textlength(current, font=font_obj) > max_width:
            current = current[:-1]
    if current:
        lines.append(current)
    return lines[:max_lines]


def draw_cell(draw, x, y, width, text, fill, font, max_lines=2):
    lines = wrap_text(draw, text, font, width, max_lines)
    for line_index, line in enumerate(lines):
        draw.text((x, y + line_index * 30), line, fill=fill, font=font)


def date_title(record):
    return record.get("dateText") or record.get("dateISO") or "未填日期"


try:
    records = json.loads(RECORDS.read_text("utf-8"))
    if not isinstance(records, list):
        records = []
except Exception:
    records = []

records = [record for record in records if not is_invalid_draft(record)]
records = sorted(records, key=lambda r: (status_sort_rank(r), r.get("dateISO") or "9999-99-99", sort_minutes(r.get("timeText"))))
DUPLICATE_IDS = duplicate_ids(records)

W = 2480
row_h = 108
date_h = 58
header_h = 440
footer_h = 180
days = []
last = None
for record in records:
    key = record.get("dateISO") or "undated"
    if key != last:
        days.append(key)
        last = key
H = max(1200, header_h + len(records) * row_h + len(days) * date_h + footer_h)

img = Image.new("RGB", (W, H), "#ffffff")
d = ImageDraw.Draw(img)

black = "#1d1d1f"
muted = "#6e6e73"
line = "#e5e5ea"
header_bg = "#f5f5f7"
blue_row = "#eef6ff"
green_row = "#effaf2"
red_row = "#fff1f1"
orange_row = "#fff8e8"
red = "#d70015"
green = "#248a3d"
blue = "#0071e3"
purple = "#5856d6"

title_f = font(56, True)
sub_f = font(25)
head_f = font(23, True)
body_f = font(24)
small_f = font(20)
tiny_f = font(18)

d.text((70, 54), "PangPang 博主探店预约全局表", fill=black, font=title_f)
d.text((70, 124), "邮件通知版｜按预约时间排序｜日报只高亮当天变动｜长链接隐藏成查看按钮", fill=muted, font=sub_f)

d.rounded_rectangle((70, 174, 2410, 300), radius=24, fill=header_bg)
metrics = [
    ("总记录", str(len(records))),
    ("新增", str(sum(1 for r in records if normalize_status(r.get("status")) == "新增"))),
    ("已发布", str(sum(1 for r in records if normalize_status(r.get("status")) == "已发布"))),
    ("取消", str(sum(1 for r in records if normalize_status(r.get("status")) == "取消"))),
    ("本次高亮", str(sum(1 for r in records if is_highlighted(r)))),
]
mx = 110
for label, value in metrics:
    d.text((mx, 198), value, fill=black, font=font(36, True))
    d.text((mx, 244), label, fill=muted, font=small_f)
    mx += 445

cols = [
    ("状态", 90),
    ("预约时间", 170),
    ("博主", 285),
    ("平台", 120),
    ("粉丝", 105),
    ("赞/数据", 285),
    ("帖子数据", 300),
    ("人数", 60),
    ("电话", 135),
    ("博主状态", 140),
    ("发帖日期", 205),
    ("链接", 170),
    ("备注", 65),
]

x0, y = 70, 350
right = 2410
d.rounded_rectangle((x0, y, right, y + row_h), radius=16, fill=header_bg)
x = x0 + 18
for name, width in cols:
    d.text((x, y + 29), name, fill=muted, font=head_f)
    x += width
y += row_h

last_date = None
for record in records:
    date = date_title(record)
    if date != last_date:
        d.text((x0 + 8, y + 22), date, fill=black, font=font(30, True))
        y += date_h
        last_date = date

    status = normalize_status(record.get("status"))
    highlighted = is_highlighted(record)
    duplicate = str(record.get("id") or "") in DUPLICATE_IDS
    if status == "已发布" and highlighted:
        fill = green_row
    elif status == "取消":
        fill = red_row
    elif highlighted:
        fill = blue_row
    elif duplicate:
        fill = orange_row
    else:
        fill = "#ffffff"

    d.rounded_rectangle((x0, y, right, y + row_h - 8), radius=12, fill=fill)
    d.line((x0 + 16, y + row_h - 8, right - 16, y + row_h - 8), fill=line, width=1)

    values = [
        " / ".join([status, "重复"] if duplicate else [status]),
        record.get("timeText") or "-",
        display_name(record),
        record.get("platform") or "待补",
        record.get("followers") or "待补",
        record.get("engagement") or "待补",
        record.get("postMetricsText") or "待补",
        record.get("pax") or "待补",
        record.get("phone") or "待补",
        payment_text(record) or "待补",
        record.get("postDateText") or "-",
        link_status(record),
        record.get("remarks") or "",
    ]

    x = x0 + 18
    for idx, ((_, width), value) in enumerate(zip(cols, values)):
        color = black
        if value == "取消":
            color = red
        elif "已发布" in str(value):
            color = purple
        elif "查看" in str(value):
            color = blue
        elif idx == 8 and value != "-":
            color = green

        f = body_f
        if idx in (3, 5, 6, 8, 9, 10):
            f = small_f
        if idx == 0:
            f = font(22, True)

        draw_cell(d, x, y + 22, width - 8, str(value), fill=color, font=f, max_lines=2)
        x += width

    y += row_h

d.rounded_rectangle((70, H - 160, 2410, H - 72), radius=22, fill=header_bg)
d.text((102, H - 133), "颜色说明：浅蓝=本次新增预约｜浅绿=本次发帖更新｜浅红=取消但保留记录｜浅橙=重复博主。", fill=muted, font=small_f)
d.text((70, H - 40), "后台保留完整数据；这张 PNG 用来给手机和电脑快速看全局。", fill=muted, font=tiny_f)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(OUT)

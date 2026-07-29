import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


RECORDS = Path(os.environ.get("PANGPANG_RECORDS_JSON", "data/records.json"))
OUT = Path(os.environ.get("PANGPANG_REPORT_PDF_OUT", "output/pangpang_creator_report.pdf"))
HIGHLIGHT_IDS = {item.strip() for item in os.environ.get("PANGPANG_HIGHLIGHT_IDS", "").split(",") if item.strip()}
REPORT_DATE = os.environ.get("PANGPANG_REPORT_DATE", "")

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
    if value == "爽约":
        return "爽约"
    return "新增"


def is_archived_record(record):
    return bool(
        record
        and (
            record.get("archived")
            or record.get("cancelReason") in {"填错", "改约"}
        )
    )


def is_inactive_record(record):
    return is_archived_record(record) or normalize_status(record.get("status")) in {"取消", "爽约"}


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
    if not record or is_inactive_record(record):
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
    return {"新增": 0, "取消": 1, "爽约": 2, "已发布": 3}.get(normalize_status(record.get("status")), 0)


def is_invalid_draft(record):
    return (
        not record.get("dateISO")
        and not record.get("timeText")
        and not record.get("phone")
        and not record.get("pax")
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


def date_title(record):
    english = record.get("dateText") or ""
    chinese = chinese_date(record.get("dateISO") or "")
    if english and chinese:
        return f"{english} · {chinese}"
    return english or chinese or record.get("dateISO") or "未填日期"


def chinese_date(date_iso):
    if not date_iso:
        return ""
    try:
        date = datetime.strptime(str(date_iso)[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    week = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][date.weekday()]
    return f"{date.year}年{date.month}月{date.day}日 {week}"


def wrap_text(draw, text, font_obj, max_width, max_lines=2):
    raw = str(text or "")
    if not raw:
        return [""]
    tokens = raw.split(" ") if " " in raw else list(raw)
    sep = " " if " " in raw else ""
    lines = []
    current = ""
    for token in tokens:
        test = f"{current}{sep}{token}".strip() if sep else current + token
        if draw.textlength(test, font=font_obj) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = token
            if len(lines) >= max_lines - 1:
                break
    if current:
        while draw.textlength(current, font=font_obj) > max_width and len(current) > 1:
            current = current[:-1]
        lines.append(current)
    return lines[:max_lines]


def draw_wrapped(draw, xy, text, font_obj, fill, max_width, max_lines=2, line_gap=8):
    x, y = xy
    for index, line in enumerate(wrap_text(draw, text, font_obj, max_width, max_lines)):
        draw.text((x, y + index * (font_obj.size + line_gap)), line, fill=fill, font=font_obj)


def draw_chip(draw, x, y, text, fill, color, font_obj):
    pad_x = 14
    pad_y = 7
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    width = bbox[2] - bbox[0] + pad_x * 2
    height = bbox[3] - bbox[1] + pad_y * 2
    draw.rounded_rectangle((x, y, x + width, y + height), radius=height // 2, fill=fill)
    draw.text((x + pad_x, y + pad_y - 2), text, fill=color, font=font_obj)
    return width


def draw_button(draw, x, y, label):
    width = 128
    height = 42
    draw.rounded_rectangle((x, y, x + width, y + height), radius=21, fill="#ffffff", outline="#d2d2d7", width=2)
    tw = draw.textlength(label, font=BUTTON_FONT)
    draw.text((x + (width - tw) / 2, y + 9), label, fill=BLUE, font=BUTTON_FONT)
    return (x, y, width, height)


def safe_records():
    try:
        records = json.loads(RECORDS.read_text("utf-8"))
        if isinstance(records, list):
            return records
    except Exception:
        pass
    return []


records = [record for record in safe_records() if not is_invalid_draft(record) and not is_archived_record(record)]
records = sorted(records, key=lambda r: (status_sort_rank(r), r.get("dateISO") or "9999-99-99", sort_minutes(r.get("timeText"))))
duplicate_set = duplicate_ids(records)

SCALE = 2
PAGE_W_PT, PAGE_H_PT = landscape(A4)
PAGE_W = int(PAGE_W_PT * SCALE)
PAGE_H = int(PAGE_H_PT * SCALE)
M = 48
HEADER_H = 228
DATE_H = 48
CARD_H = 158
GAP = 10

BLACK = "#1d1d1f"
MUTED = "#6e6e73"
SOFT = "#8e8e93"
BLUE = "#0071e3"
GREEN = "#248a3d"
PURPLE = "#5856d6"
RED = "#d70015"
YELLOW = "#a86f00"
PANEL = "#f5f5f7"
LINE = "#e5e5ea"
BLUE_ROW = "#eef6ff"
GREEN_ROW = "#effaf2"
RED_ROW = "#fff1f1"
ORANGE_ROW = "#fff8e8"

TITLE_FONT = font(42, True)
SUB_FONT = font(18)
METRIC_FONT = font(28, True)
METRIC_LABEL_FONT = font(14)
DATE_FONT = font(25, True)
NAME_FONT = font(24, True)
BODY_FONT = font(18)
SMALL_FONT = font(16)
CHIP_FONT = font(15, True)
BUTTON_FONT = font(17, True)


def new_page():
    image = Image.new("RGB", (PAGE_W, PAGE_H), "#ffffff")
    draw = ImageDraw.Draw(image)
    links = []
    return image, draw, links


def draw_header(draw):
    title = REPORT_DATE or "PP博主更新"
    draw.text((M, 36), title, fill=BLACK, font=TITLE_FONT)
    y = 106
    metric_h = 90
    draw.rounded_rectangle((M, y, PAGE_W - M, y + metric_h), radius=22, fill=PANEL)
    metrics = [
        ("总记录", len(records)),
        ("新增", sum(1 for r in records if normalize_status(r.get("status")) == "新增")),
        ("已发布", sum(1 for r in records if normalize_status(r.get("status")) == "已发布")),
        ("取消", sum(1 for r in records if normalize_status(r.get("status")) == "取消")),
        ("爽约", sum(1 for r in records if normalize_status(r.get("status")) == "爽约")),
        ("重复", len(duplicate_set)),
    ]
    x = M + 34
    step = (PAGE_W - M * 2 - 68) / 6
    for label, value in metrics:
        draw.text((x, y + 12), str(value), fill=BLACK, font=METRIC_FONT)
        draw.text((x, y + 54), label, fill=SOFT, font=METRIC_LABEL_FONT)
        x += step


def row_fill(record):
    status = normalize_status(record.get("status"))
    highlighted = is_highlighted(record)
    duplicate = str(record.get("id") or "") in duplicate_set
    if status == "取消":
        return RED_ROW
    if status == "爽约":
        return ORANGE_ROW
    if status == "已发布" and highlighted:
        return GREEN_ROW
    if highlighted:
        return BLUE_ROW
    if duplicate:
        return ORANGE_ROW
    return "#ffffff"


def add_link(links, rect, url):
    if not url:
        return
    x, y, w, h = rect
    links.append((url, x / SCALE, (PAGE_H - y - h) / SCALE, (x + w) / SCALE, (PAGE_H - y) / SCALE))


def draw_record(draw, links, record, y):
    status = normalize_status(record.get("status"))
    duplicate = str(record.get("id") or "") in duplicate_set
    x0 = M
    x1 = PAGE_W - M
    draw.rounded_rectangle((x0, y, x1, y + CARD_H), radius=18, fill=row_fill(record), outline=LINE, width=1)

    status_color = PURPLE if status == "已发布" else RED if status == "取消" else YELLOW if status == "爽约" else GREEN
    draw.text((x0 + 24, y + 24), record.get("timeText") or "--", fill=BLACK, font=NAME_FONT)
    draw.text((x0 + 24, y + 60), f"{record.get('pax') or '?'} pax", fill=SOFT, font=BODY_FONT)
    chip_fill = "#e8f3ec" if status == "新增" else "#ececff" if status == "已发布" else "#fff0d6" if status == "爽约" else "#ffe8ea"
    draw_chip(draw, x0 + 24, y + 94, status, chip_fill, status_color, CHIP_FONT)
    if duplicate:
        draw_chip(draw, x0 + 94, y + 94, "重复", "#fff0d6", YELLOW, CHIP_FONT)

    main_x = x0 + 178
    button_x = x1 - 300
    max_main_width = button_x - main_x - 28
    draw_wrapped(draw, (main_x, y + 18), display_name(record), NAME_FONT, BLACK, max_main_width, 1)
    line_one = [
        record.get("platform") or "",
        f"粉丝 {record.get('followers')}" if record.get("followers") else "",
        f"{'数据' if record.get('platform') == 'Instagram' else '赞藏'} {record.get('engagement')}" if record.get("engagement") else "",
    ]
    line_two = [
        f"帖子数据 {record.get('postMetricsText')}" if record.get("postMetricsText") else "",
        f"发帖 {record.get('postDateText')}" if record.get("postDateText") else "",
        payment_text(record),
        f"电话 {record.get('phone')}" if record.get("phone") else "",
        f"处理原因 {record.get('cancelReason')}" if record.get("cancelReason") else "",
    ]
    if duplicate:
        line_one.insert(0, "重复博主")
    draw_wrapped(draw, (main_x, y + 56), " · ".join([item for item in line_one if item]) or "资料待补", BODY_FONT, MUTED, max_main_width, 1)
    draw_wrapped(draw, (main_x, y + 86), " · ".join([item for item in line_two if item]) or "资料待补", BODY_FONT, MUTED, max_main_width, 1)
    remarks = record.get("remarks") or ""
    if remarks:
        draw_wrapped(draw, (main_x, y + 118), remarks, SMALL_FONT, SOFT, max_main_width, 1)

    button_y = y + 32
    if record.get("link"):
        add_link(links, draw_button(draw, button_x, button_y, "查看主页"), record.get("link"))
        button_y += 52
    if record.get("postUrl"):
        add_link(links, draw_button(draw, button_x, button_y, "查看帖子"), record.get("postUrl"))


OUT.parent.mkdir(parents=True, exist_ok=True)
pdf = canvas.Canvas(str(OUT), pagesize=landscape(A4))
page_images = []

image, draw, links = new_page()
draw_header(draw)
y = HEADER_H
last_date = None

if not records:
    draw.text((M, HEADER_H + 80), "暂无记录", fill=MUTED, font=DATE_FONT)

for record in records:
    needs_date = date_title(record) != last_date
    needed = CARD_H + GAP + (DATE_H if needs_date else 0)
    if y + needed > PAGE_H - 54:
        page_images.append((image, links))
        image, draw, links = new_page()
        draw_header(draw)
        y = HEADER_H
        last_date = None
        needs_date = True

    if needs_date:
        draw.text((M + 8, y + 8), date_title(record), fill=BLACK, font=DATE_FONT)
        y += DATE_H
        last_date = date_title(record)

    draw_record(draw, links, record, y)
    y += CARD_H + GAP

page_images.append((image, links))

with tempfile.TemporaryDirectory() as tmp:
    for index, (image, links) in enumerate(page_images):
        path = Path(tmp) / f"page_{index}.png"
        image.save(path)
        pdf.drawImage(ImageReader(str(path)), 0, 0, width=PAGE_W_PT, height=PAGE_H_PT)
        for url, x1, y1, x2, y2 in links:
            pdf.linkURL(url, (x1, y1, x2, y2), relative=0, thickness=0, color=None)
        if index < len(page_images) - 1:
            pdf.showPage()

pdf.save()
print(OUT)

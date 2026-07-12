import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


RECORDS = Path(os.environ.get("PANGPANG_RECORDS_JSON", "data/records.json"))
OUT = Path(os.environ.get("PANGPANG_REPORT_PDF_OUT", "output/pangpang_creator_report.pdf"))
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


def normalize_profile_url(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.netloc or parsed.path:
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/").lower()
        return f"{host}{path}" if host or path else ""
    return normalize_loose(raw.split("?")[0].split("#")[0])


def duplicate_key(record):
    if not record or normalize_status(record.get("status")) == "取消":
        return ""
    profile = normalize_profile_url(record.get("link") or record.get("profileUrl") or "")
    if profile:
        return f"url:{profile}"
    platform = normalize_loose(record.get("platform"))
    handle = normalize_loose(str(record.get("handle") or "").lstrip("@"))
    if platform and handle:
        return f"handle:{platform}:{handle}"
    name = normalize_loose(record.get("name"))
    return f"name:{platform}:{name}" if platform and name else ""


def duplicate_ids(records):
    counts = {}
    for record in records:
        key = duplicate_key(record)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return {str(record.get("id") or "") for record in records if counts.get(duplicate_key(record), 0) > 1}


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


def date_title(record):
    return record.get("dateText") or record.get("dateISO") or "未填日期"


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


records = [record for record in safe_records() if not is_invalid_draft(record)]
records = sorted(records, key=lambda r: (status_sort_rank(r), r.get("dateISO") or "9999-99-99", sort_minutes(r.get("timeText"))))
duplicate_set = duplicate_ids(records)

SCALE = 2
PAGE_W_PT, PAGE_H_PT = landscape(A4)
PAGE_W = int(PAGE_W_PT * SCALE)
PAGE_H = int(PAGE_H_PT * SCALE)
M = 48
HEADER_H = 252
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
    draw.text((M, 36), "PangPang 博主探店预约全局表", fill=BLACK, font=TITLE_FONT)
    draw.text((M, 90), "PDF 邮件版｜按预约时间排序｜按钮可点击打开主页或帖子", fill=MUTED, font=SUB_FONT)
    y = 124
    metric_h = 90
    draw.rounded_rectangle((M, y, PAGE_W - M, y + metric_h), radius=22, fill=PANEL)
    metrics = [
        ("总记录", len(records)),
        ("新增", sum(1 for r in records if normalize_status(r.get("status")) == "新增")),
        ("已发布", sum(1 for r in records if normalize_status(r.get("status")) == "已发布")),
        ("取消", sum(1 for r in records if normalize_status(r.get("status")) == "取消")),
        ("重复", len(duplicate_set)),
    ]
    x = M + 34
    step = (PAGE_W - M * 2 - 68) / 5
    for label, value in metrics:
        draw.text((x, y + 12), str(value), fill=BLACK, font=METRIC_FONT)
        draw.text((x, y + 54), label, fill=SOFT, font=METRIC_LABEL_FONT)
        x += step


def row_fill(record):
    status = normalize_status(record.get("status"))
    highlighted = str(record.get("id") or "") in HIGHLIGHT_IDS
    duplicate = str(record.get("id") or "") in duplicate_set
    if status == "取消":
        return RED_ROW
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

    status_color = PURPLE if status == "已发布" else RED if status == "取消" else GREEN
    draw.text((x0 + 24, y + 24), record.get("timeText") or "--", fill=BLACK, font=NAME_FONT)
    draw.text((x0 + 24, y + 60), f"{record.get('pax') or '?'} pax", fill=SOFT, font=BODY_FONT)
    draw_chip(draw, x0 + 24, y + 94, status, "#e8f3ec" if status == "新增" else "#ececff" if status == "已发布" else "#ffe8ea", status_color, CHIP_FONT)
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

import json
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


RECORDS = Path(os.environ.get("PANGPANG_RECORDS_JSON", "data/records.json"))
OUT = Path(os.environ.get("PANGPANG_REPORT_PDF_OUT", "output/pangpang_creator_report.pdf"))
HIGHLIGHT_IDS = {item.strip() for item in os.environ.get("PANGPANG_HIGHLIGHT_IDS", "").split(",") if item.strip()}

FONT_REG_CANDIDATES = [
    os.environ.get("PANGPANG_FONT_REG", ""),
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]
FONT_BOLD_CANDIDATES = [
    os.environ.get("PANGPANG_FONT_BOLD", ""),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def register_font(name, candidates):
    for path in candidates:
        if path and Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    fallback = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
        return fallback
    except Exception:
        return "Helvetica"


FONT = register_font("PangPangCJK", FONT_REG_CANDIDATES)
FONT_BOLD = register_font("PangPangCJKBold", FONT_BOLD_CANDIDATES)


def normalize_status(value):
    if value == "已发布":
        return "已发布"
    if value == "取消":
        return "取消"
    return "新增"


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


def text_width(text, font_name, size):
    return pdfmetrics.stringWidth(str(text or ""), font_name, size)


def wrap_text(text, font_name, size, max_width, max_lines=2):
    raw = str(text or "")
    if not raw:
        return [""]
    tokens = raw.split(" ") if " " in raw else list(raw)
    sep = " " if " " in raw else ""
    lines = []
    current = ""
    for token in tokens:
        test = f"{current}{sep}{token}".strip() if sep else current + token
        if text_width(test, font_name, size) <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = token
            if len(lines) >= max_lines - 1:
                break
    if current:
        while text_width(current, font_name, size) > max_width and len(current) > 1:
            current = current[:-1]
        lines.append(current)
    return lines[:max_lines]


def draw_text(c, x, y, text, font_name=FONT, size=9, fill=colors.HexColor("#1d1d1f"), max_width=None, max_lines=2):
    c.setFillColor(fill)
    c.setFont(font_name, size)
    lines = wrap_text(text, font_name, size, max_width, max_lines) if max_width else [str(text or "")]
    for i, line in enumerate(lines):
        c.drawString(x, y - i * (size + 3), line)


def link_label(record):
    labels = []
    if record.get("link"):
        labels.append(("查看主页", record.get("link")))
    if record.get("postUrl"):
        labels.append(("查看帖子", record.get("postUrl")))
    return labels


try:
    records = json.loads(RECORDS.read_text("utf-8"))
    if not isinstance(records, list):
        records = []
except Exception:
    records = []

records = [record for record in records if not is_invalid_draft(record)]
records = sorted(records, key=lambda r: (status_sort_rank(r), r.get("dateISO") or "9999-99-99", sort_minutes(r.get("timeText"))))

OUT.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(OUT), pagesize=landscape(A3))
page_w, page_h = landscape(A3)

margin = 34
top = page_h - 34
row_h = 42
date_h = 24
header_h = 34

cols = [
    ("状态", 42),
    ("预约时间", 66),
    ("博主", 142),
    ("平台", 62),
    ("粉丝", 52),
    ("赞/数据", 160),
    ("帖子数据", 190),
    ("人数", 36),
    ("电话", 68),
    ("博主状态", 76),
    ("发帖日期", 104),
    ("链接", 100),
]

black = colors.HexColor("#1d1d1f")
muted = colors.HexColor("#6e6e73")
blue = colors.HexColor("#0071e3")
purple = colors.HexColor("#5856d6")
green_text = colors.HexColor("#248a3d")
header_bg = colors.HexColor("#f5f5f7")
blue_row = colors.HexColor("#eef6ff")
green_row = colors.HexColor("#effaf2")
red_row = colors.HexColor("#fff1f1")


def draw_header():
    c.setFillColor(black)
    c.setFont(FONT_BOLD, 26)
    c.drawString(margin, top, "PangPang 博主探店预约全局表")
    c.setFillColor(muted)
    c.setFont(FONT, 10)
    c.drawString(margin, top - 22, "PDF 邮件版｜只高亮本次保存的记录｜主页和帖子按钮可点击")
    metric_y = top - 66
    c.setFillColor(header_bg)
    c.roundRect(margin, metric_y - 26, page_w - margin * 2, 48, 12, fill=1, stroke=0)
    metrics = [
        ("总记录", len(records)),
        ("新增", sum(1 for r in records if normalize_status(r.get("status")) == "新增")),
        ("已发布", sum(1 for r in records if normalize_status(r.get("status")) == "已发布")),
        ("取消", sum(1 for r in records if normalize_status(r.get("status")) == "取消")),
        ("本次高亮", sum(1 for r in records if str(r.get("id") or "") in HIGHLIGHT_IDS)),
    ]
    x = margin + 20
    for label, value in metrics:
        c.setFillColor(black)
        c.setFont(FONT_BOLD, 18)
        c.drawString(x, metric_y, str(value))
        c.setFillColor(muted)
        c.setFont(FONT, 8)
        c.drawString(x, metric_y - 14, label)
        x += 150


def draw_table_header(y):
    c.setFillColor(header_bg)
    c.roundRect(margin, y - header_h + 8, page_w - margin * 2, header_h, 8, fill=1, stroke=0)
    x = margin + 8
    for label, width in cols:
        draw_text(c, x, y - 10, label, FONT_BOLD, 9, muted)
        x += width


draw_header()
y = top - 120
draw_table_header(y)
y -= header_h
last_date = None

for record in records:
    needed = row_h + (date_h if date_title(record) != last_date else 0)
    if y - needed < 50:
        c.showPage()
        draw_header()
        y = top - 120
        draw_table_header(y)
        y -= header_h
        last_date = None

    date = date_title(record)
    if date != last_date:
        c.setFillColor(black)
        c.setFont(FONT_BOLD, 13)
        c.drawString(margin + 4, y - 4, date)
        y -= date_h
        last_date = date

    status = normalize_status(record.get("status"))
    highlighted = str(record.get("id") or "") in HIGHLIGHT_IDS
    fill = colors.white
    if status == "已发布" and highlighted:
        fill = green_row
    elif status == "取消":
        fill = red_row
    elif highlighted:
        fill = blue_row
    c.setFillColor(fill)
    c.roundRect(margin, y - row_h + 8, page_w - margin * 2, row_h - 4, 6, fill=1, stroke=0)

    values = [
        status,
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
    ]

    x = margin + 8
    for idx, (text, (_, width)) in enumerate(zip(values, cols)):
        color = purple if text == "已发布" else green_text if idx == 8 and text != "待补" else black
        size = 8 if idx in (5, 6, 10) else 9
        font_name = FONT_BOLD if idx == 0 else FONT
        draw_text(c, x, y - 10, text, font_name, size, color, width - 5, 2)
        x += width

    link_x = margin + 8 + sum(width for _, width in cols[:-1])
    link_y = y - 10
    for label, url in link_label(record):
        draw_text(c, link_x, link_y, label, FONT_BOLD, 9, blue)
        tw = text_width(label, FONT_BOLD, 9)
        c.linkURL(url, (link_x, link_y - 2, link_x + tw, link_y + 10), relative=0)
        link_y -= 14

    y -= row_h

c.setFillColor(muted)
c.setFont(FONT, 8)
c.drawString(margin, 26, "颜色说明：浅蓝=本次新增预约｜浅绿=本次发帖更新｜浅红=取消但保留记录。")
c.save()
print(OUT)

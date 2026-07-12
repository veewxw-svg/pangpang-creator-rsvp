import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


RECORDS = Path(os.environ.get("PANGPANG_RECORDS_JSON", "data/records.json"))
OUT = Path(os.environ.get("PANGPANG_REPORT_OUT", "output/pangpang_creator_report.png"))
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


def short_text(value, max_chars):
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"


def date_title(record):
    return record.get("dateText") or record.get("dateISO") or "未填日期"


try:
    records = json.loads(RECORDS.read_text("utf-8"))
    if not isinstance(records, list):
        records = []
except Exception:
    records = []

records = sorted(records, key=lambda r: (r.get("dateISO") or "9999-99-99", sort_minutes(r.get("timeText"))))

W = 2480
row_h = 86
date_h = 62
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
d.text((70, 124), "邮件通知版｜按预约时间排序｜每次新增或发帖更新会高亮整行｜长链接隐藏成查看按钮", fill=muted, font=sub_f)

d.rounded_rectangle((70, 174, 2410, 300), radius=24, fill=header_bg)
metrics = [
    ("总记录", str(len(records))),
    ("新增", str(sum(1 for r in records if normalize_status(r.get("status")) == "新增"))),
    ("已发布", str(sum(1 for r in records if normalize_status(r.get("status")) == "已发布"))),
    ("取消", str(sum(1 for r in records if normalize_status(r.get("status")) == "取消"))),
    ("新更新", str(sum(1 for r in records if float(r.get("highlightUntil") or 0) > 0))),
]
mx = 110
for label, value in metrics:
    d.text((mx, 198), value, fill=black, font=font(36, True))
    d.text((mx, 244), label, fill=muted, font=small_f)
    mx += 445

cols = [
    ("状态", 110),
    ("预约时间", 210),
    ("博主", 320),
    ("平台", 140),
    ("粉丝", 130),
    ("赞/数据", 150),
    ("人数", 78),
    ("电话", 145),
    ("发帖日期", 300),
    ("链接", 230),
    ("备注", 520),
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
    highlighted = float(record.get("highlightUntil") or 0) > 0
    if status == "已发布" and highlighted:
        fill = green_row
    elif status == "取消":
        fill = red_row
    elif highlighted:
        fill = blue_row
    else:
        fill = "#ffffff"

    d.rounded_rectangle((x0, y, right, y + row_h - 8), radius=12, fill=fill)
    d.line((x0 + 16, y + row_h - 8, right - 16, y + row_h - 8), fill=line, width=1)

    values = [
        status,
        record.get("timeText") or "-",
        display_name(record),
        record.get("platform") or "待补",
        record.get("followers") or "待补",
        record.get("engagement") or "待补",
        record.get("pax") or "待补",
        record.get("phone") or "待补",
        record.get("postDateText") or "-",
        link_status(record),
        record.get("remarks") or "",
    ]

    x = x0 + 18
    for idx, ((_, width), value) in enumerate(zip(cols, values)):
        color = black
        if value == "取消":
            color = red
        elif value == "已发布":
            color = purple
        elif "查看" in str(value):
            color = blue
        elif idx == 8 and value != "-":
            color = green

        f = body_f
        if idx in (3, 8, 9, 10):
            f = small_f
        if idx == 0:
            f = font(22, True)

        max_chars = max(3, int(width / 12.5))
        d.text((x, y + 28), short_text(value, max_chars), fill=color, font=f)
        x += width

    y += row_h

d.rounded_rectangle((70, H - 160, 2410, H - 72), radius=22, fill=header_bg)
d.text((102, H - 133), "颜色说明：浅蓝=本次新增预约｜浅绿=本次发帖更新｜浅红=取消但保留记录。邮件正文可放真实主页/帖子按钮。", fill=muted, font=small_f)
d.text((70, H - 40), "后台保留完整数据；这张 PNG 用来给手机和电脑快速看全局。", fill=muted, font=tiny_f)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(OUT)

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


OUT = Path("/Users/Vee/Dropbox/Pang Pang 全局/output/pdf/PangPang_单条新增邮件通知_demo.png")
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def wrap_text(draw, text, font_obj, max_width):
    lines = []
    current = ""
    for char in str(text):
        test = current + char
        if draw.textlength(test, font=font_obj) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


record = {
    "status": "新增",
    "type": "探店预约",
    "name": "奶奶的毛孩子",
    "platform": "小红书",
    "followers": "1",
    "engagement": "10+",
    "date": "2026年7月9日 星期四",
    "time": "7:00 pm",
    "pax": "3 pax",
    "phone": "82774791",
    "submitter": "中文板块营销专员",
    "menu": "晚餐推广菜单",
    "note": "新增预约，已自动识别博主主页；主页链接已隐藏，邮件正文可点“查看主页”。",
    "profile_link": "查看主页",
    "post_link": "",
}

W, H = 1280, 1580
img = Image.new("RGB", (W, H), "#f5f5f7")
d = ImageDraw.Draw(img)

black = "#1d1d1f"
muted = "#6e6e73"
soft = "#86868b"
line = "#d2d2d7"
blue = "#0071e3"
green = "#248a3d"
green_soft = "#e9f7ee"
panel = "#ffffff"

title_f = font(58, True)
subtitle_f = font(28)
label_f = font(26, True)
value_f = font(36, True)
small_f = font(24)
tiny_f = font(21)

d.text((72, 58), "PangPang", fill=black, font=font(26, True))
d.text((72, 106), "博主探店预约通知", fill=black, font=title_f)
d.text((72, 184), "这次新增的记录已高亮，预约表会自动按预约时间排序。", fill=muted, font=subtitle_f)

d.rounded_rectangle((72, 252, 1208, 390), radius=30, fill=green_soft)
d.text((106, 286), "新增预约", fill=green, font=font(42, True))
d.text((106, 342), "需要营销、店长、老板知道的新记录", fill=muted, font=small_f)
d.rounded_rectangle((1000, 290, 1168, 354), radius=32, fill="#ffffff")
d.text((1040, 306), "新增", fill=green, font=font(26, True))

d.rounded_rectangle((72, 430, 1208, 738), radius=30, fill=panel)
d.text((106, 472), record["name"], fill=black, font=font(52, True))
d.text((106, 542), f'{record["platform"]} · 粉丝 {record["followers"]} · 赞藏 {record["engagement"]}', fill=muted, font=subtitle_f)

pill_y = 622
d.rounded_rectangle((106, pill_y, 286, pill_y + 58), radius=29, fill="#f5f5f7", outline=line, width=2)
d.text((144, pill_y + 13), "查看主页", fill=blue, font=small_f)

cards = [
    ("预约日期", record["date"]),
    ("预约时间", record["time"]),
    ("人数", record["pax"]),
    ("电话", record["phone"]),
    ("提交人", record["submitter"]),
    ("套餐", record["menu"]),
]

x_positions = [72, 658]
y = 778
card_w = 550
card_h = 168
for idx, (label, value) in enumerate(cards):
    x = x_positions[idx % 2]
    if idx and idx % 2 == 0:
        y += card_h + 22
    d.rounded_rectangle((x, y, x + card_w, y + card_h), radius=26, fill=panel)
    d.text((x + 34, y + 28), label, fill=soft, font=label_f)
    lines = wrap_text(d, value, value_f, card_w - 68)
    for line_idx, line in enumerate(lines[:2]):
        d.text((x + 34, y + 76 + line_idx * 42), line, fill=black, font=value_f)

note_top = 1320
d.rounded_rectangle((72, note_top, 1208, 1480), radius=30, fill=panel)
d.text((106, note_top + 28), "备注", fill=soft, font=label_f)
for idx, line in enumerate(wrap_text(d, record["note"], small_f, 1040)[:3]):
    d.text((106, note_top + 74 + idx * 34), line, fill=black, font=small_f)

d.text((72, 1518), "邮件正文会附：查看主页 / 查看帖子按钮；PNG 内不展示长链接，避免页面变乱。", fill=muted, font=tiny_f)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(OUT)

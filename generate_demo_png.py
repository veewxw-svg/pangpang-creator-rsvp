from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


OUT = Path("/Users/Vee/Dropbox/Pang Pang 全局/output/pdf/PangPang_全局预约追踪邮件_demo.png")
FONT_REG = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def time_minutes(t):
    raw = t.lower().strip()
    parts = raw.replace("am", "").replace("pm", "").strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if "pm" in raw and h < 12:
        h += 12
    if "am" in raw and h == 12:
        h = 0
    return h * 60 + m


records = [
    {
        "status": "新增",
        "date": "2026年7月9日 星期四",
        "sort_date": "2026-07-09",
        "time": "7:00 pm",
        "name": "奶奶的毛孩子",
        "platform": "小红书",
        "fans": "1",
        "data": "10+",
        "pax": "3",
        "phone": "82774791",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页",
        "post_date": "",
        "note": "本次新增，高亮",
        "highlight": True,
    },
    {
        "status": "已发布",
        "date": "2026年7月9日 星期四",
        "sort_date": "2026-07-09",
        "time": "7:00 pm",
        "name": "奶奶的毛孩子",
        "platform": "小红书",
        "fans": "1",
        "data": "10+",
        "pax": "3",
        "phone": "82774791",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页 / 查看帖子",
        "post_date": "2026年7月12日 星期日",
        "note": "发帖自动更新在原预约",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月12日 星期日",
        "sort_date": "2026-07-12",
        "time": "11:30 am",
        "name": "鲫鱼",
        "platform": "小红书",
        "fans": "10+",
        "data": "1千+",
        "pax": "2",
        "phone": "87991234",
        "owner": "中文营销",
        "menu": "午餐",
        "links": "查看主页",
        "post_date": "",
        "note": "靠窗，少辣",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月12日 星期日",
        "sort_date": "2026-07-12",
        "time": "1:00 pm",
        "name": "Mia Eats",
        "platform": "Instagram",
        "fans": "8,420",
        "data": "36 posts",
        "pax": "3",
        "phone": "91234567",
        "owner": "英文营销",
        "menu": "午餐",
        "links": "查看主页",
        "post_date": "",
        "note": "等博主回电话",
        "highlight": False,
    },
    {
        "status": "新增",
        "date": "2026年7月12日 星期日",
        "sort_date": "2026-07-12",
        "time": "6:00 pm",
        "name": "Yuki",
        "platform": "小红书",
        "fans": "12,800",
        "data": "88,000",
        "pax": "4",
        "phone": "97996245",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页",
        "post_date": "",
        "note": "已确认不吃牛",
        "highlight": True,
    },
    {
        "status": "取消",
        "date": "2026年7月12日 星期日",
        "sort_date": "2026-07-12",
        "time": "7:30 pm",
        "name": "小陈爱吃",
        "platform": "小红书",
        "fans": "3,600",
        "data": "14,200",
        "pax": "2",
        "phone": "81239876",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页",
        "post_date": "",
        "note": "临时取消，保留记录",
        "highlight": True,
    },
    {
        "status": "已发布",
        "date": "2026年7月12日 星期日",
        "sort_date": "2026-07-12",
        "time": "8:45 pm",
        "name": "Kimiii",
        "platform": "小红书",
        "fans": "2,036",
        "data": "11,000",
        "pax": "2",
        "phone": "87654321",
        "owner": "英文营销",
        "menu": "晚餐",
        "links": "查看主页 / 查看帖子",
        "post_date": "2026年7月13日 星期一",
        "note": "已发帖，需看曝光",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月13日 星期一",
        "sort_date": "2026-07-13",
        "time": "12:00 pm",
        "name": "Taro",
        "platform": "Instagram",
        "fans": "5,900",
        "data": "128 posts",
        "pax": "2",
        "phone": "92345678",
        "owner": "英文营销",
        "menu": "午餐",
        "links": "查看主页",
        "post_date": "",
        "note": "生日探店",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月13日 星期一",
        "sort_date": "2026-07-13",
        "time": "2:15 pm",
        "name": "Nana",
        "platform": "小红书",
        "fans": "18,000",
        "data": "102,000",
        "pax": "1",
        "phone": "83456789",
        "owner": "中文营销",
        "menu": "午餐",
        "links": "查看主页",
        "post_date": "",
        "note": "只喝饮料",
        "highlight": False,
    },
    {
        "status": "已发布",
        "date": "2026年7月13日 星期一",
        "sort_date": "2026-07-13",
        "time": "5:45 pm",
        "name": "Alicia",
        "platform": "Instagram",
        "fans": "7,200",
        "data": "82 posts",
        "pax": "2",
        "phone": "94567890",
        "owner": "英文营销",
        "menu": "晚餐",
        "links": "查看主页 / 查看帖子",
        "post_date": "2026年7月14日 星期二",
        "note": "Reel 已发布",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月14日 星期二",
        "sort_date": "2026-07-14",
        "time": "10:45 am",
        "name": "坡岛胃口",
        "platform": "小红书",
        "fans": "9,800",
        "data": "50,100",
        "pax": "2",
        "phone": "96789012",
        "owner": "中文营销",
        "menu": "午餐",
        "links": "查看主页",
        "post_date": "",
        "note": "需要儿童椅",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月14日 星期二",
        "sort_date": "2026-07-14",
        "time": "6:15 pm",
        "name": "Lemon",
        "platform": "小红书",
        "fans": "6,100",
        "data": "18,700",
        "pax": "5",
        "phone": "98901234",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页",
        "post_date": "",
        "note": "2A + 3C",
        "highlight": True,
    },
    {
        "status": "新增",
        "date": "2026年7月14日 星期二",
        "sort_date": "2026-07-14",
        "time": "7:00 pm",
        "name": "Foodie Ray",
        "platform": "Instagram",
        "fans": "14,000",
        "data": "74 posts",
        "pax": "2",
        "phone": "89012345",
        "owner": "英文营销",
        "menu": "晚餐",
        "links": "查看主页",
        "post_date": "",
        "note": "等确认菜单",
        "highlight": False,
    },
    {
        "status": "已发布",
        "date": "2026年7月15日 星期三",
        "sort_date": "2026-07-15",
        "time": "6:00 pm",
        "name": "吃货阿森",
        "platform": "小红书",
        "fans": "15,600",
        "data": "120,000",
        "pax": "3",
        "phone": "81234567",
        "owner": "中文营销",
        "menu": "晚餐",
        "links": "查看主页 / 查看帖子",
        "post_date": "2026年7月16日 星期四",
        "note": "图文已发布",
        "highlight": True,
    },
]


records.sort(key=lambda r: (r["sort_date"], time_minutes(r["time"])))

W, H = 2480, 2480
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
    ("新增", str(sum(1 for r in records if r["status"] == "新增"))),
    ("已发布", str(sum(1 for r in records if r["status"] == "已发布"))),
    ("取消", str(sum(1 for r in records if r["status"] == "取消"))),
    ("新更新", str(sum(1 for r in records if r["highlight"]))),
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
row_h = 86
d.rounded_rectangle((x0, y, right, y + row_h), radius=16, fill=header_bg)
x = x0 + 18
for name, width in cols:
    d.text((x, y + 29), name, fill=muted, font=head_f)
    x += width
y += row_h

last_date = None
for r in records:
    if r["date"] != last_date:
        d.text((x0 + 8, y + 22), r["date"], fill=black, font=font(30, True))
        y += 62
        last_date = r["date"]

    if r["status"] == "已发布" and r["highlight"]:
        fill = green_row
    elif r["status"] == "取消":
        fill = red_row
    elif r["highlight"]:
        fill = blue_row
    else:
        fill = "#ffffff"

    d.rounded_rectangle((x0, y, right, y + row_h - 8), radius=12, fill=fill)
    d.line((x0 + 16, y + row_h - 8, right - 16, y + row_h - 8), fill=line, width=1)

    values = [
        r["status"],
        r["time"],
        r["name"],
        r["platform"],
        r["fans"],
        r["data"],
        r["pax"],
        r["phone"],
        r["post_date"] or "-",
        r["links"],
        r["note"],
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

        txt = str(value)
        max_chars = max(3, int(width / 12.5))
        if len(txt) > max_chars:
            txt = txt[: max_chars - 1] + "…"
        d.text((x, y + 28), txt, fill=color, font=f)
        x += width

    y += row_h

d.rounded_rectangle((70, H - 170, 2410, H - 82), radius=22, fill=header_bg)
d.text((102, H - 143), "颜色说明：浅蓝=本次新增预约｜浅绿=本次发帖更新｜浅红=取消但保留记录。邮件正文可放真实主页/帖子按钮。", fill=muted, font=small_f)
d.text((70, H - 48), "后台仍保留完整 Excel/CSV 数据；这张 PNG 用来给手机和电脑快速看全局。", fill=muted, font=tiny_f)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print(OUT)

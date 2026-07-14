# PangPang 博主探店预约系统

用于记录博主探店预约、追踪发帖、生成邮件用全局 PNG。

## 功能

- 从小红书 / Instagram 主页链接识别博主信息
- 从帖子链接追踪发帖，并更新到原预约
- 预约记录按预约时间排序
- 状态：新增、取消、已发布
- 生成全局 PNG：`/api/report.png`
- 可选 Resend 邮件通知

## 本地运行

```bash
npm start
```

打开：

```text
http://127.0.0.1:8787/
```

## Render 部署

使用 Docker 部署。仓库内已包含：

- `Dockerfile`
- `render.yaml`

需要一个持久磁盘：

```text
mount path: /var/data
```

正式记录保存到：

```text
/var/data/records.json
```

## 邮件环境变量

默认不发邮件。

开启邮件需要设置：

```text
SEND_EMAILS=1
RESEND_API_KEY=你的 Resend API Key
NOTIFY_FROM=PangPang <通知发件邮箱>
NOTIFY_TO=老板邮箱,店长邮箱,营销邮箱
PUBLIC_URL=正式网站网址
```

## Instagram 数据追踪

如果要更稳定地追踪公开 Instagram 帖子/Reel 数据，可以设置：

```text
APIFY_TOKEN=你的 Apify API Token
APIFY_IG_ACTOR=apify/instagram-scraper
```

设置后，系统会优先用 Apify 抓 Instagram 作者、发布时间、点赞、评论、播放等数据；没有设置时继续使用公开网页兜底。

## 主要接口

```text
GET  /api/records
POST /api/records
GET  /api/report.png
GET  /api/resolve-profile?url=...
```

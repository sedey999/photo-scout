# 权威源清单

按场景类别整理的“第一跳”来源。Agent 做候选发现时按此顺序尝试。

## 1. 企业 / 品牌 Logo

### 1.1 官网直取
解析首页 HTML 中的：
- `<link rel="apple-touch-icon" sizes="NxN">` — 取 sizes 最大的
- `<link rel="icon">`
- `<meta property="og:image">`
- `<meta name="twitter:image">`
- `<img alt="...logo...">`

常见品牌域名速查（持续扩充）：

| 品牌 | 域名 |
|---|---|
| 豆包 | doubao.com, team.doubao.com |
| 字节跳动 | bytedance.com |
| 抖音 | douyin.com |
| 今日头条 | toutiao.com |
| 小红书 | xiaohongshu.com |
| 微信 | weixin.qq.com |
| 瑞幸咖啡 | lkcoffee.com, luckincoffee.com |
| 星巴克 | starbucks.com.cn |
| 蜜雪冰城 | mxbc.com |
| 胖东来 | pangdonglai.com |
| 喜马拉雅 | ximalaya.com |
| 百度 | baidu.com |
| 华为 | huawei.com, consumer.huawei.com |
| 小米 | mi.com, xiaomi.com |
| 比亚迪 | byd.com |
| 肯德基 | kfc.com.cn |
| 麦当劳 | mcdonalds.com.cn |
| 海尔 | haier.com |

**未在表中的品牌**：用 `search("XX 官网 官方网站")` 找到域名，再拉 HTML。

### 1.2 App Store / 应用市场
- iTunes Search API: `https://itunes.apple.com/search?term={q}&country=cn&media=software&limit=10`
- 结果中 `artworkUrl512` 替换 `/512x512bb.jpg` 为 `/1024x1024bb.png`
- 必查 `sellerName` 是否为目标品牌的母公司或关联公司，防止同名 App 图标误用

### 1.3 自媒体头像原图

| 平台 | 头像原图 URL 模式 |
|---|---|
| 微博 | `https://wx1.sinaimg.cn/large/{uid}.jpg`（large 是原图，不要用 thumbnail/crop） |
| 微信公众号 | 文章页 `<meta property="og:image">` |
| 抖音 | `https://p3.douyinpic.com/img/aweme-avatar/{id}` 或从 sec_uid 页面解析 |
| B站 | `https://i0.hdslb.com/bfs/face/{id}.jpg` |
| 小红书 | 从用户页解析 |
| YouTube | `https://yt3.googleusercontent.com/{id}=s1024-ck` |

### 1.4 品牌素材站
- LobeHub Icons: `https://cdn.jsdelivr.net/npm/@lobehub/icons-static-png/light/{slug}.png` 和 `.../static-avatar/avatars/{slug}.webp`（覆盖 1600+ AI/科技品牌）
- World Vector Logo: `https://worldvectorlogo.com/logo/{slug}`（SVG）
- SeekLogo
- 品牌星球 brandstar.com.cn
- 数英网 digitaling.com（国内品牌 campaign 物料）
- SocialBeta socialbeta.com（营销案例图）

## 2. 人物照片

优先级：
1. **官方账号发布**：微博、抖音、公众号、小红书的本人账号
2. **企业官方**：公司官网“管理团队”页、官方公众号
3. **权威媒体通稿**：新华社、人民日报、湖北日报等党媒（图床通常是 hbrbapp 等子域）
4. **财经/商业媒体**：FoodTalks、虎嗅、36氪、第一财经、中国企业家杂志
5. **百科 og:image**：百度百科/维基百科 infobox 主图
6. **通用搜索兜底**：视觉门控

注意：
- 搜狐号、今日头条号、百家号内容质量良莠不齐，要视觉复核
- 人物旧照可能与当前形象差异大（尤其企业家），优先近 1-2 年的图

## 3. 事件 / 营销活动

1. **品牌官方微博/公众号**首发图
2. **数英网 digitaling.com/projects/{id}.html** —— 项目页通常有完整海报/视频截图
3. **SocialBeta socialbeta.com/campaign/{id}**
4. **广告门、品牌星球**
5. **财经/新闻媒体**：搜狐、网易、腾讯、凤凰（注意有些要JS渲染）
6. 微博话题页（需要登录，沙箱可能不通）

## 4. 地标 / 风景

### 4.1 官方
- 景区官网
- 地方政府文旅局官网
- 地方官媒图片库：
  - 湖南图片库 pic.voc.com.cn（去 `!watermark` 后缀）
  - 视觉江苏、东方 IC（付费）

### 4.2 公共授权图库
- Wikimedia Commons（沙箱可能超时）
- Unsplash: `https://images.unsplash.com/photo-{id}?w=1600`
- Pixabay CDN: `https://cdn.pixabay.com/photo/...`
- Pexels
- Pixnio
- NASA Visible Earth（雪山、卫星图）
- 国家地理官网

### 4.3 游记/社区
- 携程攻略、马蜂窝、小红书
- Chiphell 等论坛游记（质量高但要确认作者授权）

## 5. 餐饮 / 菜品

1. **大众点评/美团**商家相册（需要登录，找有公开图床的转载）
2. **携程旅行社区** articleId 页（图片 CDN 通常可直链）
3. **抖音/小红书**探店笔记
4. **本地媒体探店文**：搜狐号、腾讯大湘网等
5. 官方公众号文章

## 搜索引擎：正常页面 URL，截图定位主通道

**铁律：只用浏览器地址栏可见的正常搜索页 URL；严禁内部 XHR 数据接口。**

### 通道

| 通道 | 正常页面 URL | 访问方式 | 角色 |
|---|---|---|---|
| 百度图片 | `https://image.baidu.com/search/index?tn=baiduimage&word={词}` | Playwright 真实浏览器 | **主通道**：从 DOM 的 `[data-objurl]` 元素提取图片地址+标题+坐标，按屏截图 |
| Bing 图片 | `https://cn.bing.com/images/search?q={词}&first=N` | requests 直连 | 补充：海外/英文内容有优势；中文专有名词语义易漂移，从严门控 |
| 360/搜狗 | 正常页 | — | 禁用（渲染后无有效结果/空壳） |

截图定位法要点（search_engines.baidu_screenshot_search）：
- 浏览器开页后滚动加载，从 DOM 提取每个结果的 `data-objurl`（图片地址）、`title`、页面坐标
- 按视口高度逐屏截图到 `screens/page_XX.png`；每个候选标注所在屏号与屏内序号
- Agent 看截图按位置勾选，只下载勾选 id 的图片——不预先批量下载原图
- 百度结果标题是真实文章标题，相关性判断价值高（优于文件名猜测）

### 内部接口黑名单（不要使用）

- ❌ 百度 `image.baidu.com/search/acjson` → requests 直连返回 Forbid spider access
- ❌ 360 `image.so.com/j` → 只返回极少量无关结果
- ❌ 搜狗 `pic.sogou.com/napi/pc/searchList` → 返回 forbid
- ❌ Bing `cn.bing.com/images/async` → 非用户可见页面，用正常页替代

## 通用反爬应对

| 问题 | 应对 |
|---|---|
| 百度 requests 被拦 | 换 Playwright 浏览器通道（search_engines.py 已内置） |
| 360/搜狗 彻底失效 | 不用，Bing + 百度浏览器已够 |
| 长尾词/人物事件 Bing 结果少 | 用平台 `search(source="web")` 找文章页 + `extract_page_images.py` 抽图 |
| 头条/腾讯图片 403 | 文章正文可能 JS 渲染，改用 search 找其他转载 |
| 沙箱 HTTPS 偶发超时 | 脚本自动重试；持续不通换国内 CDN（jsdelivr→unpkg→npmmirror） |
| 图片 URL 无扩展名（搜狐加密图床） | 直接下载，PIL 自动识别格式 |
| voc 等地方图库带水印 | URL 去掉 `!watermark` 后缀 |

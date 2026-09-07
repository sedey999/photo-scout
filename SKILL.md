---
name: photo-scout
description: 多模态视觉门控图片下载器（Vision-Gated Photo Downloader）。触发词：下载图片、搜图、找图、要XX的高清图、logo下载、视觉筛选图片、批量搜图。核心方法：浏览器打开搜索页→按屏截图/DOM定位→多模态视觉门控→只下载勾选原图→来源页截屏复核。当用户需要按主题搜索并下载高质量图片（企业logo、人物照片、风景、产品图、营销事件图、餐馆菜品等）时使用。
---

# Photo Scout — 多模态视觉门控图片下载器

## 设计理念

图片搜索的难点不在“搜到图”，而在“从一堆噪声里挑出真正对的那张”。

文件名、页面标题这类文本信息与图片真实内容经常脱节：同名异物、CDN 随机文件名、蹭关键词的无关图，都会让纯文本规则失效。因此本技能把“这张图是不是用户要的”交给**多模态视觉模型**：浏览器打开搜索结果页后按屏截图，模型看截图按位置勾选，脚本只负责打开页面、提取数据、下载勾选图、计算客观指标（分辨率、清晰度）。

**前置要求：视觉理解能力。** 核心筛选步骤（看截图/contact sheet 判断图片内容）依赖多模态视觉理解。脚本无法检测调用它的模型是否具备视觉能力，因此 discover 完成后会输出“视觉能力探测”提示——Agent 必须先用 `fetch(type=file_path)` 读取任一截图并尝试描述其画面内容：

- 若能返回图片的画面描述（红底、人物、雪山等具体内容），说明平台已桥接视觉能力，可继续视觉门控
- 若 fetch 只能返回文件元数据（尺寸/路径）或无法描述画面，说明当前环境不具备视觉理解能力，应**停止任务并提示用户更换支持视觉的模型**

不要在未确认视觉能力前直接进入勾选。

## 场景识别（自动）

`run.py` 对查询词自动分类，决定源头策略与筛选标准：

| 场景 | 识别线索 | 选图标准 |
|---|---|---|
| **logo/标识** | 含 logo、标志、图标、icon、商标 | **只选纯色/透明背景的标准 logo 本体**；挂 logo 的门店/大楼/产品/招牌一律排除 |
| 人物 | 人名、创始人、CEO 等 | 本人正脸/半身、新闻现场、近期照片 |
| 事件/营销 | 发布会、大会、联名、代言、开幕等 | 品牌物料/现场图，多元素词须所有元素同框 |
| 建筑 | 大楼、大厦、总部、园区 | 建筑主体完整、无遮挡、无他物抢主体 |
| 风景 | 山、湖、景区、雪山等 | 主体突出、构图完整、光线好 |
| 菜品 | 菜、席、宴、美食、餐厅 | 菜品特写/宴席全景，无筷子入镜等杂物 |

## 工作流

```
Step 0  check-env：环境自检（playwright/Chromium、Bing、openpyxl、视觉能力提示）
Step 1  discover：浏览器打开百度图片页 → DOM提取(URL+标题+坐标) → 按屏截图 screens/
                 + Bing 补充结果拼分页 contact_sheet
         logo 类：先用 source_router 直取官网/App Store/自媒体头像（纯净 logo）
Step 2  视觉门控：Agent 看 screens/page_XX.png（含原文位置/标题）或 contact_sheet，
                 按候选 id 勾选（logo 只选纯色/透明底标准 logo）
Step 3  select：只下载勾选 id 的原图 → 以短边分辨率为主、清晰度为辅排序 → final/ + XLSX
Step 4  verify（事件类/存疑时强烈建议）：打开来源页整页截屏 + 图注提取，
                 确认图片是准确配图、文章与关键词匹配
```

### 命令

```bash
# Step 0：环境自检
python3 scripts/run.py check-env

# Step 1：截图定位搜索 + contact sheet
python3 scripts/run.py --workdir ./out/<任务名> discover \
    --query "<搜索词>" [--no-bing] [--no-baidu] \
    [--extra-file urls.txt] [--sheet-size 36]

# logo 类：先直取权威源（官网域名可从平台 search 搜“XX 官网”得到）
python3 scripts/source_router.py "<品牌名>" ./out/<任务名>/brand --domains <官网域名>
#   生成 brand/urls.txt，喂给 discover：
python3 scripts/run.py --workdir ./out/<任务名> discover \
    --query "<品牌名> logo" --extra-file ./out/<任务名>/brand/urls.txt

# Step 3：按候选 id 下载原图（文件名含 id，防同名冲突丢图）
python3 scripts/run.py --workdir ./out/<任务名> select \
    --ids "3,7,12,25" --prefix <命名前缀> --query "<搜索词>"

# Step 4：网页截屏复核（事件/活动类建议）
python3 scripts/run.py --workdir ./out/<任务名> verify

# 可选：重生成 XLSX
python3 scripts/run.py --workdir ./out/<任务名> report --query "<搜索词>"
```

产物结构：
```
<workdir>/
├── screens/             ← 主：搜索页按屏截图（page_00.png ...，含位置/标题上下文）
├── contact_sheet_01.jpg ← 补充：候选缩略图网格（分页，每张≤36格，避免超大图）
├── candidates.json      ← 全部候选元数据（id、URL、标题、来源页、坐标、屏号）
├── thumbs/              ← 缩略图
├── final/               ← 最终选中原图（按质量排序，文件名含候选 id）
├── selected.json        ← 选中图元数据（来源 URL 可追溯）
├── verify/              ← 来源页整页截屏 + 图注（复核用）
└── report.xlsx          ← 三表：选中图片/全部候选/任务信息
```

## 搜索引擎方案

**只用浏览器地址栏可见的正常搜索页 URL，不用内部数据接口。**

| 通道 | 正常页面 URL | 访问方式 | 角色 |
|---|---|---|---|
| 百度图片 | `image.baidu.com/search/index?tn=baiduimage&word=...` | Playwright 真实浏览器 | **主通道**：DOM 提取结果（URL+标题+坐标），按屏截图 |
| Bing 图片 | `cn.bing.com/images/search?q=...&first=N` | requests 直连 | 补充：海外/英文内容有优势；中文专有名词语义易漂移，结果从严门控 |
| 360/搜狗 | 正常页 | — | 禁用（渲染后无有效结果/空壳） |

要点：
- 百度 requests 直连会返回安全验证页，**必须用真实浏览器**（Playwright + 反检测），与普通用户浏览一致
- 主通道从页面 DOM 的 `[data-objurl]` 元素提取真实图片地址、标题、坐标，并按屏截图——不使用 acjson 等内部接口
- **第三通道**：平台内置 `search(source="web")`（走平台后端，无本地反爬限制）。搜到含图文章后，用 `scripts/extract_page_images.py` 抽 `<img>` 链接，经 `--extra-file` 注入。事件/人物/长尾词尤其有效

## logo 类专项（重要）

当查询含 logo/标志/图标/icon/商标 时自动触发：

1. **直取权威源**（`source_router.py`）：
   - T1 官网 `apple-touch-icon` 最大尺寸 / og:image / 首页 logo
   - T2 App Store 图标（1024px，核对开发者名防同名 App）
   - T3 自媒体头像原图（微博 large 图、抖音/公众号等）、素材站（LobeHub、WorldVectorLogo 等，需视觉复核）
   - 官网域名：内置少量快捷字典；不在字典中的品牌，用平台 search 搜“XX 官网”得到域名后 `--domains` 传入
2. **视觉门控只选标准 logo**：纯色底或透明底上的 logo 本体；挂 logo 的大楼、门店、杯子、包装、工服、PPT 现场一律不选
3. 多版本（新版/旧版、彩色/单色、横版/徽章）都保留并在报告注明；优先当前最新版

## 视觉门控规则

看截图/contact sheet 时，按 `references/scoring.md` 执行，核心是先揣摩“用户拿图做什么”：
- 相关性第一（多元素词所有核心元素同框；主体占比够大）
- 不要拼图（九宫格、对比图、组图封面）
- 默认不要大面积水印/文字（明确要 App 截图/报纸/海报时例外）
- logo 只要纯色/透明底本体
- 客观门槛（logo ≥256px，其余短边 ≥800px，对焦清晰，不裁边）
- 排除 AI 生成/粉丝二创/素材站占位图；人物近照优先；事件图当期发布

## select 的排序依据

相关性由视觉门控决定（勾选的候选才进入 final），脚本只在勾选项里按客观质量排序：

- **主排序键：短边分辨率**（`min(宽,高)`，越大越优先）
- **辅助：清晰度**（Laplacian 全图梯度）只作小幅 tie-break 加分，不做乘法惩罚
  - 原因：浅景深背景虚化、雪景/雾景/天空等低纹理场景的梯度天然偏低，这些常是好照片特征，不能因此压低
- 缩略图回退的小图（原图下载失败）排到最后
- 分辨率仍需过视觉门槛（logo ≥256px，其余短边 ≥800px），分数高但画面有问题的图应在视觉门控阶段排除

## 网页截屏复核（verify）

事件/品牌活动类关键词，或视觉门控存疑时，`select` 后执行 `verify`：
- 自动打开选中图的来源文章页，整页按屏截屏到 `verify/<id>/`
- 提取文章标题、正文图片图注（figcaption/alt）
- Agent 查看截图：确认该图在原文中的位置与图注、文章标题是否与关键词匹配（如活动主办方、人物身份），判断是否准确配图、是否原图

这是“图片是否原图/准确配图”的最终确认环节——图片是否符合，需要基于它在上下文中的位置和图注判断。

## 文件结构

| 文件 | 作用 |
|---|---|
| `scripts/run.py` | 统一入口：check-env / discover / select / verify / report |
| `scripts/search_engines.py` | 主通道（百度截图定位 DOM 提取）+ Bing 补充 + 环境自检 |
| `scripts/vision_pipeline.py` | 图片下载、contact sheet 拼接、清晰度计算、Referer 注入、原图参数清理 |
| `scripts/source_router.py` | logo 权威源直取（官网/App Store），输出 urls.txt 供 --extra-file |
| `scripts/webctx_verify.py` | 来源页整页截屏 + 图注/上下文提取 |
| `scripts/extract_page_images.py` | 从任意网页抽 `<img>` URL（配合平台 search 用） |
| `references/scoring.md` | 视觉门控规则（场景标准 + 十条硬规则 + 提问模板） |
| `references/sources.md` | 权威源清单（头像 URL 模板、搜索通道、反爬注意） |

## 环境依赖

- pip：`Pillow requests beautifulsoup4 openpyxl playwright`（openpyxl 可选）
- Chromium：`python3 -m playwright install chromium`（主通道必需；缺失时降级为仅 Bing）
- Linux 沙箱如遇 pip 权限问题可加 `--break-system-packages`
- `python3 scripts/run.py check-env` 一键自检
- Chromium 路径自动查找（缓存目录通配 → 系统 PATH），无硬编码；工作目录全由 `--workdir` 传入

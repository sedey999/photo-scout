# Photo Scout — 多模态视觉门控图片下载器

> 多模态视觉门控：浏览器打开搜索页 → 按屏截图/DOM 定位 → 视觉模型看图勾选 → 只下载勾选原图 → 来源页截屏复核。

## 它解决什么问题

图片搜索的难点不在“搜到图”，而在“从一堆噪声里挑出真正对的那张”。文件名、页面标题与图片真实内容经常脱节：同名异物、CDN 随机文件名、蹭关键词的无关图，都会让纯文本规则失效。

Photo Scout 把“这张图是不是用户要的”交给**多模态视觉模型**判断，脚本只负责打开页面、提取数据、下载勾选图、计算客观指标（分辨率、清晰度）。并按场景自动切换选图标准（logo 只选干净背景本体、人物要正脸近期照、事件图要元素同框等）。

## 核心特性

- **场景识别（自动）**：logo / 人物 / 事件营销 / 建筑 / 风景 / 菜品 六类场景自动分类，各自的选图硬规则见 `references/scoring.md`
- **权威源路由**：logo 类优先走官网 `apple-touch-icon`、`og:image` 等直取链路，避免搜索引擎噪声；微博官方头像自动搜 uid 并取原图（含头像相册历史头像），见 `references/sources.md`
- **视觉能力探测**：进入勾选前强制自检多模态视觉能力，不支持则停止并提示更换模型
- **来源复核**：下载后对来源页截屏复核，防止“图不对题”
- **客观指标兜底**：分辨率、清晰度打分排序，多候选时自动择优

## 使用场景

需要按主题搜索并批量下载高质量图片时：企业 logo、人物照片、产品图、营销事件图、建筑外观、风景地标、餐馆菜品等。

## 安装

```bash
# ClawHub（推荐）
openclaw skills install photo-scout

# 或从本仓库手动安装：将仓库内容放入 skills/photo-scout/ 即可
```

依赖（见 `requirements.txt`）：Pillow、requests、beautifulsoup4、openpyxl、playwright

```bash
pip install -r requirements.txt
playwright install chromium
```

## 仓库结构

```
photo-scout/
├── SKILL.md              # 技能主文档：工作流、场景标准、调用规范
├── requirements.txt      # Python 依赖
├── references/
│   ├── scoring.md        # 视觉门控筛选规则（六类场景选图硬规则）
│   └── sources.md        # 权威源清单（logo 直取、域名速查等）
└── scripts/
    ├── run.py            # 主入口：场景识别 + 流程编排
    ├── search_engines.py # 搜索引擎适配（百度图片、Bing 等）
    ├── source_router.py  # 权威源路由（官网直取优先）
    ├── extract_page_images.py  # DOM 图片提取（URL+标题+坐标）
    ├── vision_pipeline.py      # 截图/contact sheet 流水线
    └── webctx_verify.py        # 来源页截屏复核
```

## 许可证

MIT

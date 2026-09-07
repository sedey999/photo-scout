#!/usr/bin/env python3
"""
网页截屏复核（web context verify）

对选中图片的来源页做整页截屏 + 图注/上下文提取：
  - 打开来源文章页（图片在网页中的原始上下文）
  - 按屏截图到 verify/<id>/page_XX.png
  - 提取正文图片的图注（figcaption / alt）、标题、URL
Agent 查看截图，确认图片在原文中的位置与图注，判断：
  1) 该图是否为文章准确配图（非水印/广告/无关）
  2) 文章标题/正文是否与关键词匹配（事件主办方、人物身份等）

这是“图片是否原图/准确配图”的最终确认环节。
事件/活动类关键词、视觉门控存疑时强烈建议执行。
"""
import sys, json, re, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import search_engines as se

EXTRACT_JS = r"""
() => {
  const main = document.querySelector('article, .content, .article-content, .rich_media_content, main, .news-content, #article') || document.body;
  const out = [];
  let gi = 0;
  main.querySelectorAll('img').forEach((img) => {
    const src = img.currentSrc || img.src || '';
    if (!src || !src.startsWith('http')) return;
    if (/logo|icon|avatar|emoji|loading|spinner|placeholder|share|qr|wechat|qrcode|blank/i.test(src)) return;
    const rect = img.getBoundingClientRect();
    if (rect.width < 80 || rect.height < 80) return;
    let caption = '';
    const fig = img.closest('figure');
    if (fig) {
      const fc = fig.querySelector('figcaption');
      if (fc) caption = fc.textContent.trim();
    }
    if (!caption && img.getAttribute('alt')) caption = img.getAttribute('alt').trim();
    out.push({
      idx: gi++,
      src: src,
      caption: caption,
      alt: img.getAttribute('alt') || '',
      x: Math.round(rect.x),
      y: Math.round(rect.y + window.scrollY),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    });
  });
  const title = document.title || (document.querySelector('h1') && document.querySelector('h1').textContent.trim()) || '';
  return { title: title, url: location.href, imgs: out };
}
"""


def verify_url(page_url, out_dir, viewport_w=1280, viewport_h=1000, max_screens=8):
    """打开单个来源页，截图 + 提取图注。返回 {title,url,imgs,screenshots} 或 None。"""
    ok, exe = se.playwright_available()
    if not ok:
        print(f"[verify] 浏览器不可用: {exe}", flush=True)
        return None
    if not page_url or not page_url.startswith("http"):
        return None
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=exe, headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=se.UA, locale="zh-CN",
                                  viewport={"width": viewport_w, "height": viewport_h})
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        pg = ctx.new_page()
        try:
            pg.goto(page_url, timeout=40000, wait_until="domcontentloaded")
            pg.wait_for_timeout(3500)
            for _ in range(2):
                pg.mouse.wheel(0, 800)
                pg.wait_for_timeout(500)
            data = pg.evaluate(EXTRACT_JS) or {"title": "", "imgs": []}
            total_h = pg.evaluate("document.body.scrollHeight")
            screenshots = []
            for i, y in enumerate(range(0, total_h, viewport_h)):
                if i >= max_screens:
                    break
                pg.evaluate(f"window.scrollTo(0, {y})")
                pg.wait_for_timeout(250)
                sp = out_dir / f"page_{i:02d}.png"
                pg.screenshot(path=str(sp))
                screenshots.append(str(sp))
            data["screenshots"] = screenshots
            browser.close()
            return data
        except Exception as e:
            browser.close()
            print(f"[verify] 打开失败 {page_url[:60]}: {str(e)[:60]}", flush=True)
            return None


def verify_sources(selected_records, out_root, max_pages=6):
    """对选中图片逐条复核来源页。selected_records 来自 selected.json。"""
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    summary = []
    seen_pages = set()
    count = 0
    for r in selected_records:
        page = r.get("page") or ""
        if not page or page in seen_pages or not page.startswith("http"):
            continue
        if "baidu.com/search" in page:  # 搜索结果页本身不是来源
            continue
        seen_pages.add(page)
        count += 1
        if count > max_pages:
            break
        tag = f"{r.get('id', count)}"
        res = verify_url(page, out_root / tag, max_screens=6)
        if res:
            summary.append({
                "candidate_id": r.get("id"),
                "filename": r.get("filename"),
                "page_title": res.get("title", ""),
                "page_url": res.get("url", page),
                "img_count": len(res.get("imgs", [])),
                "captions": [im.get("caption", "") for im in res.get("imgs", []) if im.get("caption")][:5],
                "screenshots": res.get("screenshots", []),
            })
            print(f"[verify] id={r.get('id')} 《{res.get('title','')[:40]}》 "
                  f"{len(res.get('imgs',[]))} 图，{len(res.get('screenshots',[]))} 屏截图", flush=True)
    (out_root / "verify_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[verify] 复核报告 → {out_root/'verify_report.json'}", flush=True)
    print("[verify] 请查看各来源页截图与图注，确认图片为准确配图且文章与关键词匹配。", flush=True)
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="要复核的来源页 URL")
    ap.add_argument("--outdir", default="./out/verify_single")
    args = ap.parse_args()
    res = verify_url(args.url, args.outdir)
    if res:
        print(json.dumps({k: v for k, v in res.items() if k != "screenshots"},
                         ensure_ascii=False, indent=2)[:1500])
        print(f"\n截图 {len(res['screenshots'])} 屏 → {args.outdir}")

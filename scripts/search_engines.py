#!/usr/bin/env python3
"""
搜索引擎模块 — 截图定位法主通道 + Bing 补充通道

主通道（浏览器截图定位）：
  Playwright 打开百度图片搜索正常页面（浏览器地址栏可见的 URL），
  从 DOM 提取每个图片结果的 [data-objurl] 属性 —— 内含：
    - objURL：图片真实地址（部分含原图 CDN，非百度 500px 缓存）
    - 坐标（x, y）：图片在页面中的位置，用于与按屏截图对位
    - 标题：结果标题（真实文章标题，相关性判断依据）
  同时按屏截图（视口宽度，天然尺寸可控），Agent 看截图按位置勾选。

补充通道：Bing 图片搜索正常页面，requests 直连（海外/英文内容有优势；
对中文专有名词语义漂移较明显，结果需严格视觉门控）。

严禁内部 XHR 接口（/acjson、/napi、/j、/async），一律使用正常搜索页 URL。
"""
import os, sys, json, re, time, shutil
from pathlib import Path
from urllib.parse import quote_plus, quote
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}


# ================= 环境检测 =================

def find_chrome_executable():
    """动态查找 Chromium/Chrome 可执行文件，无硬编码版本号。"""
    pw_cache = Path.home() / ".cache" / "ms-playwright"
    if pw_cache.exists():
        for pat in ("chromium-*/chrome-linux64/chrome",
                    "chromium-*/chrome-linux/chrome",
                    "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"):
            hits = sorted(pw_cache.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
            if hits:
                return str(hits[0])
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def playwright_available():
    """检测 playwright pip 包 + Chromium 二进制。返回 (bool, 可执行路径或错误说明)"""
    try:
        import playwright  # noqa
    except ImportError:
        return False, "playwright pip 包未安装（pip install playwright）"
    exe = find_chrome_executable()
    if not exe:
        return False, "未找到 Chromium（python3 -m playwright install chromium）"
    return True, exe


def check_bing_direct(timeout=8):
    try:
        r = requests.get("https://cn.bing.com/images/search?q=test&form=HDRSC2&first=0",
                         headers=HEADERS, timeout=timeout)
        return r.status_code == 200 and len(r.text) > 10000
    except Exception:
        return False


def ensure_environment(verbose=True):
    """环境自检。返回 dict：bing_direct, playwright(ok,msg), vision_hint。

    关于视觉理解能力：图片下载与脚本本身不需要视觉模型，但“视觉门控”这一
    核心步骤必须由具备多模态视觉理解能力的 Agent 执行（看截图/contact sheet）。
    Agent 自身清楚自己是否具备视觉能力——若不具备，应停止任务并告知用户更换
    支持视觉的模型。脚本通过 report 输出此提示，由调用方（Agent）判断。
    """
    result = {}
    result["bing_direct"] = check_bing_direct()
    ok, msg = playwright_available()
    result["playwright"] = (ok, msg)
    if verbose:
        print("=" * 54)
        print("环境自检")
        print("=" * 54)
        print(f"[env] 百度截图定位通道（playwright）: "
              f"{'✅ ' + str(msg) if ok else '❌ ' + str(msg)}")
        print(f"[env] Bing 补充通道（requests 直连）: {'✅' if result['bing_direct'] else '❌'}")
        try:
            import openpyxl  # noqa
            print("[env] XLSX 报告（openpyxl）: ✅")
        except ImportError:
            print("[env] XLSX 报告（openpyxl）: ❌（pip install openpyxl 后可用）")
        print()
        print("[env] 视觉门控要求：本 skill 的核心筛选步骤必须由具备")
        print("      多模态视觉理解能力的 Agent 执行（看截图判断图片内容）。")
        print("      若当前模型不具备图片理解能力，必须停止任务并请用户")
        print("      更换支持视觉的模型，脚本无法替代该判断。")
        print()
        if ok:
            print("✅ 主通道就绪（百度截图定位）")
        elif result["bing_direct"]:
            print("⚠️  仅 Bing 补充通道可用（无浏览器，截图定位不可用）")
        else:
            print("❌ 两个通道都不可用，请检查网络与依赖")
    return result


# ================= 主通道：百度截图定位 =================

# 从页面 DOM 提取图片结果（百度图片结果元素带 data-objurl 属性）
_DOM_EXTRACT_JS = r"""
() => {
  const results = [];
  const els = document.querySelectorAll('[data-objurl]');
  els.forEach((el, i) => {
    const img = el.querySelector('img') || (el.tagName === 'IMG' ? el : null);
    const src = img ? (img.currentSrc || img.src || '') : '';
    const rect = el.getBoundingClientRect();
    if (rect.width < 30 || rect.height < 30) return;
    // 来源页：从最近的详情链接 a 标签的 href 里解析 fromurl 参数
    let fromurl = el.getAttribute('data-fromurl') || '';
    const link = el.closest('a');
    const href = link ? link.href : '';
    if (!fromurl && href && href.indexOf('fromurl=') !== -1) {
      try {
        const m = href.match(/fromurl=([^&]+)/);
        if (m) {
          let fu = decodeURIComponent(m[1]);
          try { fu = decodeURIComponent(fu); } catch (e) {}
          fromurl = fu;
        }
      } catch (e) {}
    }
    results.push({
      idx: i,
      thumb_src: src,
      url: el.getAttribute('data-objurl') || '',
      fromurl: fromurl,
      title: (img && img.getAttribute('alt')) || el.getAttribute('title') || '',
      x: Math.round(rect.x),
      y: Math.round(rect.y + window.scrollY),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    });
  });
  return results;
}
"""


def baidu_screenshot_search(query, workdir, viewport_w=1280, viewport_h=900,
                            scroll_rounds=3, headless=True):
    """
    截图定位主通道。
    - 打开百度图片搜索正常页面
    - DOM 提取图片结果（objURL + 标题 + 坐标）
    - 按屏截图到 workdir/screens/page_XX.png
    返回：(items, screenshots)
      items: [{url, thumb_src, fromurl, title, x, y, w, h, screen, idx_in_screen, engine}]
      screenshots: [截图文件路径]
    """
    ok, exe = playwright_available()
    if not ok:
        print(f"[baidu-shot] 浏览器不可用: {exe}", flush=True)
        return [], []
    from playwright.sync_api import sync_playwright

    workdir = Path(workdir)
    screens_dir = workdir / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)

    page_url = f"https://image.baidu.com/search/index?tn=baiduimage&word={quote(query)}"
    items, screenshots = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=exe, headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN",
                                  viewport={"width": viewport_w, "height": viewport_h})
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        pg = ctx.new_page()
        try:
            pg.goto(page_url, timeout=45000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[baidu-shot] 页面加载失败: {str(e)[:80]}", flush=True)
            browser.close()
            return [], []
        pg.wait_for_timeout(4000)
        for _ in range(scroll_rounds):
            pg.mouse.wheel(0, 800)
            pg.wait_for_timeout(800)
        pg.wait_for_timeout(1000)

        # DOM 提取
        try:
            dom_items = pg.evaluate(_DOM_EXTRACT_JS) or []
        except Exception as e:
            print(f"[baidu-shot] DOM 提取失败: {str(e)[:80]}", flush=True)
            dom_items = []

        # 按屏截图，并给每个 item 标注它在哪一屏、屏内序号
        total_h = pg.evaluate("document.body.scrollHeight")
        screen_idx = 0
        for y in range(0, total_h, viewport_h):
            pg.evaluate(f"window.scrollTo(0, {y})")
            pg.wait_for_timeout(350)
            shot_path = screens_dir / f"page_{screen_idx:02d}.png"
            pg.screenshot(path=str(shot_path))
            screenshots.append(str(shot_path))
            screen_idx += 1

        # 为每个 item 计算所在屏（坐标 y 落在哪一屏）
        for it in dom_items:
            screen_no = min(it["y"] // viewport_h, len(screenshots) - 1) if screenshots else 0
            # 同屏内的视觉序号（从 0 开始，按 x,y 排序）
            it["screen"] = screen_no
            it["engine"] = "baidu-shot"
            it["page"] = it.get("fromurl", "") or page_url
            items.append(it)
        browser.close()

    # 同屏内排序编号（便于视觉定位：左上→右下）
    items.sort(key=lambda x: (x["screen"], x["y"], x["x"]))
    # 给每个 item 全局唯一 id
    for gi, it in enumerate(items):
        it["id"] = gi
    # 屏内序号
    per_screen = {}
    for it in items:
        s = it["screen"]
        it["idx_in_screen"] = per_screen.get(s, 0)
        per_screen[s] = it["idx_in_screen"] + 1

    print(f"[baidu-shot] {len(items)} 个图片结果，{len(screenshots)} 屏截图", flush=True)
    return items, screenshots


# ================= 补充通道：Bing =================

def bing_images(q, first=0, count=35, retries=2):
    """Bing 图片搜索正常页面解析。URL 与浏览器地址栏一致。
    页面每条结果带 m='...' 属性（HTML 转义 JSON），含 murl/turl/t/purl。"""
    url = (f"https://cn.bing.com/images/search?q={quote_plus(q)}"
           f"&form=HDRSC2&first={first}&count={count}&adlt=off")
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200 or len(r.text) < 2000:
                time.sleep(0.5 * (attempt + 1))
                continue
            items = []
            for gi, m in enumerate(re.finditer(r'm="(\{[^"]+\})"', r.text)):
                try:
                    data = json.loads(m.group(1).replace('&quot;', '"'))
                    murl = data.get("murl", "")
                    if not murl:
                        continue
                    items.append({
                        "id": None,  # 稍后统一编号
                        "url": murl,
                        "thumb_src": data.get("turl", ""),
                        "fromurl": data.get("purl", ""),
                        "title": data.get("t", ""),
                        "x": 0, "y": 0, "w": data.get("mw", 0), "h": data.get("mh", 0),
                        "screen": -1, "idx_in_screen": -1,
                        "engine": "bing", "page": data.get("purl", ""),
                    })
                except Exception:
                    continue
            if items:
                return items
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return []


def bing_paginated(q, pages=1, per_page=35):
    all_items, seen = [], set()
    for p in range(pages):
        first = p * per_page
        items = bing_images(q, first=first, count=per_page)
        new = 0
        for it in items:
            key = re.sub(r'[?&].*$', '', it.get("url", ""))
            if key and key not in seen:
                seen.add(key)
                it["id"] = len(all_items)
                all_items.append(it)
                new += 1
        print(f"[bing] page {p+1}/{pages}: {len(items)} 条，{new} 新", flush=True)
        if not items or new == 0:
            break
        time.sleep(0.5)
    return all_items


# ================= 统一入口 =================

def search_candidates(query, workdir, use_baidu_shot=True, use_bing=True,
                      bing_pages=1):
    """
    统一候选发现。
    - 主通道：百度截图定位（返回 items + screenshots，items 带坐标/标题/屏号）
    - 补充通道：Bing（返回 items，无坐标，用于拼 contact sheet）
    返回：(items, screenshots)
    screenshots 非空时，Agent 优先看按屏截图；Bing 结果可另拼 contact sheet。
    """
    all_items, screenshots = [], []

    if use_baidu_shot:
        try:
            bitems, shots = baidu_screenshot_search(query, workdir)
            for it in bitems:
                it["id"] = len(all_items)
                all_items.append(it)
            screenshots.extend(shots)
        except Exception as e:
            print(f"[search] 百度截图通道失败: {str(e)[:80]}", flush=True)

    if use_bing:
        try:
            bitems = bing_paginated(query, pages=bing_pages)
            for it in bitems:
                it["id"] = len(all_items)
                all_items.append(it)
        except Exception as e:
            print(f"[search] Bing 通道失败: {str(e)[:80]}", flush=True)

    print(f"[search] 合计 {len(all_items)} 个候选，{len(screenshots)} 屏截图", flush=True)
    return all_items, screenshots


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--workdir", default="./out/search")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--no-bing", action="store_true")
    ap.add_argument("--no-baidu", action="store_true")
    args = ap.parse_args()

    if args.check_env:
        ensure_environment()
        sys.exit(0)
    if not args.query:
        ap.error("需要 query（或 --check-env）")

    items, shots = search_candidates(args.query, args.workdir,
                                     use_baidu_shot=not args.no_baidu,
                                     use_bing=not args.no_bing)
    Path(args.workdir).mkdir(parents=True, exist_ok=True)
    (Path(args.workdir) / "search_items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(items)} 候选，{len(shots)} 屏截图")
    for it in items[:8]:
        print(f"  [{it.get('screen','?')}屏#{it.get('idx_in_screen','?')}] "
              f"{str(it.get('title',''))[:30]} | {it['url'][:60]}")

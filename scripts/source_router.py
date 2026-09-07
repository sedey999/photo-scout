#!/usr/bin/env python3
"""
权威源直取（T1-T4）—— 主要服务 logo/图标 类需求。

核心改变：不再依赖硬编码品牌域名字典。品牌名通过动态方式确定官网：
  1) 若调用方提供官网域名（从平台 search 搜“XX 官网”得到），直接用
  2) 内置少量常见品牌快捷域名作为加速（可选，不作为唯一依据）

logo 类需求的原则（在 SKILL/scoring 中强制）：
  - 只取纯色/透明背景的标准 logo 本体
  - 挂 logo 的门店/大楼/产品/招牌图不属于 logo

层级：
  T1 官网 favicon / og:image / 首页 logo
  T2 App Store / 应用市场图标（1024px）
  T3 微博官方账号头像原图（最新 = 当前头像；可选扫描头像相册历史头像）
  T4 百科词条图 / 素材站图标（LobeHub 等，需视觉复核）
输出：URL 列表文件（可直接喂 run.py discover --extra-file）+ 已下载图片。

T3 说明（微博头像）：
  - 微博未登录一律被 Sina Visitor System 拦（requests 直连返回访客系统页），
    必须用 Playwright 真实浏览器：首次访问自动完成访客登记并下发 cookie。
  - 取数用浏览器内 fetch「/ajax/profile/info?uid={uid}」（页面可见的公开数据接口），
    拿 screen_name + profile_image_url，再把尺寸段换成 large 得到原图。
  - 头像文件名是哈希串（tvax1.sinaimg.cn/large/<hash>.jpg），不是数字 uid，
    所以「wx1.sinaimg.cn/large/{uid}.jpg」这类模板是无效的，禁止使用。
  - uid 发现：优先 --weibo-uid 传入；未传则用浏览器搜「XX 官方微博 site:weibo.com」抽取。

各源均为软依赖：单个源失败/超时不影响其他源。
"""
import sys, json, re, io, time, concurrent.futures
from pathlib import Path
from urllib.parse import quote_plus, urljoin
import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 少量常见品牌快捷域名（仅加速用；不在表中的品牌走动态搜索）
KNOWN_BRAND_DOMAINS = {
    "豆包": ["doubao.com", "www.doubao.com"],
    "抖音": ["douyin.com"],
    "瑞幸": ["lkcoffee.com", "www.luckincoffee.com"],
    "瑞幸咖啡": ["lkcoffee.com"],
    "星巴克": ["starbucks.com.cn"],
    "蜜雪冰城": ["mxbc.com"],
    "百度": ["baidu.com"],
    "华为": ["huawei.com", "consumer.huawei.com"],
    "小米": ["mi.com", "xiaomi.com"],
    "名创优品": ["miniso.com", "www.miniso.com"],
    "美的": ["midea.com", "www.midea.com", "midea.cn"],
    "比亚迪": ["byd.com"],
}


def _get(url, timeout=10, headers=None, **kw):
    """带重试的 GET。headers 会与默认 HEADERS 合并（调用方可覆盖/追加）。"""
    h = {**HEADERS, **(headers or {})}
    for attempt in range(2):
        try:
            r = requests.get(url, headers=h, timeout=timeout, **kw)
            if r.status_code == 200 and r.content:
                return r
        except Exception:
            time.sleep(0.4 * (attempt + 1))
    return None


def _save_img(content: bytes, out_dir: Path, tag: str):
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        if w < 48 or h < 48:
            return None
        out_path = out_dir / f"{tag}.png"
        img.save(out_path)
        return {"path": str(out_path), "w": w, "h": h, "size": len(content)}
    except Exception:
        return None


def tier1_official_site(domains, out_dir):
    """抓官网首页，解析 apple-touch-icon/icon/og:image（取最大尺寸）。"""
    results, seen_urls = [], set()
    for d in domains:
        for scheme in ("https", "http"):
            base = f"{scheme}://{d}"
            r = _get(base, timeout=12)
            if not r:
                continue
            html = r.text
            candidates = []
            for m in re.finditer(
                r'<link[^>]+rel=["\'][^"\']*(?:apple-touch-icon|icon|shortcut icon|mask-icon)[^"\']*["\']([^>]*)>',
                html, re.I):
                attrs = m.group(1)
                href_m = re.search(r'href=["\']([^"\']+)["\']', attrs)
                if not href_m:
                    continue
                sizes_m = re.search(r'sizes=["\']([^"\']+)["\']', attrs)
                sizes = 0
                if sizes_m:
                    sm = re.match(r'(\d+)', sizes_m.group(1))
                    if sm:
                        sizes = int(sm.group(1))
                candidates.append((sizes, href_m.group(1)))
            for m in re.finditer(
                r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)["\']',
                html, re.I):
                candidates.append((9999, m.group(1)))
            by_href = {}
            for sizes, href in candidates:
                full = urljoin(base + "/", href)
                if full in by_href and sizes <= by_href[full][0]:
                    continue
                by_href[full] = (sizes, "")
            for i, (full, (sizes, _)) in enumerate(
                    sorted(by_href.items(), key=lambda x: -x[1][0])[:5]):
                if full in seen_urls:
                    continue
                ir = _get(full, timeout=12)
                if not ir or len(ir.content) < 1500:
                    continue
                tag = f"t1_{re.sub(r'[^a-zA-Z0-9]', '_', d)}_{sizes or i}"
                info = _save_img(ir.content, out_dir, tag)
                if info:
                    info.update({"tier": 1, "source": f"official:{d}", "url": full,
                                 "declared_size": sizes})
                    results.append(info)
                    seen_urls.add(full)
            break
    results.sort(key=lambda x: -(x["w"] * x["h"]))
    return results


def tier2_app_store(keyword, out_dir, country="cn", limit=8):
    """App Store 图标（替换为 1024px），按名称匹配度排序。"""
    url = (f"https://itunes.apple.com/search?term={quote_plus(keyword)}"
           f"&country={country}&media=software&limit={limit}")
    r = _get(url, timeout=12)
    if not r:
        return []
    try:
        apps = r.json().get("results", [])
    except Exception:
        return []
    kw = keyword.lower().replace(" logo", "").replace("logo", "").strip()

    def rank(a):
        name = (a.get("trackName") or "").lower()
        if name == kw:
            return 0
        if name.startswith(kw):
            return 1
        if kw in name:
            return 2
        return 5
    apps.sort(key=rank)
    results = []
    for i, app in enumerate(apps):
        for k in ("artworkUrl512", "artworkUrl100", "artworkUrl60"):
            if app.get(k):
                img_url = re.sub(r'/\d+x\d+(bb)?\.[a-z]+$', '/1024x1024bb.png', app[k])
                ir = _get(img_url, timeout=12)
                if ir and len(ir.content) > 5000:
                    info = _save_img(ir.content, out_dir, f"t2_app_r{rank(app)}_{i}")
                    if info:
                        info.update({"tier": 2,
                                     "source": f"appstore:{app.get('trackName')}",
                                     "url": img_url, "seller": app.get("sellerName", ""),
                                     "match_rank": rank(app)})
                        results.append(info)
                break
    results.sort(key=lambda x: x.get("match_rank", 9))
    return results


# ---------------------------------------------------------------- T3 微博头像

WEIBO_REFERER = {"Referer": "https://weibo.com/"}
_SINAIMG_RE = re.compile(
    r'(https?://[a-z0-9]+\.sinaimg\.cn)/([^/]+)/([A-Za-z0-9_\-]+\.(?:jpg|jpeg|png|gif))',
    re.I)
# 需要换成 large 的尺寸段（缩略/裁剪/中等尺寸）；mw2000、orj1080 已足够大，保留
_SINAIMG_SMALL_RE = re.compile(
    r'^(crop\.|thumbnail|square|small|bmiddle|wap\d+|thumb\d+|orj\d+|\d+x\d+)', re.I)
_AVATAR_HOST_RE = re.compile(r'https?://tvax\d\.sinaimg\.cn/', re.I)


def _upgrade_sinaimg(url):
    """把 sinaimg 的裁剪/缩略尺寸段换成 large（原图），已是原图尺寸的保持不动。"""
    if not url:
        return url
    clean = url.split("?")[0]        # 去掉 ?KID=imgbed... 签名参数
    m = _SINAIMG_RE.match(clean)
    if not m:
        return clean
    host, size, name = m.groups()
    if size == "large" or size.startswith("mw"):
        return clean
    if _SINAIMG_SMALL_RE.match(size):
        return f"{host}/large/{name}"
    return clean


def _weibo_browser(exe):
    """启动带反检测配置的 Chromium（与 search_engines 主通道一致）。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        executable_path=exe, headless=True,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(user_agent=HEADERS["User-Agent"], locale="zh-CN",
                              viewport={"width": 1440, "height": 900})
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return pw, browser, ctx


def _weibo_uid_from_search(page, query, limit=3):
    """用微博自家用户搜索发现官方账号 uid（访客态可访问，外部搜索被反爬）。"""
    try:
        page.goto("https://s.weibo.com/user?q=" + quote_plus(query),
                  timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        hrefs = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href)") or []
    except Exception:
        return []
    uids = []
    for h in hrefs:
        for m in re.finditer(r'weibo\.com/u/(\d{5,})', h):
            uid = m.group(1)
            if uid not in uids:
                uids.append(uid)
    return uids[:limit]


def _weibo_profile_info(page, uid):
    """浏览器内 fetch 微博公开数据接口，返回 (screen_name, avatar_url)。"""
    data = page.evaluate(
        """async (uid) => {
            try {
                const r = await fetch('https://weibo.com/ajax/profile/info?uid=' + uid, {
                    headers: {'x-requested-with': 'XMLHttpRequest',
                              'accept': 'application/json'}});
                if (!r.ok) return null;
                const j = await r.json();
                const u = (j && j.data && j.data.user) || null;
                if (!u) return null;
                return {name: u.screen_name || '',
                        avatar: u.avatar_hd || u.profile_image_url || '',
                        verified: !!u.verified,
                        vtype: u.verified_type,
                        vreason: u.verified_reason || ''};
            } catch (e) { return null; }
        }""", uid)
    if not data or not data.get("avatar"):
        return None
    return data


def _weibo_album_urls(page, uid, limit=12):
    """打开相册页，收集头像 CDN（tvax*.sinaimg.cn）上的历史头像原图。"""
    try:
        page.goto(f"https://weibo.com/u/{uid}?tabtype=album",
                  timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(1500)
        html = page.content()
    except Exception:
        return []
    urls = []
    for m in _SINAIMG_RE.finditer(html):
        full = m.group(0)
        if not _AVATAR_HOST_RE.match(full):
            continue
        up = _upgrade_sinaimg(full)
        if up not in urls:
            urls.append(up)
    return urls[:limit]


def _classify_weibo_name(name, kw):
    """按昵称与品牌词的关系分级：2=官方主账号，1=相关号（粉丝/子IP），0=无关。

    只对自动发现的 uid 做过滤；调用方显式传 --weibo-uid 时全部放行。
    判定（以 n=昵称、k=品牌词）：
      2  昵称==品牌词；品牌词开头+官方后缀；品牌词结尾且前缀是英文名/官方后缀
         （luckincoffee瑞幸咖啡、瑞幸咖啡官方微博）
      1  品牌词在昵称中但前后有中文修饰（黄恺爱喝蜜雪冰城、蜜雪冰城雪王）
      0  品牌词不在昵称中
    """
    n = (name or "").strip().lstrip("@")
    if not kw or not n:
        return 1
    k = kw.lower()
    nl = n.lower()
    base = re.sub(r'(官方微博|官方|旗舰店|官微)$', '', n).strip()
    bl = base.lower()
    if nl == k or bl == k:
        return 2
    if n.startswith(kw) and re.search(r'(官方微博|官方|旗舰店|官微)$', n):
        return 2
    # 品牌词结尾：前缀若为纯英文/数字（英文名、拼音、官微后缀）算官方
    if nl.endswith(k):
        prefix = nl[:-len(k)]
        if re.fullmatch(r'[a-z0-9_\-]*', prefix):
            return 2
    if k in nl:
        return 1
    return 0


def tier3_weibo_avatar(query, out_dir, uids=None, with_album=False, timeout=60):
    """T3 微博官方账号头像原图。

    uids 为空时先用微博用户搜索发现官方账号 uid（自动发现时按昵称匹配度过滤，
    只下官方主账号 + 品牌词开头的官方后缀号；粉丝号、个人号排除）。
    显式传入的 uid 全部放行（视为用户已确认）。
    需要 Playwright + Chromium（微博未登录必须走浏览器访客态）。
    """
    try:
        import playwright  # noqa
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from search_engines import find_chrome_executable
        exe = find_chrome_executable()
    except Exception as e:
        print(f"  T3 微博: 跳过（浏览器不可用：{str(e)[:50]}）", flush=True)
        return []
    if not exe:
        print("  T3 微博: 跳过（未找到 Chromium）", flush=True)
        return []

    results = []
    try:
        pw, browser, ctx = _weibo_browser(exe)
    except Exception as e:
        print(f"  T3 微博: 跳过（浏览器启动失败：{str(e)[:50]}）", flush=True)
        return []

    try:
        page = ctx.new_page()
        try:
            page.goto("https://weibo.com/", timeout=40000,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  T3 微博: 首页访问失败（{str(e)[:50]}）", flush=True)

        found = list(uids or [])
        if not found:
            found = _weibo_uid_from_search(page, query)
            if found:
                print(f"  T3 微博: 搜到 uid {found}", flush=True)
        if not found:
            print("  T3 微博: 未拿到 uid（可用 --weibo-uid 直接指定）", flush=True)
            return []

        # API 调用跨域会失败；用专门的 weibo.com 页面发起 fetch
        api_page = ctx.new_page()
        try:
            api_page.goto("https://weibo.com/", timeout=40000,
                          wait_until="domcontentloaded")
            api_page.wait_for_timeout(2500)
        except Exception:
            pass

        kw = query.lower().replace(" logo", "").replace("logo", "").strip()
        explicit = bool(uids)   # 显式传入的 uid 视为已确认，全部放行
        for uid in found:
            info = _weibo_profile_info(api_page, uid)
            if not info:
                print(f"  T3 微博: uid {uid} 未取到头像", flush=True)
                continue
            name = info.get("name") or ""
            tier_name = 2 if explicit else _classify_weibo_name(name, kw)
            if tier_name < 2:
                role = {1: "相关号（粉丝/子IP），跳过", 0: "名称不匹配，跳过"}[tier_name]
                print(f"  T3 微博: uid {uid} @{name} → {role}", flush=True)
                continue
            avatar = _upgrade_sinaimg(info["avatar"])
            ir = _get(avatar, timeout=15, headers={**HEADERS, **WEIBO_REFERER})
            if ir and len(ir.content) > 1500:
                tag = f"t3_weibo_{uid}"
                meta = _save_img(ir.content, out_dir, tag)
                if meta:
                    meta.update({"tier": 3, "source": f"weibo:avatar:{uid}",
                                 "url": avatar, "screen_name": name,
                                 "verified": info.get("verified", False),
                                 "verified_reason": info.get("vreason", ""),
                                 "name_match": True,
                                 "note": "当前头像（头像相册中最新的那张）"})
                    results.append(meta)
                    print(f"  T3 微博: uid {uid} @{name} ✓ "
                          f"{meta['w']}x{meta['h']}", flush=True)

            if with_album:
                for i, u in enumerate(_weibo_album_urls(page, uid)):
                    ir = _get(u, timeout=15, headers={**HEADERS, **WEIBO_REFERER})
                    if not ir or len(ir.content) < 1500:
                        continue
                    meta = _save_img(ir.content, out_dir, f"t3_weibo_album_{uid}_{i}")
                    if meta:
                        meta.update({"tier": 3, "source": f"weibo:album:{uid}",
                                     "url": u, "screen_name": name,
                                     "name_match": True,
                                     "note": "头像相册候选，需视觉门控确认"})
                        results.append(meta)
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
    return results


def harvest_brand(query, out_dir, official_domains=None, use_appstore=True,
                  weibo_uids=None, weibo_album=False, use_weibo=True):
    """
    logo/图标 权威源直取。
    official_domains: 调用方从平台 search 搜到的官网域名列表（可选）；
                      为空则查内置快捷字典。
    输出：
      - 下载图片到 out_dir
      - out_dir/urls.txt：纯 URL 列表（可直接喂 run.py --extra-file）
      - out_dir/harvest.json：元数据
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_results = []

    domains = list(official_domains or [])
    if not domains:
        # 用品牌词查快捷字典（模糊匹配）
        for k, ds in KNOWN_BRAND_DOMAINS.items():
            if k in query or query.replace("logo", "").strip() in k:
                domains.extend(ds)
                break

    def _run(label, fn, timeout=18):
        try:
            with concurrent.futures.ThreadPoolExecutor() as ex:
                r = ex.submit(fn).result(timeout=timeout)
                print(f"  {label}: {len(r)} 张", flush=True)
                return r
        except Exception as e:
            print(f"  {label}: 跳过 ({str(e)[:40]})", flush=True)
            return []

    if domains:
        all_results.extend(_run(f"T1 官网 {domains}",
                                lambda: tier1_official_site(domains, out_dir)))
    else:
        print("  T1: 未提供官网域名且不在快捷字典，跳过（建议先用平台 search 搜“XX 官网”）", flush=True)
    if use_appstore:
        all_results.extend(_run("T2 App Store",
                                lambda: tier2_app_store(query, out_dir)))
    if use_weibo:
        all_results.extend(_run("T3 微博头像",
                                lambda: tier3_weibo_avatar(
                                    query, out_dir, weibo_uids,
                                    with_album=weibo_album),
                                timeout=120))

    (out_dir / "harvest.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    urls = [r["url"] for r in all_results if r.get("url")]
    (out_dir / "urls.txt").write_text("\n".join(urls), encoding="utf-8")
    print(f"  共 {len(all_results)} 张，URL 列表 → {out_dir/'urls.txt'}", flush=True)
    return all_results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="品牌/产品名（logo 类）")
    ap.add_argument("outdir", nargs="?", default="./out/brand")
    ap.add_argument("--domains", nargs="*", help="官网域名（从平台 search 得到）")
    ap.add_argument("--no-appstore", action="store_true")
    ap.add_argument("--weibo-uid", nargs="*", dest="weibo_uid",
                    help="官方微博 uid（可多个；不传则自动搜索发现）")
    ap.add_argument("--weibo-album", action="store_true",
                    help="同时扫描微博头像相册的历史头像（需视觉门控）")
    ap.add_argument("--no-weibo", action="store_true", help="跳过微博头像源")
    args = ap.parse_args()
    harvest_brand(args.query, args.outdir,
                  official_domains=args.domains, use_appstore=not args.no_appstore,
                  weibo_uids=args.weibo_uid,
                  weibo_album=args.weibo_album,
                  use_weibo=not args.no_weibo)

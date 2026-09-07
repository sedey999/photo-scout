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
  T3 百科词条图 / 素材站图标（LobeHub 等，需视觉复核）
输出：URL 列表文件（可直接喂 run.py discover --extra-file）+ 已下载图片。

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


def _get(url, timeout=10, **kw):
    for attempt in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, **kw)
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


def harvest_brand(query, out_dir, official_domains=None, use_appstore=True):
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
    args = ap.parse_args()
    harvest_brand(args.query, args.outdir,
                  official_domains=args.domains, use_appstore=not args.no_appstore)

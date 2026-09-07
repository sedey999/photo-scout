#!/usr/bin/env python3
"""从一个网页抓取所有候选图片URL，自动筛选合适尺寸/格式的图，输出 JSON。"""
import sys, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def extract_images(url, min_w=200, min_h=200):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                         timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"  fail: {e}", file=sys.stderr)
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    cands = []
    seen = set()
    for img in soup.find_all("img"):
        src = (img.get("data-src") or img.get("data-original") or
               img.get("data-actualsrc") or img.get("src") or "")
        if not src or src.startswith("data:"):
            continue
        full = urljoin(url, src)
        if full in seen:
            continue
        seen.add(full)
        # 解析声明尺寸
        w = img.get("width") or img.get("data-w")
        h = img.get("height") or img.get("data-h")
        try: w = int(str(w).rstrip("px")) if w else 0
        except: w = 0
        try: h = int(str(h).rstrip("px")) if h else 0
        except: h = 0
        alt = img.get("alt", "")
        title = img.get("title", "")
        # 跳过小图标
        if (w and w < min_w) or (h and h < min_h):
            continue
        path_lower = full.lower()
        if any(path_lower.endswith(ext) for ext in (".svg", ".gif", ".ico")):
            # SVG 对 logo 场景有价值，保留；gif/ico 跳过
            if path_lower.endswith((".gif", ".ico")):
                continue
        cands.append({
            "url": full,
            "page": url,
            "declared_w": w,
            "declared_h": h,
            "alt": alt,
            "title": title,
            "engine": "webpage",
        })
    # meta og:image
    for m in soup.find_all("meta"):
        prop = (m.get("property") or m.get("name") or "").lower()
        if prop in ("og:image", "twitter:image"):
            src = m.get("content")
            if src and src not in seen:
                seen.add(src)
                cands.append({"url": urljoin(url, src), "page": url,
                              "declared_w": 0, "declared_h": 0,
                              "alt": "og:image", "title": "", "engine": "og"})
    return cands


if __name__ == "__main__":
    urls = sys.argv[1:]
    all_items = []
    for u in urls:
        print(f"-> {u}", file=sys.stderr)
        items = extract_images(u)
        print(f"   found {len(items)}", file=sys.stderr)
        all_items.extend(items)
    print(json.dumps(all_items, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""
视觉管线核心库（纯函数模块，无 CLI 入口——统一入口在 run.py）

提供：
  _download_image(url)   下载图片为 PIL Image，吞掉所有网络异常
  build_sheet(items, out_path)  把候选缩略图拼成 contact sheet（网格总览）
  sharpness_of(img)      Laplacian 梯度清晰度评分

关键设计：相关性判断完全由多模态模型完成（看 contact sheet），
本模块只做 I/O 与客观指标计算。

反爬/原图技巧：
  - 按 CDN 域名自动注入 Referer（防盗链）
  - 清理 CDN 缩略图 resize 参数还原原图
  - Content-Type 校验，防 HTML 假响应
"""
import io, time, re
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 按 CDN 域名自动注入 Referer（防盗链图床必需）
_REFERER_MAP = [
    (re.compile(r'img\d*\.baidu\.com|gips\d*\.baidu\.com|bdstatic\.com'), "https://image.baidu.com/"),
    (re.compile(r'sogoucdn\.com'), "https://pic.sogou.com/"),
    (re.compile(r'qhimg\.com|so\.com'), "https://image.so.com/"),
    (re.compile(r'mm\.bing\.net|bing\.net'), "https://cn.bing.com/"),
    (re.compile(r'sinaimg\.cn|weibocdn'), "https://weibo.com/"),
    (re.compile(r'toutiaoimg\.com|pstatp\.com'), "https://www.toutiao.com/"),
    (re.compile(r'douyinpic\.com|douyincdn'), "https://www.douyin.com/"),
    (re.compile(r'itc\.cn'), "https://www.sohu.com/"),
]


def _referer_for(url):
    for pat, ref in _REFERER_MAP:
        if pat.search(url):
            return ref
    return None


def clean_resize_params(url):
    """清理 CDN 缩略图参数，尽量还原原图 URL。"""
    url = re.sub(r'[?&]x-bce-process=image/[^&]*', '', url)          # 百度BCE处理
    url = re.sub(r'!watermark.*$', '', url)                            # voc水印
    url = re.sub(r'!(?:thumb|w\w+|wh\w+|large|small)[^/]*$', '', url) # 七牛/阿里样式
    url = re.sub(r'[?&](?:imageView2/[^&]*|x-oss-process=[^&]*)', '', url)
    url = re.sub(r'\?$', '', url).replace('?&', '?')
    url = re.sub(r'&$', '', url)
    return url


def _get(url, timeout=10, referer=None):
    headers = {"User-Agent": UA,
               "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
               "Accept-Language": "zh-CN,zh;q=0.9"}
    ref = referer or _referer_for(url)
    if ref:
        headers["Referer"] = ref
    for attempt in range(2):
        try:
            r = requests.get(url, headers=headers, timeout=timeout, stream=True)
            if r.status_code == 200:
                ctype = r.headers.get("Content-Type", "")
                if "text" in ctype or "html" in ctype:
                    return None  # 防 HTML 假响应
                return r
        except Exception:
            time.sleep(0.3 * (attempt + 1))
    return None


def _download_image(url, referer=None, timeout=12, try_original=True):
    """下载图片为 (PIL.Image, content_bytes)；任何失败返回 (None, None)。
    try_original: 首次失败时自动清理 resize 参数重试一次（争取原图）。"""
    urls = [url]
    if try_original:
        cleaned = clean_resize_params(url)
        if cleaned != url:
            urls.append(cleaned)
    for attempt_url in urls:
        try:
            r = _get(attempt_url, timeout=timeout, referer=referer)
        except Exception:
            r = None
        if not r:
            continue
        try:
            content = r.content
        except Exception:
            continue
        if len(content) < 1500:
            continue
        try:
            img = Image.open(io.BytesIO(content))
            img.load()
            return img, content
        except Exception:
            continue
    return None, None


def _font(size=14):
    """跨平台中文字体查找；找不到时回退 PIL 内置字体（编号是数字，不影响核心判断）。"""
    candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def build_sheet(candidates, out_path, cols=6, cell=260, pad=32, mark_ids=None):
    """
    把候选缩略图拼成网格总览 contact sheet。
    candidates: [{_thumb: PIL.Image, engine, w, h, title}, ...]
    mark_ids: 需要描红边的编号集合（复核阶段用）
    返回 out_path
    """
    mark_ids = set(mark_ids or [])
    rows = (len(candidates) + cols - 1) // cols
    W = cols * cell + 20
    H = rows * (cell + pad) + 20
    sheet = Image.new("RGB", (W, H), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    f_num = _font(15)
    f_meta = _font(11)

    for i, item in enumerate(candidates):
        r, c = divmod(i, cols)
        x = 10 + c * cell
        y = 10 + r * (cell + pad)
        img = item.get("_thumb")
        if img:
            thumb = img.copy()
            thumb.thumbnail((cell - 8, cell - 8))
            ix = x + (cell - thumb.size[0]) // 2
            iy = y + (cell - thumb.size[1]) // 2
            sheet.paste(thumb, (ix, iy))
        color = (220, 30, 30) if i in mark_ids else (40, 40, 40)
        draw.rectangle([x, y, x + 30, y + 22], fill=color)
        draw.text((x + 5, y + 3), f"{i:02d}", fill="white", font=f_num)
        meta = f"{item.get('engine','?')} {item.get('w','?')}x{item.get('h','?')}"
        draw.text((x + 34, y + 5), meta, fill=(60, 60, 60), font=f_meta)
        title = (item.get("title") or "")[:20]
        draw.text((x + 4, y + cell + 4), title, fill=(20, 20, 20), font=f_meta)
        if i in mark_ids:
            draw.rectangle([x + 1, y + 1, x + cell - 1, y + cell - 1],
                           outline=(220, 30, 30), width=4)

    sheet.save(out_path, "JPEG", quality=86)
    return out_path


def sharpness_of(img):
    """Laplacian 梯度清晰度（numpy 可选；不可用返回 None）。
    <5 明显模糊，5-10 一般，>10 清晰。"""
    try:
        import numpy as np
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        gx = np.diff(gray, axis=1)
        gy = np.diff(gray, axis=0)
        return float(np.sqrt(gx[:-1, :] ** 2 + gy[:, :-1] ** 2).mean())
    except Exception:
        return None

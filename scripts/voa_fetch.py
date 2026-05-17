"""
VOA Learning English 文章抓取 → 发音练习导入脚本

用法：
    # 本地环境（默认）
    python scripts/voa_fetch.py

    # 线上环境
    python scripts/voa_fetch.py --base-url https://your-domain.com

    # 其他选项
    python scripts/voa_fetch.py --count 5                 # 只抓 5 篇
    python scripts/voa_fetch.py --section /z/3521         # 抓其他栏目
    python scripts/voa_fetch.py --dry-run                 # 只抓取不导入

通过 API 导入（POST /practice/sources/import），本地/线上通用。
首次运行时会提示输入邮箱和密码获取 JWT token，缓存到 ~/.speakeasy_token。
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VOA_BASE = "https://learningenglish.voanews.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TOKEN_CACHE = Path.home() / ".speakeasy_token"


# ── HTTP helpers ─────────────────────────────────────────────

def _is_local(url: str) -> bool:
    return "localhost" in url or "127.0.0.1" in url


def fetch_page(url: str) -> str:
    """用 curl 抓取网页（绕 SSL 证书问题）"""
    result = subprocess.run(
        ["curl", "-s", "-L", "-H", f"User-Agent: {UA}", url],
        capture_output=True, text=True, timeout=20,
    )
    return result.stdout


def api_call(base_url: str, path: str, token: str,
             method: str = "POST", payload: dict = None) -> dict:
    """调用 Speakeasy API（本地自动跳过代理）"""
    cmd = ["curl", "-s", "-X", method]
    if _is_local(base_url):
        cmd.append("--noproxy")
        cmd.append("*")
    cmd += [
        f"{base_url}{path}",
        "-H", f"Authorization: Bearer {token}",
        "-H", "Content-Type: application/json",
    ]
    if payload:
        cmd += ["-d", json.dumps(payload, ensure_ascii=False)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout or result.stderr}


# ── 认证 ─────────────────────────────────────────────────────

def get_token(base_url: str) -> str:
    """从缓存读取或交互式登录获取 JWT token"""
    cache_key = base_url.rstrip("/")

    # 读缓存
    if TOKEN_CACHE.exists():
        try:
            cache = json.loads(TOKEN_CACHE.read_text())
            if cache_key in cache:
                token = cache[cache_key]
                # 验证 token 是否有效
                resp = api_call(base_url, "/auth/me", token, method="GET")
                if "user" in resp or "id" in resp or "email" in resp:
                    return token
                print("Token 已过期，重新登录...")
        except (json.JSONDecodeError, KeyError):
            pass

    # 交互式登录
    import getpass
    email = input(f"Email ({base_url}): ").strip()
    password = getpass.getpass("Password: ")

    cmd = ["curl", "-s", "-X", "POST"]
    if _is_local(base_url):
        cmd += ["--noproxy", "*"]
    cmd += [
        f"{base_url}/auth/login",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"email": email, "password": password}),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Login failed: {result.stdout}")
        sys.exit(1)

    if "token" not in data:
        print(f"Login failed: {data}")
        sys.exit(1)

    token = data["token"]

    # 写缓存
    cache = {}
    if TOKEN_CACHE.exists():
        try:
            cache = json.loads(TOKEN_CACHE.read_text())
        except json.JSONDecodeError:
            pass
    cache[cache_key] = token
    TOKEN_CACHE.write_text(json.dumps(cache))
    TOKEN_CACHE.chmod(0o600)
    print("Login OK, token cached.\n")
    return token


# ── VOA 解析 ─────────────────────────────────────────────────

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles: List[Tuple[str, str]] = []
        self.in_link = False
        self.href = ""
        self.title = ""
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href", "").startswith("/a/"):
            self.in_link = True
            self.href = d["href"]
            self.title = ""
            self.depth = 1
        elif self.in_link:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.in_link:
            self.depth -= 1
            if tag == "a" and self.depth <= 0:
                t = self.title.strip()
                if t and len(t) > 10:
                    self.articles.append((t, self.href))
                self.in_link = False

    def handle_data(self, data):
        if self.in_link:
            self.title += data


def get_article_list(section: str, count: int) -> List[Dict]:
    html = fetch_page(f"{VOA_BASE}{section}")
    parser = _LinkParser()
    parser.feed(html)
    seen = set()
    result = []
    for title, href in parser.articles:
        if href not in seen:
            seen.add(href)
            result.append({"title": title, "url": f"{VOA_BASE}{href}", "href": href})
    return result[:count]


def extract_segments(html: str) -> List[Dict]:
    wsw_start = html.find('class="wsw"')
    if wsw_start < 0:
        return []
    rest = html[wsw_start:wsw_start + 20000]
    paras = re.findall(r'<p[^>]*>(.*?)</p>', rest, re.DOTALL)
    segments = []
    for p in paras:
        clean = re.sub(r'<[^>]+>', '', p).strip()
        if not clean or len(clean) < 25:
            continue
        if clean.startswith("_") or clean.startswith("No media"):
            continue
        if "VOA Learning English" in clean and len(clean) < 80:
            continue
        if "wrote this story" in clean.lower():
            continue
        if "let's hear" in clean.lower() and len(clean) < 60:
            continue
        segments.append({"content": clean})
    return segments


def extract_published_at(html: str) -> Optional[str]:
    """从 <time datetime="..."> 提取 ISO 发布时间"""
    m = re.search(r'<time[^>]*datetime="([^"]+)"', html)
    return m.group(1) if m else None


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VOA Learning English → Practice 导入")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Speakeasy API 地址（默认 http://localhost:8000）")
    parser.add_argument("--section", default="/z/987",
                        help="VOA 栏目路径（默认 /z/987 Words and Their Stories）")
    parser.add_argument("--count", type=int, default=10, help="抓取文章数量（默认 10）")
    parser.add_argument("--dry-run", action="store_true", help="只抓取不导入")
    args = parser.parse_args()

    print(f"VOA Section: {VOA_BASE}{args.section}")
    print(f"API Target:  {args.base_url}")
    print(f"Count:       {args.count}")
    print()

    # Step 1: 抓取文章列表
    articles = get_article_list(args.section, args.count)
    print(f"Found {len(articles)} articles\n")

    # Step 2: 逐篇抓取正文
    articles_data = []
    for i, art in enumerate(articles):
        print(f"[{i+1}/{len(articles)}] {art['title']}")
        try:
            html = fetch_page(art["url"])
            segments = extract_segments(html)
            published_at = extract_published_at(html)
            print(f"  → {len(segments)} segments, published: {published_at or 'unknown'}")

            url_match = re.search(r'/(\d+)\.html', art["url"])
            source_id = f"voa_{url_match.group(1)}" if url_match else \
                f"voa_{hashlib.md5(art['url'].encode()).hexdigest()[:12]}"

            articles_data.append({
                "source_id": source_id,
                "source_type": "voa",
                "title": f"VOA: {art['title']}",
                "url": art["url"],
                "segments": segments,
                "published_at": published_at,
            })
            time.sleep(0.3)
        except Exception as e:
            print(f"  ✗ Error: {e}")

    total_segs = sum(len(a["segments"]) for a in articles_data)
    print(f"\nTotal: {total_segs} segments from {len(articles_data)} articles")

    if args.dry_run:
        out_path = "/tmp/voa_practice_items.json"
        with open(out_path, "w") as f:
            json.dump(articles_data, f, ensure_ascii=False, indent=2)
        print(f"\nDry-run: saved to {out_path}")
        return

    # Step 3: 登录 + 导入
    token = get_token(args.base_url)

    print("Importing...")
    ok = 0
    for art in articles_data:
        payload = {
            "source_id": art["source_id"],
            "source_type": art["source_type"],
            "title": art["title"],
            "segments": art["segments"],
            "source_url": art["url"],
            "published_at": art.get("published_at"),
        }
        resp = api_call(args.base_url, "/practice/sources/import", token, payload=payload)
        if "error" in resp or "detail" in resp:
            print(f"  ✗ {art['title']}: {resp.get('error') or resp.get('detail')}")
        else:
            print(f"  ✓ {art['title']} ({resp.get('segments_count', '?')} segments)")
            ok += 1

    print(f"\n✅ Done! {ok}/{len(articles_data)} articles imported.")
    print("Go to Practice → 📚 历史 to start practicing.")


if __name__ == "__main__":
    main()

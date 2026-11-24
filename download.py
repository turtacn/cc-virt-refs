#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Download CC/virtualization resources organized by category and pack into ZIP.
Usage:
  python3 download.py                                        # use urls.txt (respects HTTP_PROXY / HTTPS_PROXY)
  python3 download.py mylist.txt                             # use custom list
  python3 download.py --nozip                                # download only, no zip
  python3 download.py --proxy http://127.0.0.1:7890
  python3 download.py --proxy socks5://127.0.0.1:7891        # requires PySocks (pip install pysocks)
  python3 download.py --url https://example.com/a.pdf        # download single URL
  python3 download.py --url https://example.com/a.pdf --subdir 01_virtualization_pps
  python3 download.py --retries 3 --retry-delay 2            # retry failed requests
  python3 download.py --insecure                             # disable SSL cert verification if needed
"""

import hashlib
import os
import re
import ssl
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Connection": "keep-alive",
}

OUTDIR = Path("artifacts")
ZIPNAME = "cc-virt-refs.zip"
TIMEOUT = 60
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = 1.5

# 分类名 -> 输出子目录
CATEGORY_DIR = {
    "cc-standards":       "00_cc_standards",
    "virtualization-pps": "01_virtualization_pps",
    "other-pps":          "02_other_pps",
    "product-examples":   "03_product_examples",
    "writing-guides":     "04_writing_guides",
    "research":           "05_research_literature",
    "github-repos":       "06_github_repos",
}
DEFAULT_CAT = "00_misc"

# 默认清单（若 urls.txt 不存在）
DEFAULT_URLS = """
[cc-standards]
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART1R1.pdf
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART2R1.pdf
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART3R1.pdf
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART4R1.pdf
https://www.commoncriteriaportal.org/files/ccfiles/CC2022PART5R1.pdf
https://www.commoncriteriaportal.org/files/ccfiles/CEM2022R1.pdf
https://www.commoncriteriaportal.org/cc/index.cfm

[virtualization-pps]
https://sec-certs.org/pp/1a418f87e23daafe/profile.pdf
https://commoncriteria.github.io/virtualization/master/virtualization-release.html
https://www.commoncriteriaportal.org/nfs/ccpfiles/files/ppfiles/PP_VIRTUALIZATION_BASE_V1.1.pdf
https://www.commoncriteriaportal.org/files/ppfiles/MOD_SV_v1.0.pdf
https://commoncriteria.github.io/pp/servervirtualization/servervirtualization-sd.html
https://commoncriteria.github.io/pp/clientvirtualization/clientvirtualization.pdf

[other-pps]
https://commoncriteriaportal.org/files/ppfiles/pp0067b_pdf.pdf
https://www.commoncriteriaportal.org/files/ppfiles/pp_gpos_v3.9.pdf
https://www.commoncriteriaportal.org/files/ppfiles/pp_skpp_hr_v1.03.pdf

[product-examples]
https://www.commoncriteriaportal.org/nfs/ccpfiles/files/epfiles/st_vid11249-vr.pdf
https://oracle.com/a/ocom/docs/kvm-assurance-activity-report.pdf
https://www.commoncriteriaportal.org/nfs/ccpfiles/files/epfiles/st_nutanix_nec_515_v0.7.pdf

[writing-guides]
https://www.commoncriteriaportal.org/files/ccfiles/CommonCriteriaDevelopersGuide_1_0.pdf
https://www.ipa.go.jp/security/jisec/apdx/documents/27N6645_DTR_15446.pdf

[research]
https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-125Ar1.pdf
https://arxiv.org/pdf/2104.13660
https://apps.dtic.mil/sti/pdfs/ADA535069.pdf

[github-repos]
https://github.com/commoncriteria/virtualization/archive/refs/heads/master.zip
https://github.com/commoncriteria/pp-template/archive/refs/heads/master.zip
https://github.com/commoncriteria/transforms/archive/refs/heads/master.zip
https://github.com/n-design/n-doc/archive/refs/heads/master.zip
https://github.com/AbstractionsLab/c5dec/archive/refs/heads/master.zip
https://github.com/crocs-muni/sec-certs/archive/refs/heads/master.zip
https://github.com/codelabs-ch/muen/archive/refs/heads/master.zip
https://github.com/seL4/l4v/archive/refs/heads/master.zip
""".strip().splitlines()


def _normalize_proxy_url(proxy_url: str) -> str:
    p = proxy_url.strip()
    if p.startswith("socks5h://"):
        return "socks5://" + p[len("socks5h://"):]
    return p


def build_opener(cli_proxy: str | None = None, insecure: bool = False):
    """构建 OpenerDirector：优先读取环境变量 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY 与 NO_PROXY"""
    env = os.environ
    http_proxy = (
        cli_proxy
        or env.get("HTTP_PROXY")
        or env.get("http_proxy")
        or env.get("ALL_PROXY")
        or env.get("all_proxy")
    )
    https_proxy = (
        cli_proxy
        or env.get("HTTPS_PROXY")
        or env.get("https_proxy")
        or env.get("ALL_PROXY")
        or env.get("all_proxy")
    )
    no_proxy = env.get("NO_PROXY") or env.get("no_proxy") or ""

    proxies = {}
    if http_proxy:
        proxies["http"] = _normalize_proxy_url(http_proxy)
    if https_proxy:
        proxies["https"] = _normalize_proxy_url(https_proxy)

    if no_proxy.strip() == "*":
        proxies = {}

    handlers = []
    if proxies:
        handlers.append(urllib.request.ProxyHandler(proxies))

    if insecure:
        ctx = ssl._create_unverified_context()
        handlers.append(urllib.request.HTTPSHandler(context=ctx))

    return urllib.request.build_opener(*handlers), proxies


def _clean_url(raw_url: str) -> str:
    s = raw_url.strip().strip('"').strip("'")
    # 兼容 Markdown 链接格式 [https://...](https://...)
    m_md = re.match(r"^\[[^\]]*\]\((https?://[^)\s]+)\)$", s)
    if m_md:
        return m_md.group(1).strip()
    # 兼容误写成 [https://...] 的格式
    m_br = re.match(r"^\[(https?://[^\]\s]+)\]$", s)
    if m_br:
        return m_br.group(1).strip()
    return s


def parse_listing(lines):
    """解析 urls.txt：支持 [分类] 和 URL -> 指定相对路径"""
    items, cur_cat = [], DEFAULT_CAT
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m_cat = re.match(r"^\[(.+?)\]$", s)
        if m_cat:
            cur_cat = CATEGORY_DIR.get(m_cat.group(1), m_cat.group(1).replace(" ", "_"))
            continue
        if "->" in s:
            url_part, rel = s.split("->", 1)
            url = _clean_url(url_part)
            if url:
                items.append((url, rel.strip().strip('"')))
        else:
            url = _clean_url(s)
            if url:
                items.append((url, cur_cat))
    return items


def _candidates(url):
    yield url
    m = re.match(r"^(https://github\.com/[^/]+/[^/]+)/archive/refs/heads/(master|main)\.zip$", url)
    if m:
        base, branch = m.group(1), m.group(2)
        yield f"{base}/archive/refs/heads/{'main' if branch == 'master' else 'master'}.zip"


def _ext_for(url, ct):
    p = urlparse(url).path.lower()
    for ext in (".pdf", ".html", ".htm", ".txt", ".zip"):
        if p.endswith(ext):
            return ext
    if "pdf" in (ct or ""):
        return ".pdf"
    if "html" in (ct or ""):
        return ".html"
    if "zip" in (ct or ""):
        return ".zip"
    if "plain" in (ct or ""):
        return ".txt"
    return ".bin"


def _headers_for(url: str) -> dict:
    hdrs = dict(DEFAULT_HEADERS)
    parsed = urlparse(url)
    if parsed.netloc:
        hdrs["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
    return hdrs


def download_one(url, subdir, idx, opener, retries=DEFAULT_RETRIES, retry_delay=DEFAULT_RETRY_DELAY):
    target_dir = OUTDIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    last_err = ""
    max_retries = max(0, int(retries))
    delay = max(0.0, float(retry_delay))

    for cand in _candidates(url):
        for attempt in range(max_retries + 1):
            try:
                req = urllib.request.Request(cand, headers=_headers_for(cand))
                with opener.open(req, timeout=TIMEOUT) as resp:
                    data = resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    # GitHub 404 页面试探：如果分支不存在，跳到下一个候选
                    if "html" in ct and b"GitHub" in data[:1500] and "archive/refs/heads" in cand:
                        last_err = "GitHub branch not found (HTML 404)"
                        break
                    ext = _ext_for(cand, ct)
                    digest = hashlib.sha256(cand.encode()).hexdigest()[:10]
                    fname = f"{idx:03d}_{digest}{ext}"
                    (target_dir / fname).write_bytes(data)
                    return "OK", len(data), cand, str(target_dir / fname), ""
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                if attempt < max_retries:
                    if delay > 0:
                        time.sleep(delay)
                    continue
                break
    return "ERR", 0, url, "", last_err


def parse_args(argv):
    nozip = False
    insecure = False
    cli_proxy = None
    single_url = None
    subdir = DEFAULT_CAT
    retries = DEFAULT_RETRIES
    retry_delay = DEFAULT_RETRY_DELAY
    listfile = Path("urls.txt")
    positional = []

    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--nozip":
            nozip = True
        elif arg == "--insecure":
            insecure = True
        elif arg == "--proxy" and i + 1 < len(argv):
            cli_proxy = argv[i + 1]
            i += 1
        elif arg.startswith("--proxy="):
            cli_proxy = arg.split("=", 1)[1]
        elif arg == "--url" and i + 1 < len(argv):
            single_url = _clean_url(argv[i + 1])
            i += 1
        elif arg.startswith("--url="):
            single_url = _clean_url(arg.split("=", 1)[1])
        elif arg == "--subdir" and i + 1 < len(argv):
            subdir = argv[i + 1].strip().strip('"')
            i += 1
        elif arg.startswith("--subdir="):
            subdir = arg.split("=", 1)[1].strip().strip('"')
        elif arg == "--retries" and i + 1 < len(argv):
            retries = int(argv[i + 1])
            i += 1
        elif arg.startswith("--retries="):
            retries = int(arg.split("=", 1)[1])
        elif arg == "--retry-delay" and i + 1 < len(argv):
            retry_delay = float(argv[i + 1])
            i += 1
        elif arg.startswith("--retry-delay="):
            retry_delay = float(arg.split("=", 1)[1])
        elif not arg.startswith("--"):
            positional.append(arg)
        i += 1

    if positional:
        listfile = Path(positional[0])
    return nozip, insecure, cli_proxy, single_url, subdir, retries, retry_delay, listfile


def main():
    nozip, insecure, cli_proxy, single_url, subdir, retries, retry_delay, listfile = parse_args(sys.argv)
    opener, active_proxies = build_opener(cli_proxy, insecure=insecure)

    if active_proxies:
        print(f"[*] 使用代理: {active_proxies}")
    else:
        print("[*] 未检测到代理环境变量（HTTP_PROXY / HTTPS_PROXY / ALL_PROXY），直连下载。")

    if single_url:
        items = [(single_url, subdir)]
    elif listfile.exists():
        raw = listfile.read_text(encoding="utf-8").splitlines()
        items = parse_listing(raw)
    else:
        print(f"[!] {listfile} 不存在，使用内置清单。")
        items = parse_listing(DEFAULT_URLS)

    OUTDIR.mkdir(exist_ok=True)
    status_path = OUTDIR / "_status.tsv"

    rows = []
    with status_path.open("w", encoding="utf-8") as sts:
        sts.write("status\turl\tbytes\tfile\terror\n")
        for idx, (url, target_subdir) in enumerate(items, 1):
            status, size, final_url, fpath, err = download_one(
                url, target_subdir, idx, opener, retries=retries, retry_delay=retry_delay
            )
            clean_err = err.replace("\t", " ").replace("\n", " ")
            sts.write(f"{status}\t{final_url}\t{size}\t{fpath}\t{clean_err}\n")
            rows.append((status, url, target_subdir))
            if status == "OK":
                print(f"[{idx:03d}] [{target_subdir}] {status} {url}")
            else:
                print(f"[{idx:03d}] [{target_subdir}] {status} {url} ({clean_err})")

    ok = sum(1 for r in rows if r[0] == "OK")
    print(f"\n完成: OK={ok} / FAIL={len(rows)-ok}")
    print(f"状态文件: {status_path}")

    if not nozip:
        with zipfile.ZipFile(ZIPNAME, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(OUTDIR.rglob("*")):
                if p.is_file() and p.name != "_status.tsv":
                    zf.write(p, p.relative_to(OUTDIR))
        print(f"已打包: {ZIPNAME} ({os.path.getsize(ZIPNAME)} bytes)")


if __name__ == "__main__":
    main()
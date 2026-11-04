"""1단계: 기사 수집 — 구글 뉴스 검색 피드, 매체 직접 RSS, 네이버 뉴스 API(선택)."""
from __future__ import annotations

import hashlib
import html
import os
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

UA = "Mozilla/5.0 (compatible; EduIssueBrief/1.0; +https://github.com)"
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(TAG_RE.sub(" ", text))
    return SPACE_RE.sub(" ", text).strip()


def norm_title(title: str) -> str:
    """중복 판정용: 기호·공백 제거, 소문자."""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", title)
    t = re.sub(r"[^0-9a-zA-Z가-힣]", "", t).lower()
    return t


class OutletBook:
    """config의 outlets 사전으로 매체명·도메인 → 성향·유형을 찾는다."""

    def __init__(self, outlets: list[dict]):
        self.by_name = {}
        self.by_domain = {}
        for o in outlets:
            self.by_name[self._key(o["name"])] = o
            for d in o.get("domains", []):
                self.by_domain[d.lower()] = o

    @staticmethod
    def _key(name: str) -> str:
        return re.sub(r"[^0-9a-z가-힣]", "", name.lower())

    def lookup(self, name: str = "", url: str = "") -> dict | None:
        if name:
            k = self._key(name)
            if k in self.by_name:
                return self.by_name[k]
            for key, o in self.by_name.items():  # "조선일보 사회" 같은 변형
                if key and (key in k or k in key) and min(len(k), len(key)) >= 3:
                    return o
        if url:
            host = urlparse(url).netloc.lower()
            for d, o in self.by_domain.items():
                if host == d or host.endswith("." + d):
                    return o
        return None


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    return None


def _fetch_feed(url: str):
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def _article(title, source, url, published, summary, region, country, meta, via):
    lean = (meta or {}).get("lean", "미분류")
    otype = (meta or {}).get("type", "언론")
    aid = hashlib.md5((norm_title(title) + source).encode()).hexdigest()[:10]
    return {
        "id": aid,
        "title": title,
        "source": source,
        "url": url,
        "published": published.isoformat() if published else None,
        "snippet": summary[:400],
        "region": region,
        "country": country,
        "lean": lean,
        "type": otype,
        "via": via,
    }


def collect_google_news(cfg: dict, book: OutletBook, since: datetime, failures: list, until: datetime | None = None) -> list[dict]:
    gn = cfg["google_news"]
    limit = gn.get("per_query_limit", 25)
    jobs = []
    d = gn["domestic"]
    for q in d["queries"]:
        jobs.append(("domestic", "한국", q, d["hl"], d["gl"], d["ceid"]))
    for ed in gn["global"]["editions"]:
        for q in gn["global"]["queries"]:
            jobs.append(("global", ed["country"], q, ed["hl"], ed["gl"], ed["ceid"]))

    out = []
    for region, country, q, hl, gl, ceid in jobs:
        url = (
            f"https://news.google.com/rss/search?q={quote_plus(q + ' when:2d')}"
            f"&hl={hl}&gl={gl}&ceid={ceid}"
        )
        try:
            feed = _fetch_feed(url)
        except Exception as e:  # noqa: BLE001
            failures.append({"source": f"구글 뉴스 '{q}' ({country})", "error": str(e)[:120]})
            continue
        kept = 0
        for entry in feed.entries:
            if kept >= limit:
                break
            pub = _published(entry)
            if pub and (pub < since or (until and pub > until)):
                continue
            kept += 1
            source = clean(entry.get("source", {}).get("title", ""))
            title = clean(entry.get("title", ""))
            if source and title.endswith(" - " + source):
                title = title[: -len(" - " + source)]
            elif " - " in title and not source:
                title, source = title.rsplit(" - ", 1)
            meta = book.lookup(source, entry.get("source", {}).get("href", ""))
            name = meta["name"] if meta else source or "알 수 없음"
            out.append(_article(title, name, entry.get("link", ""), pub, "", region, country, meta, "google"))
        time.sleep(0.4)  # 과도한 요청 방지
    return out


def collect_rss(cfg: dict, book: OutletBook, since: datetime, failures: list, until: datetime | None = None) -> list[dict]:
    out = []
    for src in cfg.get("rss", []):
        try:
            feed = _fetch_feed(src["url"])
            if not feed.entries:
                raise ValueError("기사 0건(주소 변경 가능성)")
        except Exception as e:  # noqa: BLE001
            failures.append({"source": src["name"], "error": str(e)[:120]})
            continue
        meta = {"lean": src.get("lean", "미분류"), "type": src.get("type", "언론")}
        country = src.get("country", "한국" if src["region"] == "domestic" else "해외")
        kept = 0
        for entry in feed.entries:
            if kept >= 40:
                break
            pub = _published(entry)
            if pub and (pub < since or (until and pub > until)):
                continue
            kept += 1
            summary = clean(entry.get("summary", ""))
            out.append(
                _article(clean(entry.get("title", "")), src["name"], entry.get("link", ""),
                         pub, summary, src["region"], country, meta, "rss")
            )
    return out


def collect_naver(cfg: dict, book: OutletBook, since: datetime, failures: list) -> list[dict]:
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        return []
    nv = cfg.get("naver", {})
    out = []
    for q in nv.get("queries", []):
        try:
            r = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                params={"query": q, "display": nv.get("per_query_limit", 30), "sort": "date"},
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret},
                timeout=15,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
        except Exception as e:  # noqa: BLE001
            failures.append({"source": f"네이버 뉴스 '{q}'", "error": str(e)[:120]})
            continue
        for it in items:
            try:
                pub = parsedate_to_datetime(it.get("pubDate"))
            except Exception:  # noqa: BLE001
                pub = None
            if pub and pub < since:
                continue
            link = it.get("originallink") or it.get("link", "")
            meta = book.lookup(url=link)
            name = meta["name"] if meta else urlparse(link).netloc.replace("www.", "")
            out.append(_article(clean(it.get("title")), name, link, pub, clean(it.get("description")),
                                "domestic", "한국", meta, "naver"))
    return out


def dedupe(articles: list[dict], exclude: list[str]) -> list[dict]:
    seen = {}
    ex = [k.lower() for k in exclude]
    for a in articles:
        if not a["title"] or any(k in a["title"].lower() for k in ex):
            continue
        key = (norm_title(a["title"])[:40], a["source"])
        if key in seen:
            # 원문 링크·요약이 있는 쪽(rss·naver)을 남김
            if seen[key]["via"] == "google" and a["via"] != "google":
                seen[key] = a
            continue
        seen[key] = a
    # 같은 제목을 여러 매체가 똑같이 받아 쓴 경우는 매체 정보만 남기고 유지(확산도 계산에 필요)
    return list(seen.values())


def balance_cap(articles: list[dict], cap: int) -> list[dict]:
    """한 매체가 기사 목록을 독차지하지 않도록 매체별로 돌아가며 뽑는다."""
    if len(articles) <= cap:
        return articles
    by_src: dict[str, list] = {}
    for a in sorted(articles, key=lambda x: x["published"] or "", reverse=True):
        by_src.setdefault(a["source"], []).append(a)
    out, i = [], 0
    while len(out) < cap:
        added = False
        for lst in by_src.values():
            if i < len(lst):
                out.append(lst[i])
                added = True
                if len(out) >= cap:
                    break
        if not added:
            break
        i += 1
    return out


def collect_all(cfg: dict, until: datetime | None = None) -> tuple[list[dict], list[dict]]:
    """until을 주면 그 시각 이전 기사만 남긴다(지난 시각의 브리핑 재현용)."""
    book = OutletBook(cfg.get("outlets", []))
    end = until or datetime.now(timezone.utc)
    since = end - timedelta(hours=cfg.get("window_hours", 30))
    failures: list[dict] = []
    arts = []
    arts += collect_rss(cfg, book, since, failures, until)
    arts += collect_naver(cfg, book, since, failures)
    arts += collect_google_news(cfg, book, since, failures, until)
    if until:
        end_iso = until.astimezone(timezone.utc)
        arts = [a for a in arts if a["published"] and datetime.fromisoformat(a["published"]) <= end_iso]
    arts = dedupe(arts, cfg.get("exclude_keywords", []))
    cap = cfg["diversity"].get("max_articles_per_region", 220)
    dom = balance_cap([a for a in arts if a["region"] == "domestic"], cap)
    glo = balance_cap([a for a in arts if a["region"] == "global"], cap)
    return dom + glo, failures

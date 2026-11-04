"""매일 실행되는 본 프로그램.

    python -m brief.run              # 실제 수집·분석
    python -m brief.run --fixture tests/sample_articles.json   # 저장된 기사로 시험 실행
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import llm
from .collect import collect_all
from .scoring import score_cluster, select

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
KST = timezone(timedelta(hours=9))


def load_cfg() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_recent(today: str, days: int = 3) -> tuple[dict[str, list], dict[str, int]]:
    """최근 며칠의 사안 목록(지역별)과 key별 연속 일수."""
    recent = {"domestic": [], "global": []}
    streaks: dict[str, int] = {}
    d0 = datetime.strptime(today, "%Y-%m-%d")
    for back in range(1, days + 1):
        p = DATA / f"{(d0 - timedelta(days=back)).strftime('%Y-%m-%d')}.json"
        if not p.exists():
            continue
        try:
            day = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for t in day.get("topics", []):
            recent.setdefault(t["region"], []).append({"key": t["key"], "label": t["label"]})
            streaks[t["key"]] = t.get("streak_days", 1)
    for r in recent:
        recent[r] = recent[r][:60]
    return recent, streaks


def fetch_body(url: str) -> str:
    if not url or "news.google.com" in url:
        return ""
    try:
        import trafilatura
        raw = trafilatura.fetch_url(url)
        text = trafilatura.extract(raw or "", include_comments=False, include_tables=False) or ""
        return text[:1200]
    except Exception:  # noqa: BLE001
        return ""


def build_materials(c: dict, arts: dict, with_body: bool) -> str:
    members = sorted((arts[i] for i in c["article_ids"]),
                     key=lambda a: (a["via"] == "google", a["source"]))
    lines, bodies = [], 0
    for a in members[:8]:
        snip = f" — {a['snippet'][:200]}" if a["snippet"] else ""
        lines.append(f"- [{a['source']} | {a['lean']} | {a['country']}] {a['title']}{snip}")
    if with_body:
        for a in members:
            if bodies >= 2:
                break
            body = fetch_body(a["url"])
            if body:
                lines.append(f"[본문 발췌: {a['source']}]\n{body}")
                bodies += 1
    # 요지·본문이 하나도 없으면 제목만으로 요약한 것이므로 화면에 표시
    c["title_only"] = bodies == 0 and not any(a["snippet"] for a in members)
    return "\n".join(lines)


def issue_json(c: dict, arts: dict, brief: dict) -> dict:
    members = [arts[i] for i in c["article_ids"]]
    seen, sources = set(), []
    for a in sorted(members, key=lambda a: (a["via"] == "google", a["published"] or ""), reverse=False):
        if a["source"] in seen:
            continue
        seen.add(a["source"])
        sources.append({k: a[k] for k in ("source", "lean", "type", "country", "url", "title")})
    return {
        "key": c["key"], "region": c["region"], "field": c["field"],
        "title": brief.get("title") or c["label"], "summary": brief.get("summary", []),
        "implication": brief.get("implication", ""), "perspective": brief.get("perspective"),
        "tags": brief.get("tags", []), "score": c["score"], "score_parts": c["score_parts"],
        "streak_days": c["streak_days"], "source_count": c["source_count"], "leans": c["leans"],
        "official": bool(c.get("official_action")), "title_only": bool(c.get("title_only")),
        "sources": sources[:8],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="수집 대신 사용할 기사 JSON 파일")
    ap.add_argument("--date", help="브리핑 날짜(YYYY-MM-DD), 기본값은 오늘(한국 시간)")
    ap.add_argument("--no-body", action="store_true", help="원문 본문 가져오기 생략")
    ap.add_argument("--until", default=os.getenv("BRIEF_UNTIL") or None,
                    help="기준 시각(한국 시간, 예: 2026-11-04T05:50). 그 시각에 받았을 브리핑을 재현")
    args = ap.parse_args()

    cfg = load_cfg()
    until = None
    if args.until:
        until = datetime.fromisoformat(args.until.strip())
        if until.tzinfo is None:
            until = until.replace(tzinfo=KST)
    now = until or datetime.now(KST)
    today = args.date or now.strftime("%Y-%m-%d")
    DATA.mkdir(parents=True, exist_ok=True)

    # 1) 수집
    if args.fixture:
        articles = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        failures = []
    else:
        articles, failures = collect_all(cfg, until)
    print(f"[1] 수집 {len(articles)}건, 실패 출처 {len(failures)}곳")

    arts = {}
    for i, a in enumerate(articles):
        a["_sid"] = f"{'d' if a['region'] == 'domestic' else 'g'}{i}"
        arts[a["_sid"]] = a

    # 2) 사안 묶기
    recent, prev_streaks = load_recent(today)
    clusters = []
    for region in ("domestic", "global"):
        reg_arts = [a for a in articles if a["region"] == region]
        for j, c in enumerate(llm.group_articles(cfg, region, reg_arts, recent.get(region, []))):
            c["region"] = region
            c["key"] = f"{today}-{region[0]}{j:02d}"
            clusters.append(c)
    print(f"[2] 사안 {len(clusters)}개")

    # 3) 이슈도 점수·선별
    for c in clusters:
        score_cluster(c, arts, cfg, prev_streaks)
    top, sections = select(clusters, arts, cfg)
    chosen = top + [c for lst in sections.values() for c in lst]
    print(f"[3] 핵심 {len(top)}개, 분야별 {len(chosen) - len(top)}개 선별")

    # 4) 요약
    items = [{"key": c["key"], "label": c["label"],
              "materials": build_materials(c, arts, with_body=not args.no_body and not args.fixture)}
             for c in chosen]
    overview, briefs = llm.summarize(cfg, items)
    print(f"[4] 요약 {len(briefs)}개")

    # 5) 저장
    used = [arts[i] for c in chosen for i in c["article_ids"]]
    srcs = {a["source"]: a for a in articles}
    day = {
        "date": today,
        "generated_at": now.isoformat(timespec="minutes"),
        "replayed_at": datetime.now(KST).isoformat(timespec="minutes") if until else None,
        "mode": ("claude" if not llm.ERRORS else "partial") if os.getenv("ANTHROPIC_API_KEY") and not args.fixture else "fallback",
        "site": cfg.get("site", {}),
        "overview": overview,
        "stats": {
            "articles": len(articles),
            "sources": len(srcs),
            "issues": len(clusters),
            "domestic": sum(a["region"] == "domestic" for a in articles),
            "global": sum(a["region"] == "global" for a in articles),
            "by_lean": dict(Counter(a["lean"] for a in srcs.values())),
            "by_type": dict(Counter(a["type"] for a in srcs.values())),
            "by_country": dict(Counter(a["country"] for a in used)),
        },
        "failures": failures,
        "llm_errors": llm.ERRORS,
        "top": [issue_json(c, arts, briefs.get(c["key"], {})) for c in top],
        "sections": [{"field": f, "issues": [issue_json(c, arts, briefs.get(c["key"], {})) for c in lst]}
                     for f, lst in sections.items() if lst],
        "topics": [{"key": c["key"], "label": c["label"], "region": c["region"], "streak_days": c["streak_days"]}
                   for c in sorted(clusters, key=lambda c: c["score"], reverse=True)[:80]],
    }
    (DATA / f"{today}.json").write_text(json.dumps(day, ensure_ascii=False, indent=1), encoding="utf-8")

    idx_path = DATA / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {"dates": []}
    dates = sorted(set(idx.get("dates", [])) | {today}, reverse=True)
    idx_path.write_text(json.dumps({"latest": dates[0], "dates": dates}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"[5] 저장 완료: docs/data/{today}.json")


if __name__ == "__main__":
    main()

"""3단계: 이슈도 점수 산정과 다양성 규칙에 따른 선별."""
from __future__ import annotations

import math

LEANS = ("진보", "중도", "보수")


def score_cluster(c: dict, arts: dict, cfg: dict, prev_streaks: dict) -> dict:
    w = cfg["scoring"]
    members = [arts[i] for i in c["article_ids"]]
    sources = {a["source"] for a in members}
    leans = {a["lean"] for a in members if a["lean"] in LEANS}

    n = len(sources)
    full = max(2, w.get("spread_full_at", 8))
    spread = w["spread"] * min(1.0, math.log2(1 + n) / math.log2(1 + full))
    balance = w["balance"] * (max(0, len(leans) - 1) / 2)          # 논조 2종=절반, 3종=만점
    streak_days = prev_streaks.get(c.get("continues") or "", 0) + 1
    streak = min(w["streak"], 5 * (streak_days - 1))
    official = w["official"] if c.get("official_action") else 0
    relevance = w["relevance"] * (int(c.get("school_relevance", 2)) / 3)

    parts = {"확산도": spread, "논조 폭": balance, "지속성": streak, "공식성": official, "현장 관련성": relevance}
    c["score"] = round(sum(parts.values()), 1)
    c["score_parts"] = {k: round(v, 1) for k, v in parts.items()}
    c["streak_days"] = streak_days
    c["source_count"] = n
    c["leans"] = sorted(leans, key=LEANS.index)
    return c


def select(clusters: list[dict], arts: dict, cfg: dict) -> tuple[list[dict], dict[str, list[dict]]]:
    """다양성 규칙을 지키며 핵심 이슈와 분야별 이슈를 고른다."""
    d = cfg["diversity"]
    ranked = sorted(clusters, key=lambda c: c["score"], reverse=True)

    # 한 매체 단독 보도 사안은 매체당 상한
    single_count: dict[str, int] = {}
    pool = []
    for c in ranked:
        if c["source_count"] == 1:
            src = arts[c["article_ids"][0]]["source"]
            if single_count.get(src, 0) >= d["single_source_cap"]:
                continue
            single_count[src] = single_count.get(src, 0) + 1
        pool.append(c)

    # 핵심 이슈: 해외 최소 개수 보장
    k, gmin = d["top_issues"], d["top_min_global"]
    glob = [c for c in pool if c["region"] == "global"][:gmin]
    rest = [c for c in pool if c not in glob]
    top = sorted(glob + rest[: k - len(glob)], key=lambda c: c["score"], reverse=True)

    # 분야별: 각 분야 상한, 전체 상한, 해외 비율 하한
    remaining = [c for c in pool if c not in top]
    max_total = d["max_total"] - len(top)
    need_global = max(0, math.ceil(d["global_share_min"] * d["max_total"]) - sum(c["region"] == "global" for c in top))
    chosen: list[dict] = []
    per_field: dict[str, int] = {}

    def can_take(c):
        return per_field.get(c["field"], 0) < d["per_field"] and len(chosen) < max_total

    global_in_field: dict[str, int] = {}
    for c in [x for x in remaining if x["region"] == "global"]:   # 해외 몫 먼저 확보
        if need_global <= 0:
            break
        # 분야마다 국내 이슈 자리를 최소 1개 남겨 둠
        if global_in_field.get(c["field"], 0) >= max(1, d["per_field"] - 1):
            continue
        if can_take(c):
            global_in_field[c["field"]] = global_in_field.get(c["field"], 0) + 1
            chosen.append(c); per_field[c["field"]] = per_field.get(c["field"], 0) + 1; need_global -= 1
    for c in remaining:                                             # 나머지는 점수 순
        if c not in chosen and can_take(c):
            chosen.append(c); per_field[c["field"]] = per_field.get(c["field"], 0) + 1

    sections: dict[str, list[dict]] = {f["name"]: [] for f in cfg["fields"]}
    for c in sorted(chosen, key=lambda c: c["score"], reverse=True):
        sections.setdefault(c["field"], []).append(c)
    return top, sections

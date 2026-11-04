"""Claude 호출 — 사안 묶기(2단계)와 요약(4단계).

API 열쇠가 없거나 호출이 실패하면 간이 규칙(제목 유사도)으로 대신 처리해
브리핑이 끊기지 않게 한다.
"""
from __future__ import annotations

import json
import os
import re
import time

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

# 새로 만든 API 조직은 분당 입력 토큰 한도가 낮아(약 3만) 한꺼번에 보내면 거절된다.
# 최근 1분 동안 보낸 양을 어림해 한도에 가까우면 잠시 기다렸다 보낸다.
ITPM_BUDGET = int(os.getenv("BRIEF_ITPM_BUDGET", "24000"))
_sent: list[tuple[float, int]] = []
ERRORS: list[str] = []   # 화면 하단·자료 파일에 남겨 원인 파악에 사용


def _pace(est_tokens: int) -> None:
    while True:
        now = time.time()
        _sent[:] = [(t, n) for t, n in _sent if now - t < 62]
        used = sum(n for _, n in _sent)
        if not _sent or used + est_tokens <= ITPM_BUDGET:
            break
        wait = 62 - (now - _sent[0][0])
        print(f"[대기] 분당 사용량 조절 {wait:.0f}초")
        time.sleep(max(1, wait))
    _sent.append((time.time(), est_tokens))


def _estimate(*texts: str) -> int:
    chars = sum(len(t) for t in texts)
    return int(chars / 1.6) + 800   # 한글·영문 섞인 글 기준 대략값(넉넉하게)


def _client():
    if anthropic is None or not os.getenv("ANTHROPIC_API_KEY"):
        return None
    return anthropic.Anthropic(max_retries=2, timeout=300)


def _json_from_text(text: str) -> dict | None:
    """도구 대신 글로 답했을 때 본문 속 JSON을 꺼낸다."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:j + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def _call_tool(client, model: str, system: str, user: str, tool: dict, max_tokens: int) -> dict:
    # 일부 모델은 도구 강제 지정(tool_choice: tool)을 받지 않으므로 자동 선택으로 두고 지시문으로 요청한다.
    user = user + f"\n\n결과는 반드시 `{tool['name']}` 도구를 한 번 호출해 보고하세요."
    _pace(_estimate(system, user, json.dumps(tool, ensure_ascii=False)))
    last = None
    for attempt in range(4):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "auto"},
                messages=[{"role": "user", "content": user}],
            )
            texts = []
            for block in msg.content:
                if block.type == "tool_use" and block.name == tool["name"]:
                    return block.input
                if block.type == "text":
                    texts.append(block.text)
            parsed = _json_from_text("\n".join(texts))
            if parsed:
                return parsed
            raise RuntimeError(f"도구 응답 없음(stop_reason={msg.stop_reason})")
        except Exception as e:  # noqa: BLE001
            last = e
            status = getattr(e, "status_code", None)
            if status in (429, 529) or (status and status >= 500):
                wait = 65
                try:
                    wait = int(e.response.headers.get("retry-after", 65)) + 2
                except Exception:  # noqa: BLE001
                    pass
                print(f"[재시도 {attempt + 1}/3] {type(e).__name__} {status} → {wait}초 후 다시 시도")
                time.sleep(wait)
                continue
            raise
    raise last


# ──────────────────────────────────────────────────────────────
#  2단계: 사안 묶기
# ──────────────────────────────────────────────────────────────
GROUP_TOOL = {
    "name": "report_clusters",
    "description": "기사 목록을 같은 사안끼리 묶은 결과를 보고한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "description": "사안 이름(한국어, 명사형, 25자 이내)"},
                        "article_ids": {"type": "array", "items": {"type": "string"}},
                        "field": {"type": "string", "description": "주어진 분야 이름 중 하나"},
                        "official_action": {"type": "boolean", "description": "정부 발표·법안·판결·공식 통계 등 제도적 사건 여부"},
                        "school_relevance": {"type": "integer", "minimum": 1, "maximum": 3,
                                             "description": "3=초중등 학교 현장에 직접 영향, 2=간접 영향, 1=배경 지식 수준"},
                        "continues": {"type": ["string", "null"], "description": "최근 사안 목록 중 같은 사안의 key, 없으면 null"},
                    },
                    "required": ["label", "article_ids", "field", "official_action", "school_relevance", "continues"],
                },
            }
        },
        "required": ["clusters"],
    },
}

GROUP_SYSTEM = """당신은 교육 전문 뉴스 데스크 편집자입니다.
주어진 기사 목록을 '같은 사건·같은 정책·같은 발표'를 다룬 것끼리 묶습니다.
규칙:
- 교육·아동·청소년·학교와 연결되는 사회 이슈만 남기고, 무관한 기사(스포츠, 연예, 주식, 단순 사건사고, 광고성 기사)는 어느 묶음에도 넣지 않습니다.
- 같은 정부 발표·정책·보고서를 지역별·기관별로 다룬 기사(예: 'A시 선정', 'B군 선정')는 하나의 사안으로 묶습니다.
- 같은 기업·기관의 같은 발표를 다룬 해외 기사도 매체가 달라도 하나로 묶습니다.
- 같은 주제(예: '교권')라도 서로 다른 사건이면 따로 묶습니다.
- 지자체·기관의 단순 홍보성 행사 소식은 학교 현장 관련성이 낮으면 school_relevance를 1로 둡니다.
- 기사 하나만 있는 사안도 의미가 있으면 1건짜리 묶음으로 남깁니다.
- field는 반드시 제시된 분야 이름 중 하나를 그대로 씁니다.
- continues는 '최근 사안 목록'에 같은 사안이 있을 때만 그 key를 적습니다.
- label은 지역명보다 정책·사건 이름이 드러나는 한국어 명사형으로 씁니다(해외 기사도 한국어로)."""


def group_articles(cfg: dict, region: str, articles: list[dict], recent_topics: list[dict]) -> list[dict]:
    if not articles:
        return []
    client = _client()
    if client is None:
        return fallback_group(articles, cfg)

    fields_txt = "\n".join(f"- {f['name']}: {f['hint']}" for f in cfg["fields"])
    lines = [f"{a['_sid']} | {a['source']} | {a['title']}" + (f" | {a['snippet'][:90]}" if a["snippet"] else "")
             for a in articles]
    recent_txt = "\n".join(f"- {t['key']}: {t['label']}" for t in recent_topics) or "(없음)"
    user = (
        f"[지역] {'국내' if region == 'domestic' else '해외'}\n\n[분야]\n{fields_txt}\n\n"
        f"[최근 3일 사안 목록]\n{recent_txt}\n\n[기사 목록: id | 매체 | 제목 | 요지]\n" + "\n".join(lines)
    )
    try:
        result = _call_tool(client, cfg["model"], GROUP_SYSTEM, user, GROUP_TOOL, 16000)
        clusters = result.get("clusters", [])
        valid = {a["_sid"] for a in articles}
        names = {f["name"] for f in cfg["fields"]}
        out = []
        for c in clusters:
            ids = [i for i in c.get("article_ids", []) if i in valid]
            if not ids:
                continue
            c["article_ids"] = ids
            if c.get("field") not in names:
                c["field"] = cfg["fields"][0]["name"]
            out.append(c)
        return out
    except Exception as e:  # noqa: BLE001
        msg = f"사안 묶기({region}) 실패: {type(e).__name__}: {str(e)[:300]}"
        print("[경고]", msg)
        ERRORS.append(msg)
        return fallback_group(articles, cfg)


STOP = {"the", "and", "for", "of", "in", "on", "to", "a", "an", "with", "is", "are", "as", "by", "at", "from"}


def _bigrams(s: str) -> set:
    """한글은 2글자 조각, 영문은 단어 단위로 비교한다."""
    s = s.lower()
    words = {w for w in re.findall(r"[a-z]{3,}", s) if w not in STOP}
    ko = re.sub(r"[^가-힣0-9]", "", s)
    return words | {ko[i:i + 2] for i in range(len(ko) - 1)}


def fallback_group(articles: list[dict], cfg: dict) -> list[dict]:
    """제목 2글자 조각 유사도로 묶는 간이 규칙(열쇠 없을 때·실패 시)."""
    clusters: list[dict] = []
    grams = {a["_sid"]: _bigrams(a["title"]) for a in articles}
    for a in articles:
        g = grams[a["_sid"]]
        best, best_sim = None, 0.0
        for c in clusters:
            inter = len(g & c["_g"])
            sim = inter / max(1, min(len(g), len(c["_g"])))
            if sim > best_sim:
                best, best_sim = c, sim
        if best and best_sim >= 0.45:
            best["article_ids"].append(a["_sid"])
            best["_g"] |= g
        else:
            clusters.append({"label": a["title"][:25], "article_ids": [a["_sid"]], "_g": set(g),
                             "field": _guess_field(a["title"], cfg), "official_action": False,
                             "school_relevance": 2, "continues": None})
    for c in clusters:
        c.pop("_g", None)
    return clusters


def _guess_field(title: str, cfg: dict) -> str:
    t = title.lower()
    for f in cfg["fields"]:
        for kw in re.split(r"[,·\s]+", f["hint"]):
            if len(kw) >= 2 and kw.lower() in t:
                return f["name"]
    return cfg["fields"][0]["name"]


# ──────────────────────────────────────────────────────────────
#  4단계: 요약
# ──────────────────────────────────────────────────────────────
SUM_TOOL = {
    "name": "report_briefs",
    "description": "선별된 사안의 요약을 보고한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overview": {"type": "array", "items": {"type": "string"},
                         "description": "오늘 전체 흐름 2~3줄(개조식, 각 60자 이내)"},
            "briefs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "title": {"type": "string", "description": "명사형 제목, 30자 이내"},
                        "summary": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3,
                                    "description": "핵심 요약 3줄, 개조식, 각 60자 이내"},
                        "implication": {"type": "string", "description": "학교 현장 시사점 1줄, 70자 이내"},
                        "perspective": {"type": ["string", "null"],
                                        "description": "매체·논조별 관점 차이가 자료에서 드러날 때만 1줄, 아니면 null"},
                        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    },
                    "required": ["key", "title", "summary", "implication", "perspective", "tags"],
                },
            },
        },
        "required": ["overview", "briefs"],
    },
}

SUM_SYSTEM = """당신은 초등학교 교사를 위한 교육·사회 브리핑 편집자입니다.
각 사안의 [자료]만 근거로 요약합니다. 자료에 없는 사실·수치·인물을 덧붙이지 않습니다.
작성 규칙:
- 개조식 문체로 씁니다(문장 끝을 '~함', '~임', '~예정', '~발표' 같은 명사형으로 맺음).
- 해외 기사도 모두 자연스러운 한국어로 씁니다. 번역투를 피합니다.
- 기사 문장을 그대로 옮기지 말고 자신의 말로 다시 씁니다.
- 비유적·구어적 표현 대신 교육 분야에서 통용되는 용어를 씁니다.
- 제목은 평범한 명사구로 씁니다(과장·감탄 금지).
- 시사점은 초등 교사·학교 운영 관점에서 무엇을 살펴야 하는지 1줄로 씁니다.
- perspective는 서로 다른 성향 매체의 제목·요지에서 강조점 차이가 실제로 보일 때만 씁니다. 매체 성향을 평가하지 말고 '어느 쪽은 무엇을, 다른 쪽은 무엇을 강조'처럼 사실만 적습니다.
- 자료가 제목뿐이면 확인된 사실만 1~2줄로 짧게 쓰고 추정하지 않습니다.
- '자료가 제목뿐이라', '확인되지 않음', '원문 확인 필요' 같은 자료 상태 설명은 요약·시사점에 쓰지 않습니다(화면에 따로 표시됨).
- implication은 비워 두지 않습니다."""


def summarize(cfg: dict, items: list[dict]) -> tuple[list[str], dict]:
    """items: [{key, label, materials:str}] → (overview, {key: brief})"""
    client = _client()
    if client is None or not items:
        return fallback_summarize(items)
    overview, briefs = [], {}
    chunk = 5
    for i in range(0, len(items), chunk):
        part = items[i:i + chunk]
        body = "\n\n".join(f"### key={it['key']} | 사안: {it['label']}\n[자료]\n{it['materials']}" for it in part)
        user = ("다음 사안들을 요약하세요." +
                (" overview에는 오늘 전체 흐름을 쓰세요." if i == 0 else " overview는 빈 배열로 두세요.") +
                "\n\n" + body)
        try:
            res = _call_tool(client, cfg["model"], SUM_SYSTEM, user, SUM_TOOL, 12000)
            if i == 0:
                overview = res.get("overview", [])
            for b in res.get("briefs", []):
                briefs[b["key"]] = b
        except Exception as e:  # noqa: BLE001
            msg = f"요약 {i // chunk + 1}묶음 실패: {type(e).__name__}: {str(e)[:300]}"
            print("[경고]", msg)
            ERRORS.append(msg)
            briefs.update(fallback_summarize(part)[1])
    for it in items:  # 빠진 항목 보충
        if it["key"] not in briefs:
            briefs.update(fallback_summarize([it])[1])
    return overview, briefs


def fallback_summarize(items: list[dict]) -> tuple[list[str], dict]:
    briefs = {}
    for it in items:
        heads = []
        for ln in it["materials"].splitlines():
            if not ln.startswith("- ["):
                continue
            title = ln.split("] ", 1)[-1].split(" — ", 1)[0].strip()   # 매체 표시·요지는 빼고 제목만
            if title and title not in heads:
                heads.append(title)
        heads = heads[:3]
        briefs[it["key"]] = {
            "key": it["key"], "title": it["label"], "summary": heads or [it["label"]],
            "implication": "요약 생성 실패 — 원문 링크에서 내용을 확인하세요.",
            "perspective": None, "tags": [],
        }
    return ["자동 요약을 만들지 못해 기사 제목으로 대신 표시함"], briefs


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)

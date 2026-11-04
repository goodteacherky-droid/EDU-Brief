"""Claude 응답을 흉내 내어 묶기·요약·선별 경로를 점검한다(네트워크 불필요).

    python -m tests.test_pipeline
"""
import types

import yaml

from brief import llm
from brief.collect import OutletBook, dedupe
from brief.run import ROOT
from brief.scoring import score_cluster, select

cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.messages = self

    def create(self, **kw):
        assert kw["tool_choice"]["type"] == "auto"
        p = self.payloads.pop(0)
        if isinstance(p, str):   # 도구 대신 글로 JSON을 준 경우
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=p)], stop_reason="end_turn")
        think = types.SimpleNamespace(type="thinking", thinking="...")
        block = types.SimpleNamespace(type="tool_use", name=kw["tools"][0]["name"], input=p)
        return types.SimpleNamespace(content=[think, block], stop_reason="tool_use")


def test_all():
    # 매체 사전
    book = OutletBook(cfg["outlets"])
    assert book.lookup("조선일보")["lean"] == "보수"
    assert book.lookup(url="https://www.hani.co.kr/arti/1.html")["name"] == "한겨레"
    assert book.lookup("The Guardian")["lean"] == "진보"

    arts = [
        {"_sid": f"d{i}", "id": str(i), "title": t, "source": s, "url": "#", "published": None, "snippet": "",
         "region": "domestic", "country": "한국", "lean": l, "type": "언론", "via": "rss"}
        for i, (t, s, l) in enumerate([("A안 발표", "한겨레", "진보"), ("A안 발표 논란", "조선일보", "보수"),
                                        ("A안 발표", "연합뉴스", "중도"), ("B 조사", "KBS", "중도")])
    ]
    assert len(dedupe(arts + [dict(arts[0])], [])) == 4

    fake = FakeClient([
        {"clusters": [
            {"label": "A안", "article_ids": ["d0", "d1", "d2", "zzz"], "field": "교육정책",
             "official_action": True, "school_relevance": 3, "continues": "2026-11-03-d01"},
            {"label": "B 조사", "article_ids": ["d3"], "field": "없는분야", "official_action": False,
             "school_relevance": 1, "continues": None},
        ]},
        '결과입니다.\n```json\n{"overview": ["흐름 1"], "briefs": [{"key": "k0", "title": "A안 발표", "summary": ["가", "나", "다"], "implication": "시사점", "perspective": null, "tags": ["정책"]}]}\n```',
    ])
    llm._client = lambda: fake
    cl = llm.group_articles(cfg, "domestic", arts, [])
    assert cl[0]["article_ids"] == ["d0", "d1", "d2"], "없는 id는 걸러야 함"
    assert cl[1]["field"] == "교육정책", "없는 분야는 기본 분야로"

    amap = {a["_sid"]: a for a in arts}
    for j, c in enumerate(cl):
        c["region"], c["key"] = "domestic", f"k{j}"
        score_cluster(c, amap, cfg, {"2026-11-03-d01": 2})
    assert cl[0]["streak_days"] == 3 and cl[0]["leans"] == ["진보", "중도", "보수"]
    assert cl[0]["score"] > cl[1]["score"]
    top, sections = select(cl, amap, cfg)
    assert top[0]["key"] == "k0"

    ov, briefs = llm.summarize(cfg, [{"key": "k0", "label": "A안", "materials": "- [한겨레] A안 발표"},
                                     {"key": "k1", "label": "B 조사", "materials": "- [KBS] B 조사"}])
    assert ov == ["흐름 1"] and briefs["k0"]["summary"] == ["가", "나", "다"]
    assert "k1" in briefs, "빠진 항목은 보충해야 함"
    print("모든 점검 통과")


if __name__ == "__main__":
    test_all()

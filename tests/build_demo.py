"""화면 미리보기용 단일 HTML을 만든다(가상 데이터 내장). 실제 운영에는 쓰지 않음.

    python tests/build_demo.py  →  tests/demo_preview.html
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def src(name, lean, country="한국", type_="언론"):
    return {"source": name, "lean": lean, "type": type_, "country": country, "url": "https://example.com", "title": "예시 기사"}


def issue(key, region, field, title, summary, impl, score, parts, streak, leans, sources, persp=None, official=False):
    return {"key": key, "region": region, "field": field, "title": title, "summary": summary, "implication": impl,
            "perspective": persp, "tags": [], "score": score, "score_parts": parts, "streak_days": streak,
            "source_count": len(sources), "leans": leans, "official": official, "sources": sources}


P = lambda a, b, c, d, e: {"확산도": a, "논조 폭": b, "지속성": c, "공식성": d, "현장 관련성": e}

day = {
    "date": "2026-11-04", "generated_at": "2026-11-04T06:34", "mode": "claude",
    "site": {"title": "교육·사회 데일리 브리핑", "subtitle": "국내·해외 교육과 사회 이슈를 매일 아침 정리합니다"},
    "overview": [
        "국내는 초등 방과후 돌봄 운영 개선안 발표가 여러 매체에서 이어지며 사흘째 주요 이슈임",
        "해외는 영국의 학교 내 휴대전화 사용 지침 발표에 교원단체 반응이 엇갈림",
        "청소년 정신건강 조사 결과 공개로 상담 인력 확충 논의가 다시 제기됨",
    ],
    "stats": {"articles": 412, "sources": 57, "issues": 96, "domestic": 228, "global": 184,
              "by_lean": {"진보": 11, "중도": 29, "보수": 12, "해당없음": 5}},
    "failures": [{"source": "예시 RSS", "error": "응답 시간 초과"}],
    "top": [
        issue("t1", "domestic", "교육정책", "초등 방과후 돌봄 운영 개선안 발표",
              ["교육부가 내년도 초등 방과후 돌봄 운영 개선안을 발표함",
               "강사 확보와 학교 업무 분리를 위한 지역 단위 전담 조직 확대가 핵심임",
               "현장에서는 공간 부족과 인력 수급 일정에 대한 우려가 제기됨"],
              "학교별 운영 공간·인력 현황을 미리 점검해 교육청 수요 조사에 대비할 필요가 있음",
              78, P(38.2, 10, 10, 10, 20), 3, ["진보", "중도", "보수"],
              [src("예시일보 A", "진보"), src("예시통신", "중도"), src("예시일보 B", "보수"), src("예시교육신문", "중도", type_="교육전문지"), src("예시방송", "중도")],
              persp="진보 성향 매체는 돌봄 인력 처우를, 보수 성향 매체는 예산 집행 효율을 주로 강조함", official=True),
        issue("t2", "global", "AI·에듀테크", "영국, 학교 내 휴대전화 사용 지침 발표",
              ["영국 교육부가 수업 시간 중 휴대전화 사용을 제한하는 지침을 발표함",
               "보관 방식은 학교 자율로 정하되 점검 결과를 공개하도록 함",
               "교원단체는 취지에 공감하면서도 학교별 관리 부담을 지적함"],
              "학교 휴대전화 관리 규정과 학생 자치 논의 절차를 비교해 볼 참고 사례임",
              64, P(31.5, 10, 5, 10, 13.3), 2, ["진보", "중도", "보수"],
              [src("Sample Times", "보수", "영국"), src("Sample Guardian", "진보", "영국"), src("Sample BBC", "중도", "영국")], official=True),
        issue("t3", "domestic", "사회정서·청소년", "청소년 우울 위험군 조사 결과 공개",
              ["전국 청소년 대상 정신건강 실태조사 결과가 공개됨",
               "우울 위험군 비율이 전년보다 높아졌고 초등 고학년에서도 증가함",
               "학교 상담 인력 배치 기준 개선 요구가 함께 제기됨"],
              "고학년 학급의 사회정서 점검 시기와 상담 연계 절차를 확인할 필요가 있음",
              59, P(27.7, 5, 0, 10, 20), 1, ["중도", "보수"],
              [src("예시방송", "중도"), src("예시일보 B", "보수"), src("예시통신", "중도")]),
    ],
    "sections": [
        {"field": "교육정책", "issues": [
            issue("s1", "domestic", "교육정책", "교원 생활지도 고시 개정 추진",
                  ["교육부가 교원 생활지도 고시 일부 개정을 추진함", "분리 지도 절차와 보호자 연락 기준을 구체화하는 내용임"],
                  "학교 생활규정 개정 시기와 학부모 안내 일정을 함께 검토할 필요가 있음",
                  46, P(20.5, 5, 0, 10, 13.3), 1, ["중도", "보수"], [src("예시일보 B", "보수"), src("예시교육신문", "중도", type_="교육전문지")], official=True),
            issue("s2", "global", "교육정책", "OECD, 교원 수급 보고서 발표",
                  ["OECD가 회원국 교원 수급 현황 보고서를 발표함", "초등 교원 부족보다 지역 간 불균형이 더 큰 과제로 제시됨"],
                  "농산어촌·신도시 학교 간 교원 배치 논의의 국제 비교 자료로 활용 가능함",
                  33, P(13.5, 0, 0, 10, 13.3), 1, [], [src("Sample OECD", "해당없음", "국제", "연구·국제기구")], official=True),
        ]},
        {"field": "학생인권·생활지도", "issues": [
            issue("s3", "domestic", "학생인권·생활지도", "학교폭력 심의 건수 증가",
                  ["지난해 학교폭력 심의 건수가 전년 대비 늘어남", "초등학교 비율이 높아지고 사이버 폭력 유형이 증가함"],
                  "초등 고학년 디지털 시민교육과 관계 회복 프로그램 운영을 점검할 필요가 있음",
                  52, P(20.5, 5, 5, 8, 13.3), 2, ["진보", "중도"], [src("예시통신", "중도"), src("예시일보 A", "진보")]),
        ]},
        {"field": "AI·에듀테크", "issues": [
            issue("s4", "global", "AI·에듀테크", "미국 공립학교 AI 학습 보조 시범 확대",
                  ["미국 여러 주가 공립학교 AI 학습 보조 시범 사업을 확대함", "학습 기록 보호와 교사 검토 절차가 쟁점으로 다뤄짐"],
                  "AI 활용 수업 시 학생 학습 기록 관리 기준을 마련할 때 참고할 수 있음",
                  41, P(20.5, 0, 0, 0, 20), 1, ["중도"], [src("Sample Post", "중도", "미국"), src("Sample EdWeek", "중도", "미국", "교육전문지")]),
        ]},
        {"field": "특수교육·포용", "issues": [
            issue("s5", "domestic", "특수교육·포용", "특수학급 과밀 해소 예산 요구",
                  ["특수학급 과밀 해소를 위한 예산 반영 요구가 제기됨", "신설 학교의 특수학급 설치 기준 보완도 함께 거론됨"],
                  "신설 학교 특수학급 수요 예측과 지원 인력 배치 계획을 점검할 필요가 있음",
                  38, P(13.5, 0, 5, 0, 20), 2, ["진보"], [src("예시일보 A", "진보")]),
        ]},
        {"field": "사회·복지", "issues": [
            issue("s6", "global", "사회·복지", "영국 아동 빈곤율 상승 통계",
                  ["영국 정부 통계에서 아동 빈곤율이 상승한 것으로 나타남", "급식 지원 대상 확대 논의가 이어짐"],
                  "교육복지 대상 학생 지원 방식 비교 자료로 참고 가능함",
                  31, P(13.5, 0, 0, 10, 6.7), 1, ["진보"], [src("Sample Guardian", "진보", "영국")], official=True),
        ]},
    ],
    "topics": [],
}

page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
head = page.split("<!--PAGE-START-->")[1].split("<!--HEAD-END-->")[0]
body = page.split("<!--BODY-START-->")[1].split("<!--PAGE-END-->")[0]
data = {"index": {"latest": day["date"], "dates": [day["date"]]}, "days": {day["date"]: day}}
slot = "<script>window.__BRIEF_DATA__ = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ";</script>"
body = body.replace("<!--DATA-SLOT-->", slot)
out = ROOT / "tests" / "demo_preview.html"
out.write_text(head.strip() + "\n" + body.strip() + "\n", encoding="utf-8")
print(out)

"""시험 실행용 가상 기사 묶음을 만든다(실제 기사 아님)."""
import json
from pathlib import Path

D = [  # (제목, 매체, 성향)
    ("초등 늘봄 프로그램 운영 개선안 발표", "예시일보A", "진보"),
    ("초등 늘봄 프로그램 운영 개선안 발표…강사 확보 과제", "예시일보B", "보수"),
    ("늘봄 프로그램 운영 개선안 발표, 현장 반응 엇갈려", "예시통신", "중도"),
    ("초등 늘봄 프로그램 운영 개선안 학부모 기대", "예시방송", "중도"),
    ("교원 생활지도 고시 개정 추진", "예시일보B", "보수"),
    ("교원 생활지도 고시 개정 추진에 교원단체 입장", "예시교육신문", "중도"),
    ("학교폭력 심의 건수 전년 대비 증가", "예시통신", "중도"),
    ("학교폭력 심의 건수 증가 초등 비율 확대", "예시일보A", "진보"),
    ("AI 활용 수업 연수 확대 계획", "예시교육신문", "중도"),
    ("특수학급 과밀 해소 예산 반영 요구", "예시일보A", "진보"),
    ("청소년 우울 위험군 조사 결과 공개", "예시방송", "중도"),
    ("청소년 우울 위험군 조사 결과 공개 상담 인력 부족", "예시일보B", "보수"),
    ("학령인구 감소로 소규모 학교 통폐합 논의", "예시통신", "중도"),
]
G = [
    ("England schools phone ban guidance published", "Sample Times", "보수", "영국"),
    ("England schools phone ban guidance published, unions react", "Sample Guardian", "진보", "영국"),
    ("Phone ban guidance for England schools explained", "Sample BBC", "중도", "영국"),
    ("US states expand AI tutoring pilots in public schools", "Sample Post", "중도", "미국"),
    ("AI tutoring pilots expand in US public schools", "Sample EdWeek", "중도", "미국"),
    ("OECD report on teacher shortages", "Sample OECD", "해당없음", "미국"),
    ("Singapore updates social emotional learning curriculum", "Sample Straits", "중도", "싱가포르·아시아"),
    ("Child poverty rises in UK", "Sample Guardian", "진보", "영국"),
]
arts = []
for i, (t, s, l) in enumerate(D):
    arts.append({"id": f"k{i}", "title": t, "source": s, "url": "#", "published": "2026-11-04T00:00:00+00:00",
                 "snippet": "", "region": "domestic", "country": "한국", "lean": l, "type": "언론", "via": "rss"})
for i, (t, s, l, c) in enumerate(G):
    arts.append({"id": f"e{i}", "title": t, "source": s, "url": "#", "published": "2026-11-04T00:00:00+00:00",
                 "snippet": "", "region": "global", "country": c, "lean": l, "type": "언론", "via": "rss"})
Path(__file__).with_name("sample_articles.json").write_text(json.dumps(arts, ensure_ascii=False, indent=1), "utf-8")
print(len(arts))

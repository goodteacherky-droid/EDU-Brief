# 교육·사회 데일리 브리핑

매일 새벽 4시 30분(한국 시간) 국내·해외 교육·사회 기사를 자동으로 모아 이슈도를 매기고, 요약해 웹페이지로 게시하는 프로그램입니다.

## Ⅰ. 구성 개요

[표 1] 처리 단계

| 단계 | 내용 | 담당 |
|---|---|---|
| 1. 수집 | 구글 뉴스 검색 피드(국내 10개 검색어, 해외 3개 지역×9개 검색어), 매체 직접 RSS 10곳, 네이버 뉴스 API(선택) | `brief/collect.py` |
| 2. 사안 묶기 | 같은 사건·정책을 다룬 기사를 하나의 사안으로 묶고 분야·공식성·현장 관련성 판단, 전날까지의 사안과 연결 | Claude (`brief/llm.py`) |
| 3. 이슈도 산정·선별 | 점수 계산 후 다양성 규칙에 따라 핵심 3건과 분야별 이슈 선별 | `brief/scoring.py` |
| 4. 요약 | 사안별 3줄 요약, 학교 현장 시사점, 매체별 관점 차이 작성 | Claude (`brief/llm.py`) |
| 5. 게시 | 날짜별 자료 저장, 웹페이지에서 날짜 이동·분야·지역 필터·검색 | `docs/` (GitHub Pages) |

[표 2] 세 가지 조건의 구현 방식

| 조건 | 구현 방식 |
|---|---|
| 정보의 다양성 | ○ 출처를 유형(언론·교육전문지·공공기관·국제기구)·논조(진보·중도·보수)·지역(한국·미국·영국·싱가포르)으로 나누어 고정<br>○ 매체별로 돌아가며 기사를 뽑아 한 매체의 독점 방지<br>○ 해외 이슈 비율 하한(35%), 핵심 이슈 중 해외 1건 이상, 단독 보도 사안은 매체당 2건 상한<br>○ 화면 상단에 매체 성향 분포와 국내·해외 비율을 매일 표시 |
| 가장 이슈되는 것 강조 | ○ 이슈도 100점 = 보도 확산도 45 + 논조 폭 10 + 지속성 15 + 공식성 10 + 현장 관련성 20<br>○ 상위 3건을 「오늘의 핵심 이슈」로 맨 위에 배치<br>○ 「N일째 이어짐」「여러 논조 매체 보도」「공식 발표·제도」 표시, 점수 구성 공개 |
| 가독성 있는 요약 | ○ 사안마다 고정 양식: 명사형 제목, 개조식 3줄 요약, 학교 현장 시사점 1줄, 보도 관점 차이(있을 때만)<br>○ 해외 기사도 한국어로 요약, 모든 사안에 원문 링크 첨부<br>○ 「오늘의 흐름」 2~3줄로 하루 전체 요약 |

## Ⅱ. 준비물

| 항목 | 용도 | 비고 |
|---|---|---|
| GitHub 계정 | 매일 자동 실행(Actions), 웹페이지 게시(Pages) | 무료 |
| Anthropic API 키 | 사안 묶기·요약 | [console.anthropic.com](https://console.anthropic.com)에서 결제 수단 등록 후 발급 |
| 네이버 개발자센터 앱 키 (선택) | 국내 매체 범위 확대 | [developers.naver.com](https://developers.naver.com)에서 '검색' API 신청 |

## Ⅲ. 설치 순서

1. **저장소 만들기**: GitHub 오른쪽 위 [+] → [New repository] → 이름 입력(예: `edu-brief`) → **Public** 선택 → [Create repository]
   - 무료 계정은 공개 저장소에서만 웹페이지 게시가 됨. API 키는 아래 4번의 비밀 저장소에 들어가므로 공개되지 않음
2. **파일 올리기**: 저장소 화면의 [uploading an existing file] → 압축을 푼 폴더 안의 파일·폴더 전체를 끌어다 놓기 → [Commit changes]
   - `.github` 폴더가 꼭 함께 올라가야 함. Mac에서는 Finder에서 `Command + Shift + .` 을 눌러야 숨김 폴더가 보임
   - 올라가지 않았다면 [Add file] → [Create new file] → 이름 칸에 `.github/workflows/daily-brief.yml` 입력 → 파일 내용 붙여 넣기 → [Commit changes]
3. **쓰기 권한 켜기**: [Settings] → [Actions] → [General] → 맨 아래 Workflow permissions에서 **Read and write permissions** 선택 → [Save]
4. **API 키 등록**: [Settings] → [Secrets and variables] → [Actions] → [New repository secret]
   - Name: `ANTHROPIC_API_KEY` / Secret: 발급받은 키 → [Add secret]
   - (선택) 같은 방법으로 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 등록
5. **웹페이지 켜기**: [Settings] → [Pages] → Source: **Deploy from a branch** → Branch: `main`, 폴더: `/docs` → [Save]
6. **첫 실행**: [Actions] 탭 → (안내가 뜨면) [I understand my workflows, go ahead and enable them] → 왼쪽 「데일리 브리핑 만들기」 → [Run workflow] → [Run workflow]
   - 3~8분 뒤 초록색 체크가 뜨면 완료
7. **확인**: `https://(GitHub 아이디).github.io/(저장소 이름)/` 접속 → 휴대전화 홈 화면에 추가해 두면 앱처럼 사용 가능
   - 이후 매일 새벽 4시 30분 전후에 자동 갱신(GitHub 사정으로 10~30분 늦어질 수 있어 5시 30분 전에는 갱신됨)

## Ⅳ. 설정 바꾸기

코드는 고치지 않고 `config.yaml` 한 파일만 고칩니다. GitHub에서 파일을 열고 연필 아이콘 → 수정 → [Commit changes].

[표 3] 자주 바꾸는 설정

| 바꾸고 싶은 것 | 고칠 곳 |
|---|---|
| 분야 추가·삭제 | `fields` (이름과 설명 한 줄) |
| 국내·해외 검색어 | `google_news` → `queries` |
| 매체 직접 추가 | `rss` (RSS 주소, 지역, 유형, 성향) |
| 매체 성향 분류 | `outlets` |
| 핵심 이슈 개수, 해외 비율 | `diversity` |
| 이슈도 가중치 | `scoring` |
| 실행 시각 | `.github/workflows/daily-brief.yml`의 `cron` (UTC 기준, 한국 시간 −9시간) |

## Ⅴ. 비용

- **Max 플랜 사용 시 추가 비용 없음**: Max 플랜에 매월 포함되는 API 크레딧(월 100달러)으로 충당 가능
  - claude.ai(웹 브라우저) [설정] → [결제] → API 크레딧 항목의 [Link organization] → Console 조직 선택 또는 새로 만들기 → 약관 확인 후 연결
  - 연결한 Console 조직에서 API 키를 만들어 Ⅲ-4에 등록
  - 크레딧은 매월 새로 채워지고 이월되지 않음. 소진되면 구매 크레딧·자동 충전이 없는 한 실행이 멈출 뿐 구독 요금에 청구되지 않음
- 하루 기사 약 300~450건 기준 Claude 입력 약 8만~10만 토큰(원문 본문 발췌 포함), 출력 약 1만~1만 5천 토큰 추정
- Sonnet 5.5 표준 요금(입력 100만 토큰당 2달러, 출력 10달러) 기준 하루 약 0.25~0.35달러, 월 1만~1만 5천 원 내외 추정
- 실제 사용량은 Anthropic Console의 Usage 화면에서 확인. **Limits에서 월 사용 한도를 정해 두는 것을 권장**
- 비용을 줄이려면 `config.yaml`의 `model`을 `claude-haiku-5-5`로 바꾸거나 `max_articles_per_region`을 낮춤

## Ⅵ. 자주 나는 오류와 대처

| 증상 | 원인 | 대처 |
|---|---|---|
| Actions가 빨간 X, 로그에 `Permission denied`·`403` | 쓰기 권한 미설정 | Ⅲ-3 다시 확인 |
| 웹페이지 하단에 "간이 규칙으로 정리" 표시 | API 키 미등록·오타, 결제 한도 초과 | Secrets 이름이 `ANTHROPIC_API_KEY`인지, Console 잔액 확인 |
| 웹페이지가 404 | Pages 설정 누락 또는 첫 실행 전 | Ⅲ-5 확인 후 1~2분 대기, 첫 실행 완료 여부 확인 |
| 하단 「수집 실패 출처」에 매체 표시 | 해당 매체 RSS 주소 변경 | `config.yaml`의 `rss`에서 주소를 고치거나 그 줄 삭제(나머지 수집은 정상 진행) |

오류가 계속되면 Actions 실행 화면을 캡처해 Claude에게 보여 주세요.

## Ⅶ. 유의 사항

- 요약은 AI가 기사 제목·요지·본문 일부를 바탕으로 작성하므로 연수 자료·보고서에 인용할 때는 반드시 원문을 확인
- 기사 문장을 옮기지 않고 요약과 원문 링크만 게시하도록 설계함
- 매체 성향 분류는 다양성 점검을 위한 참고 분류이며 사용자가 직접 고칠 수 있음
- 구글 뉴스 경유 기사의 링크는 구글 뉴스를 거쳐 원문으로 이동함
- 공개 저장소이므로 웹페이지 주소를 아는 사람은 누구나 볼 수 있음(개인정보는 다루지 않음)

## Ⅷ. 파일 구성

```
config.yaml                  설정(분야·출처·다양성 규칙·가중치)
brief/collect.py             1단계 수집
brief/llm.py                 2·4단계 Claude 호출(실패 시 간이 규칙으로 대체)
brief/scoring.py             3단계 이슈도·선별
brief/run.py                 전체 실행
docs/index.html              웹페이지
docs/data/                   날짜별 브리핑 자료(자동 생성)
.github/workflows/           매일 자동 실행 설정
tests/                       시험 실행 도구(가상 데이터)
```

시험 실행(내 컴퓨터, 네트워크 불필요): `python -m tests.test_pipeline`, `python -m brief.run --fixture tests/sample_articles.json`

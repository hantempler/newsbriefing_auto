# PRJ_starisborn: 스타이즈본 프로젝트 지침 및 에이전트 인수인계 기록 (AGENTS.md)



> **안내**: 본 문서는 다양한 환경(로컬, 리모트, 타 기기 등)에서 여러 AI 에이전트가 교대하며 작업할 때 일관성과 연속성을 유지하기 위한 **단일 진실 공급원(Single Source of Truth, SSOT)** 문서입니다.  

> 작업에 착수하는 모든 에이전트는 본 문서를 먼저 숙지하고, 작업을 마친 후에는 반드시 **[4. 에이전트 작업 및 변경 이력 히스토리]**에 변경 사항을 기록해야 합니다.



---



## 1. 프로젝트 정체성 및 5대 절대 원칙



### 1) 프로젝트 핵심 목적

- **스타이즈본 (Star is Born)**: 한국 시청자(1030 세대 및 대중)가 열광하는 현대 스타(1960년대 이후 활동 중심)의 탄생(AM)과 작별(PM), 그리고 영구 보존되는 시네마틱 심층 다큐멘터리(주말 롱폼)를 제작하는 파이프라인.

- **슬롯별 목적**:

  - **AM (오전)**: `오늘 태어난 스타 (생일)` ➔ 찬사와 축하, 전성기 업적과 매력 조명.

  - **PM (오후)**: `오늘 우리 곁을 떠난 스타 (기일)` ➔ 따뜻한 추모와 헌정(In Memoriam).

- **절대 주의**: 역사 다큐(`PRJ_history`)와 일체 격리 운영되며, 역사적 위인전 어투를 엄금하고 대중성 100% 현대 인물 중심.



### 2) 7대 절대 가드레일 (Calendar & Longform 팩트체크 원칙)

1. **한국 대중 인지도 1순위**: 썸네일과 제목만 보고 즉각 클릭할 수 있는 스타(배우, K-POP, 개그맨, 친한파 팝스타, 해외축구 영웅 등).

2. **🚨 [PM 생존자 절대 배제 가드레일]**: 생존해 있는 인물은 PM 슬롯에 절대 등록 금지(가짜뉴스 원천 차단). 반드시 공식 사망 기록(Wikidata P570 및 부고 기사)이 있는 고인(`is_deceased=True`)만 등록하며, `brief`에 'YYYY년 MM월 DD일 별세' 명시.

3. **날짜(월-일) 팩트 100% 무결점 일치**: AM(생일), PM(기일) 일자가 당일(`MM-DD`)과 반드시 일치해야 함.

4. **10-24 3인 후보군 스카우트 표준**: 실시간 검색을 통해 3인 후보군(`top_candidates`)을 채점(`traffic_score`)하고 1위를 자동 선정하여 등록.

5. **시스템 분리 격리 원칙 (Zero-Impact Isolation)**: 데일리 숏폼 파이프라인(`src/`, `daily_starisborn.yml`)과 주말 롱폼 다큐(`longform/`, `weekly_longform.yml`)는 상호 간섭 없이 완전 분리 운영.

6. **🚨 [에버그린 롱폼 60컷 전수 팩트체크 및 대본 1:1 바인딩 원칙]**:

   - 60컷 확장 시 LLM 응답 길이 제한(Output Truncation)으로 인한 30컷 누락 방지를 위해 반드시 **30컷 단위 2단계 분할 감사(Cut 01~30, Cut 31~60)**를 강제한다.

   - 감사가 완료되면 `fact_check_report_60cuts.md`에 60개 전수 컷이 등재되어야 하며(`assert count == 60`), `storyboard_60cuts_master.json`의 60개 컷 각각에 1차 출처(`source_citation`), 사료 비평(`historical_critique`), 검증 상태(`status`)가 1:1로 결합되어야 한다.

   - 과장/왜곡 판정(`MYTH_EXAGGERATED`)된 컷은 대본 내레이션에 반전 교정 문구("흔히 ~로 알려졌지만, 실은...")를 반드시 반영한다.



7. **🚨 [이모지 및 특수문자(Tofu) 절대 배제 가드레일]**:

   - 영상 화면, 자막, 뱃지, 챕터 카드 등 모든 시각 요소에 이모지(📍, 📄, ⚖️, 💥 등) 및 폰트 미지원 특수문자 사용을 절대 엄금한다.

   - 사각형 폰트 깨짐(	ofu: □) 및 유치한 숏폼 스타일을 원천 차단하고, 넷플릭스/Magnates Media 규격의 클린 타이포그래피(영문 대문자 트래킹 + 슬래시/바 디바이더: 1975 | ALBUQUERQUE, NM)만 사용한다.



### 2.5) 롱폼 60컷 팩트체크 현황 관리 대장 (2026-10-30 기준)

- **60컷 전수 무결점 완료 (3인)**: W44 빌 게이츠, W49 존 레논, W52 조지 마이클

- **🚨 후반 30컷(Cut 31~60) 팩트체크 미검증 인물 (16인)**:

  W45 에마 스톤, W46 디카프리오, W47 프레디 머큐리, W48 폴 워커, W50 월트 디즈니, W51 브래드 피트, W01 니콜라스 케이지, W02 데이비드 보위, W03 오드리 헵번, W04 히스 레저, W05 크리스찬 베일, W06 휘트니 휴스턴, W08 커트 코베인, W09 존 본 조비, W10 노토리어스 B.I.G, W11 스티븐 호킹

- **절대 원칙**: 상기 16인에 대한 영상화 착수 전, 반드시 누락된 후반 30컷 사료 감사를 거쳐 대본/리포트에 1:1 바인딩할 것.



### 2.6) 롱폼 시네마틱 각본 극작술 3대 절대 원칙 (Narrative Rules)

1. **오프닝 킬러 대조 훅 (Cut 01~02)**: 단순 시대 설명으로 시작하는 교과서적 도입을 절대 엄금하고, 인물 생애의 가장 극단적인 두 모순(전성기 vs 몰락, 독점가 vs 성자)을 첫 5초에 정면 충돌시켜 멱살을 잡는다.

2. **5대 막 전환 브릿지 훅 (Turning Points)**: 각 막의 마지막 컷(Cut 06, 18, 26, 38, 50)은 결론을 짓고 끝내지 말고, 다음 막에서 닥쳐올 위기나 반전을 예고하는 오픈 루프 브릿지 문장("하지만 바로 그 순간, 거대한 칼날이...")을 반드시 배치하여 시청 지속률을 락인한다.

3. **철학적 수미상관 엔딩 (Cut 59~60)**: 진부한 칭찬이나 미사여구로 끝맺지 말고, 인물의 삶을 관통하는 본질적 물음을 시청자 본인의 삶과 직결시키는 '질문형 여운 문장'으로 완결한다.



---



## 2. 프로젝트 구조 및 핵심 컴포넌트



```text

PRJ_starisborn/

├── .agents/                   # [일원화] 에이전트 지침, 룰, 히스토리, 스킬 통합 관리

│   ├── AGENTS.md              # [본 문서] 에이전트 인수인계 및 작업 히스토리 SSOT

│   ├── HERO_PRODUCTION_MASTER_SPEC.md # [신규] 골캐스트형 3분 HERO 시네마틱 쇼츠 전 공정 마스터 규격서 (12씬 1:1 고유 컷 & 넷플릭스 다큐 룩)

│   ├── EVERGREEN_PRODUCTION_MASTER_SPEC.md # [최신] 롱폼 다큐 무인 렌더링 & 싱크 마스터 규격서 (PRJ_history 이식)

│   ├── PLANNING_PROPOSAL.md   # 숏폼 파이프라인 실행 계획서

│   ├── rules/

│   │   ├── calendar_rules.md  # 캘린더 인물 선정 및 10-24 스키마 5대 원칙

│   │   └── mermaid_artifacts.md

│   └── skills/

│       └── starisborn-calendar/SKILL.md # 캘린더 스카우트/검증 워크플로우

├── .github/workflows/

│   └── daily_starisborn.yml   # 매일 AM/PM 숏폼 자동 생성 & 유튜브 업로드 액션

│   └── weekly_longform.yml    # 주말 롱폼 다큐멘터리 수동/예약 실행 액션

├── data/

│   ├── calendar_db.json       # 누적 인물 데이터베이스 (현재 라이브 기준 운용)

│   └── calendar_db copy.json  # 47일치 원본 레퍼런스 백업본

├── src/                       # 데일리 숏폼 제작 엔진

│   ├── 01_star_script.py      # 대본 생성 (Gemini 2.5 Pro + Search Grounding)

│   ├── 02_star_image.py       # 9:16 레트로 팝아트 캐리커처 이미지 생성

│   ├── 03_star_tts.py         # 딕션 빠른 Gemini Kore 보이스 생성

│   ├── 05_star_music.py       # AM/PM 테마 BGM 생성 (Lyria-002)

│   ├── 06_star_subtitle.py    # 자막 및 메타데이터 추출

│   ├── 08_star_assemble.py    # FFmpeg 9:16 세로 영상 합성 (Ken Burns + 볼드 자막)

│   ├── build_calendar_365.py  # 캘린더 빌더 및 무결점 검증기

│   └── star_trend_scout.py    # 10-24 정식 3인 후보 실시간 스카우터

└── longform/                  # 주말 롱폼 다큐멘터리 전용 독립 파이프라인 (16:9 와이드)

    ├── README.md              # 롱폼 파이프라인 개요 및 4막 시네마틱 구조

    ├── run_longform.py        # 롱폼 통합 파이프라인 실행 런처

    ├── src/

    │   ├── 01_deep_research.py   # 심층 탐사 리서치

    │   ├── 02_act_script.py      # 4막 시네마틱 대본 (8~12분)

    │   ├── 03_wide_art.py        # 16:9 와이드 시네마틱 아트워크 (Nano-banana/Flash)

    │   ├── 04_narration_tts.py   # 다큐멘터리 저음 보이스 (Charon)

    │   └── 05_cinematic_assemble.py # FFmpeg 16:9 와이드 다큐 렌더러

    └── output/                # 롱폼 파일럿 제작 산출물 (웨인 루니 1080p MP4 등 완비)

```



---



## 3. 핵심 실행 명령어 치트시트



1. **캘린더 무결점 검증 (날짜 불일치 & PM 생존자 여부)**:

   ```bash

   python -c "

   import json

   from pathlib import Path

   db = json.loads(Path('data/calendar_db.json').read_text(encoding='utf-8'))['calendar']

   d_err = [f'{d} {s} ({item[\"person_name\"]})' for d, v in db.items() for s in ['am', 'pm'] if (item := v.get(s)) and not item['event_date'].endswith(d)]

   pm_err = [f'{d} PM ({item[\"person_name\"]})' for d, v in db.items() if (item := v.get('pm')) and not any(k in item.get('brief', '') for k in ['별세', '사망', '타계', '잠들다', '서거', '의거', '산화', '전사', '순국', '피살', '떠난', '심장은'])]

   print(f'검증: 총 {len(db)}일자 중 날짜 불일치 {len(d_err)}건, PM 생존자 의심 {len(pm_err)}건')

   "

   ```



2. **특정 일자 3인 후보군 실시간 스카우트 및 DB 반영**:

   ```bash

   python src/star_trend_scout.py --date 10-27 --mode am

   python src/star_trend_scout.py --date 10-27 --mode pm

   ```



3. **주말 롱폼 시네마틱 다큐멘터리 파일럿 생성**:

   ```bash

   # 대본 및 연출 지시서 생성

   python longform/run_longform.py --person "웨인 루니" --en "Wayne Rooney" --category "스포츠 / 축구" --step script

   # 전체 에셋 및 1080p 마스터 영상 렌더링

   python longform/run_longform.py --person "웨인 루니" --en "Wayne Rooney" --category "스포츠 / 축구" --step all

   ```



---



## 4. 에이전트 작업 및 변경 이력 히스토리 (Work Log)



> **규칙**: 작업을 수행한 에이전트는 교대 전 반드시 아래 표에 일시, 작업 분류, 핵심 변경 내용, 검증 상태를 누적하여 기록해야 합니다.



| 날짜 (KST) | 작업 분류 | 주요 작업 내역 및 변경 사항 | 검증 및 상태 |

| :--- | :--- | :--- | :--- |

| **2026-11-06** | 데일리 대본 엔진(01_star_script.py) 11-03 안정 원본(8d2db13) 전면 복구 완결 | • **11-04~05 실험 코드 전면 철회**: 알고리즘 저하를 초래했던 5대 서사 강제 인터록, 0초 실명 강제, 팩트 가드레일 경고문, 파이썬 후처리 로직 전면 삭제<br>• **11-03 안정 베이스라인 복원**: 소지섭(1,163회), 신성일(1,277회)을 달성했던 검증된 11월 3일 원본 대본 엔진(`8d2db13`, 김아중 오프닝 및 웨인 루니 엔딩 모범 예시 포함)으로 100% 원상복구 완료<br>• **캘린더 DB 100% 무결점 보존**: 봇이 자동 수집한 11-04(소지섭/신성일), 11-05(보아/아론 카터), 11-06(이동욱/이진원) 3일치 스타 데이터는 절대 손대지 않고 온전히 보존<br>• **원격 저장소 동기화 완료**: 커밋 `05c9aab`(`revert: restore 01_star_script.py to commit 8d2db13 (preserve calendar_db.json)`)로 GitHub `origin/main`에 안전하게 푸시 완료 | 원격 git diff 전수 검증 완료 (8d2db13과 0줄 차이 확인) |

| **2026-11-04** | 데일리 대본 생성 엔진(01_star_script.py) 서사 다변화 개조 완결 | • **판박이 클리셰 영구 박멸**: 매일 반복되던 `~알고 계셨나요?` 및 `오늘은 OOO가 태어난 날입니다` 단일 예시를 전면 삭제하고, 5대 플롯별 전용 훅/클로징 템플릿 독립화<br>• **팩트체크 기반 서사 DNA 자동 판정**: `run_fact_check`에서 `debunked_myths`와 팩트 성격에 따라 5대 플롯(`recommended_plot`) 및 `core_conflict`를 기계적으로 확정<br>• **LLM 락인 인터록 장착**: JSON 스키마에 `narrative_plot` 및 `core_conflict` 사전 선언을 강제하여 팩트 나열 일대기(Bio)로의 이탈 원천 차단<br>• **11-05 보아 실증 검증 완료**: `PLOT_B(언더독 투혼)`로 자동 판정되어 "IMF 30억 빚을 짊어진 만 13세 소녀" 훅부터 "가장 깊은 어둠 속 아시아의 별" 엔딩까지 무결점 생성 확인<br>• **캘린더 무간섭 원칙 준수**: GitHub Actions의 당일 실시간 3인 스카우터 자율성 보장을 위해 미래 일자(11-05 이후)는 `calendar_db.json`에 임의 주입하지 않고 청정 상태 롤백 완결 | E2E 대본 생성 및 JSON 검증 통과 |
| **2026-11-04** | 데일리 대본 서사 다변화 엔진 개조 및 단일 커밋 정합 완료 | • **판박이 클리셰 영구 박멸**: 매일 반복되던 `~알고 계셨나요?` 및 `오늘은 OOO가 태어난 날입니다` 단일 예시를 전면 삭제하고, 5대 플롯별 전용 훅/클로징 템플릿 독립화 (`src/01_star_script.py`)<br>• **팩트체크 기반 서사 DNA 자동 판정**: `run_fact_check`에서 `debunked_myths`와 팩트 성격에 따라 5대 플롯(`recommended_plot`) 및 `core_conflict`를 기계적으로 확정<br>• **LLM 락인 인터록 장착**: JSON 스키마에 `narrative_plot` 및 `core_conflict` 사전 선언을 강제하여 팩트 나열 일대기(Bio)로의 이탈 원천 차단<br>• **11-05 보아 실증 검증 완료**: `PLOT_B(언더독 투혼)`로 자동 판정되어 "IMF 30억 빚을 짊어진 만 13세 소녀" 훅부터 "가장 깊은 어둠 속 아시아의 별" 엔딩까지 무결점 생성 확인<br>• **캘린더 무간섭 원칙 준수**: GitHub Actions의 당일 실시간 3인 스카우터 자율성 보장을 위해 미래 일자(11-05 이후)는 `calendar_db.json`에 일체 임의 주입하지 않고 청정 원상태 복원<br>• **오직 1개 파이썬 파일 단독 커밋 & Rebase 완결**: 원격 저장소 최신 커밋(`ea48ebb`, 11-04 PM 신성일 등록본)을 가져와 `git rebase origin/main` 완료. 원격 변경사항과 무충돌 Fast-Forward 가능한 `src/01_star_script.py` 단독 커밋(`efafa99`, 1 file changed) 상태로 완벽 정합 | E2E 대본 검증 통과 및 단독 커밋 정합 완료 |
| **2026-11-04** | HERO 3분 시네마틱 다큐 전 공정 마스터 규격서 제정 | • **전 공정 단일 진실 공급원(SSOT) 수립**: 골캐스트 K-에디션 『Star is Born: HERO』 3분 시네마틱 세로 다큐의 전 공정 매뉴얼 확립 (`.agents/HERO_PRODUCTION_MASTER_SPEC.md`)<br>• **6단계 파이프라인 표준화**: (1) 3막 12씬 극작 공식 ➔ (2) 12씬 1:1 고유 비주얼 생성 ➔ (3) Gemini Charon TTS 및 물리 길이 프레임 스냅 ➔ (4) 72pt 샴페인 골드 ASS 자막 & 시네마틱 영문 태그 ➔ (5) FFmpeg Ken Burns & 사이드체인 오디오 덕킹 합성 ➔ (6) 유튜브 API 정규 예약 업로드<br>• **재현 무결점 보장**: 향후 어떤 에이전트나 교대 작업자가 투입되어도 인물명만 주어지면 엠마 스톤 편과 100% 동일한 퀄리티로 무인 생산 가능 체계 완성 | 규격서 제정 및 SSOT 동기화 완료 |
| **2026-11-03** | 엠마 스톤 3분 V2 시네마틱 쇼츠 유튜브 예약 업로드 완결 (11-06 22:00 KST) | • **V2 마스터 에셋 패키징 동기화**: 12개 씬 100% 고유 컷 + 넷플릭스 다큐 규격(영문 로케이션 태그 + 샴페인 골드 자막) V2 비디오(`EMMA_STONE_3MIN_HERO_CINEMATIC_MASTER.mp4`, 62.60 MB, 188.8초)를 `pilot/emma_stone_package/final_shorts.mp4`로 동기화 완료<br>• **유튜브 API v3 예약 업로드 완주**: 기존 `src/11_star_upload.py` 파이프라인을 호출하여 **2026-11-06 22:00 KST (`2026-11-06T13:00:00Z` UTC)** 정규 예약 공개 설정 완료 (Resumable Chunked 5MB 분할 전송 성공)<br>• **등록 결과**: Video ID `LaUaxtYS5CM`, URL `https://youtu.be/LaUaxtYS5CM`, 상태 `private` (11월 6일 밤 10시 정각 유튜브 서버에서 자동 공개 전환) | YouTube v3 API 예약 업로드 성공 검증 완료 |
| **2026-11-03** | 골캐스트형 프리미엄 라인업(HERO) 3분 V2 마스터 파일럿 완결 | • **골캐스트(Goalcast) K-에디션 마스터 기획안 수립**: 기존 AM/PM 일일 파이프라인 100% 보존 전제 하에 주간 프리미엄 라인업 『Star is Born: HERO』(3막 카타르시스: 언더독의 침묵 ➔ 불꽃의 결단 ➔ 거인의 포옹) 기획 완비 (`STARISBORN_HERO_EXPANSION_PLAN.md`)<br>• **188.8초(3분 8초) 12씬 전수 고유 컷 매핑 (중복 0%)**: 후반부 이미지 반복 문제를 해결하기 위해 12개 씬 전수 1:1 고유 시네마틱 컷 생성 및 바인딩 완료 (`gemini-nano-banana-2.1` 등 활용)<br>• **AM/PM 대비 넷플릭스 다큐 룩 차별화 확립**: 기존 숏폼 넘버링 박스 제거 ➔ 영문 로케이션/연도 시네마틱 태그(`1995 \| SCOTTSDALE, ARIZONA` 등) + 72pt 샴페인 골드 ASS 자막 + Whoosh SFX 배제로 Gemini Charon 명품 저음 내레이션과 감동 피아노 선율 몰입감 극대화<br>• **V2 마스터 렌더링 완주**: `pilot/output/EMMA_STONE_3MIN_HERO_CINEMATIC_MASTER.mp4` (62.60 MB, 188.83초, 1080x1920 세로 풀HD) 무결점 합성 완료 | V2 E2E 렌더링 및 ffprobe 검증 완료 |
| **2026-11-03** | 자막 누락 복구 및 100% 대본 보존 아라비아 숫자 자동 변환 | • **LLM 임의 요약/누락 원천 박멸**: LLM이 `display_text`를 요약/축약하여 음성 대비 자막이 조기 종료되던 문제를 해결하기 위해 대본 생성(`01_star_script.py`)에서 `display_text` 필드 제거 및 성우 낭독 대본(`narration`)을 단일 진실 공급원(SSOT)으로 확립<br>• **100% 문장 보존 확정적 시인성 변환 엔진 탑재**: `06_star_subtitle.py`에 `format_sub_display()` 신설 ➔ 전체 문맥과 토씨를 100% 유지하면서 한글 연도('천구백팔십오년' ➔ '1985년'), 월/일('시월 이십사일' ➔ '10월 24일'), 큰 수 단위('백만' ➔ '100만', '천억' ➔ '1,000억')만 아라비아 숫자로 정밀 변환하여 화면 시인성과 음성-자막 싱크 동시 확보 | 문법 및 정규식 무결점 검증 완료 |
| **2026-11-02** | 1일 2편(AM 07시+PM 19시) 정규 예약 파이프라인 개편 | • **1일 2편 정규 편성 확립**: 단일 픽 경쟁(`best`)을 폐지하고, 당일 AM(생일)과 PM(기일) 2편을 각각 온전히 제작하는 `both` 모드를 기본값으로 공식 전환 (`run_daily.py`, `.github/workflows/daily_starisborn.yml`)<br>• **유튜브 정밀 예약 공개 엔진 탑재**: `calculate_scheduled_publish_time()`을 신설하여 AM은 **오전 07:00 KST**, PM은 **오후 19:00 KST**에 맞춘 RFC 3339 UTC(`publishAt`)를 자동 계산 및 YouTube v3 API에 주입 (지정 시각 정각에 유튜브 자체 서버가 자동으로 비공개 ➔ 공개 전환)<br>• **과거 시각 안전 가드레일 완비**: 작업 실행 시점에 이미 07:00나 19:00가 경과한 경우 400 Bad Request 방지를 위해 즉시 공개로 안전 폴백<br>• **스카우터 루브릭 중립화**: 98/99점 편향 앵커링을 제거하고 100점 만점 3대 객관적 루브릭(인지도 40 + 화제성 30 + 극적서사 30)으로 AM/PM 공정 채점 체제 완비 (`src/star_trend_scout.py`) | 단위 테스트 & CLI 파싱 검증 완료 |

| **2026-11-02** | starisborn_evergreen 1080p 마스터 렌더링 & 유튜브 업로드 완결 | • **독립 에버그린 아키텍처 정립**: `PRJ_starisborn/starisborn_evergreen` 독립 파이프라인 구축 (`render_standalone_master.py`, `src`, `assets/bgm`, `config`, `output` 완비)<br>• **빌 게이츠 60컷 마스터 렌더링 완주**: `output/w44_bill_gates_master_1080p.mp4` (553.84 MB, 13분 44초 / 823.91s, 오차 0.00초), 60컷 사료 이미지 + 6개 Act Charon TTS + 2줄 미니멀 헤더(상단 주황 소제목 + 하단 화이트 펀치, 3단 중복 제거) 완벽 합성<br>• **BGM CC BY 4.0 저작권 & 강화된 서사 설명문 탑재**: `The Complex` by Kevin MacLeod 공식 출처 표기 + 1968년 해커 소년~1998년 반독점 법정~사재 70조 화장실 혁명 스토리텔링 반영<br>• **스타이즈본 독립 인증 및 유튜브 비공개 등록 완결**: `starisborn_evergreen/config/`로 `client_secret_1.json` 복사 및 스타이즈본 전용 `youtube_token.json` 영구 분리 보존, **스타이즈본 채널 비공개 업로드 성공 (Video ID: `NHR9YvsDjQI`, https://youtu.be/NHR9YvsDjQI)**<br>• **실측 오디오 누적 6개 Act 타임스탬프 탑재**: `00:00`, `01:25`, `04:07`, `06:10`, `08:55`, `11:30` 실측 동기화로 유튜브 플레이어 자동 챕터 완벽 활성화 | 스타이즈본 채널 업로드 E2E 완주 검증 완료 |

| **2026-11-01** | 계층형 하이브리드 표준 완결 (씬별 1:1 독립 TTS + 물리 길이 프레임 스냅) | • **계층형 하이브리드 표준 확립**: 챕터 통짜 합성 폐기 ➔ 60개 컷 전수 1:1 독립 TTS(슬라이딩 컨텍스트 운율 제어) + 음원 물리 길이 기반 100% 기계적 씬 길이 프레임 스냅(오차 0.000초, 씬 경계 추측 원천 배제)<br>• **간지 누락 및 아웃트로 완결**: 00:00초 서장 다이렉트 시작 + Cut 06 직후 **ACT 01: 야망의 탄생 & 차고의 기적** 정상 배치(총 5개 Act 간지) + 최종 아웃트로(5.0초, '시청해 주셔서 감사합니다' 단독, SFX 0개)<br>• **단일 트랙 393개 자막 무충돌 실증**: 씬 내부 완결 격리 + 33,333µs(1프레임) 안전 갭 강제로 CapCut PC 외톨이 트랙(Track 3 등) 생성 버그 100% 박멸<br>• **CapCut PC 슬롯 1031 (1) 5트랙 완주**: Track 0 비디오 66개, Track 1 헤더 60개, Track 2 자막 393개, Track 3 음성 60개 클립, Track 4 루프 BGM (총 러닝타임 856.22초, 14.27분) 듀얼 동기화 완결 | 계층형 하이브리드 E2E 완주 검증 완료 |

| **2026-11-01** | B안 확정 표준 완결 (서장 0초 직결 + SFX 전면 배제 + 클린 아웃트로) | • **B안 마스터 타임라인 규격화 완결**: 00:00초 서장(Cut 01) 간지 없이 다이렉트 시작 + 본편 60씬 + 5개 막 전환 간지(각 2.5s) + 최종 아웃트로(5.0s, '시청해 주셔서 감사합니다' 단독) 총 66개 비디오 클립 확립<br>• **효과음(SFX) 전면 배제**: 유치한 Sub-boom 효과음 일체 삭제(0개), 품격 있는 Charon 내레이션 + the_complex 심리스 루프 BGM 단독 운용<br>• **자막 싱크 1:1 결합 완결**: Act 1 Whisper 실측 단어 데이터(69.58s) 정밀 바인딩으로 11초 밀림 버그 원천 박멸 (총 393개 무충돌 자막 청크)<br>• **CapCut PC 슬롯 1031 (1) 주입 완료**: Track 0 비디오 66개, Track 1 헤더 60개, Track 2 자막 393개, Track 3 음성 6개, Track 4 루프 BGM (총 러닝타임 789.25초, 13.15분) 듀얼 동기화 완결 | B안 E2E 완주 검증 완료 |

| **2026-11-01** | 52주 표준 타임라인 & 클린 아웃트로 완결 | • **52주 롱폼 마스터 타임라인 규격화**: 00:00초 Act 1 오프닝 카드(2.5s) + 본편 60씬 + 5개 Act 전환 간지(각 2.5s) + 최종 아웃트로(5.0s) 총 7대 카드 구조 확립<br>• **클린 아웃트로 카드 단독 적용**: 잡다한 추천 UI 및 다음 편 예고 전면 삭제, '시청해 주셔서 감사합니다' 단독 문구 C-1 중앙 정렬 반영 (`card_outro.png`, `card_outro.mp4`)<br>• **CapCut PC 슬롯 1031 (1) 주입 완결**: 총 67개 비디오 클립(Track 0), 헤더 60개(Track 1), 271개 비충돌 자막(Track 2), 6개 Act 음성(Track 3), 6개 48kHz Sub-boom SFX(Track 4), 14분 심리스 루프 및 아웃트로 5초 페이드아웃 BGM(Track 5) 완주 (총 러닝타임 791.75초, 13.20분) | E2E 주입 및 동기화 완료 |

| **2026-10-24** | DB 정비 / UI | • 썸네일 헤드라인 특수문자 제거 및 72pt 볼드 폰트 적용<br>• 로자 파크스 QID(`Q41921`) 정정 및 레거시 포트레이트 폴더 삭제 | 정상 완료 |

| **2026-10-25** | 캘린더 가드레일 | • PM 슬롯 생존자 원천 차단 및 중복 폴백 방지 로직 적용<br>• 10-25 항목 교정 및 실시간 누적을 위해 10-25 이후 미래 일자 정리 | 검증 통과 |

| **2026-10-26** | 스카우터 표준화 | • 10-24 3인 후보군 경합 스카우트 표준 전면 반영 (`star_trend_scout.py`)<br>• JSON 추출 정규식 고도화 및 추모 키워드 딕셔너리 확장 | 단위 테스트 완료 |

| **2026-10-26** | 롱폼 신설 | • 16:9 주말 롱폼 다큐멘터리 전용 독립 파이프라인 신설 (`longform/`)<br>• 리서치(`01`), 4막 각본(`02`), 와이드아트(`03`), 저음TTS(`04`), FFmpeg(`05`) 완성<br>• 주말 롱폼 GitHub Actions 워크플로우 추가 (`weekly_longform.yml`)<br>• 1호 파일럿 **'웨인 루니: 투견'** 1080p 마스터 영상 생성 완비 | 파일럿 산출물 검증 완료 |

| **2026-10-27** | 인수인계 규격화 | • 다중 작업환경 인수인계를 위한 통합 `AGENTS.md` 신설<br>• 프로젝트 정체성, 가드레일, 실행 치트시트, 히스토리 테이블 규격화 | 운영 체계 확립 |

| **2026-10-27** | GCP 인증 동적화 | • `GCP_PROJECT_ID` 하드코딩 제거 및 `application_default_credentials.json` 자동 감지 로직 적용 (`src/` 7개 파일 전수 개조)<br>• GitHub 원격(`origin/main`) 푸시 완료 (커밋: `56d3cc2`) | 단위 테스트 & 푸시 완료 |

| **2026-10-27** | 하드코딩 잔재 전면제거 | • 코드 내 임의의 폴백 프로젝트 ID(`project-092c...`) 전수 제거<br>• 인증 파일/환경변수 부재 시 침묵하지 않고 명시적 `ValueError` 발생하도록 가드레일 정밀화<br>• GitHub 원격(`origin/main`) 푸시 완료 (커밋: `e043330`) | 완전 무결 검증 완료 |

| **2026-10-27** | 3.5-Flash 모델 전면 전환 & 듀얼 키 호환 | • 신규 GCP 프로젝트(`project-092cc...`)와 기존 7월 키(`project-beba...`) 모두에서 100% 작동하도록 모델을 `gemini-3.5-flash` 및 `location="global"`로 전환<br>• `src/` (스카우트, 대본, 자막, 캘린더) 전수 반영 및 `02`, `03`, `05` `import json` 보강<br>• 11-30 AM 풀 파이프라인 로컬 완주 검증 성공<br>• GitHub 원격(`origin/main`) 커밋 & 푸시 완료 (커밋: `aca3982`) | 로컬 E2E 검증 & 푸시 완료 |

| **2026-10-27** | 원격 롱폼 디렉터리 분리/제거 | • 사용자 지시 없이 푸시되었던 `longform/` 및 `weekly_longform.yml`을 GitHub 원격 저장소에서 즉시 untrack/제거 (`git rm --cached`)<br>• 로컬 파일은 100% 안전 보존하고, 원격에는 숏폼 파이프라인만 격리 유지하도록 복구 완료 (커밋: `318f081`) | 원격 제거 및 로컬 보존 완료 |

| **2026-10-27** | 에이전트 문서 일원화 | • 프로젝트 루트에 산재해 있던 `AGENTS.md` 및 `PLANNING_PROPOSAL.md`를 `.agents/` 디렉터리로 이동 및 일원화<br>• `calendar_rules.md` 등 참조 경로 정정 및 에이전트 통합 관리 체계 확립 | 정상 완료 |

| **2026-10-27** | YouTube API 권한 확장 | • `@starisborn_101` 채널 대상 전체 권한 토큰 발급 완료 (`config/youtube_token.json`)<br>• 동영상 업로드 외 채널 정보/통계(`youtube.readonly`), 영상 관리/수정(`youtube`), 애널리틱스(`yt-analytics.readonly`) 권한 확보 및 API 호출 검증 완료 | 실시간 검증 완료 |

| **2026-10-27** | 영상 8종 메타데이터 최적화 | • 트래픽 상위 8개 영상(루니, 이건희, 레이놀즈, 파월, 피트번즈, 반담, 신해철, 서인국) 메타데이터 일괄 최적화 완료<br>• 유튜브 검색 유입용 SEO 상단 블록 및 검색 태그 15~23개 풀 확장 반영 (API `videos.update`) | 실시간 반영 완료 |

| **2026-10-27** | 차세대 쇼츠 파일럿 제작 | • Google Veo-3.1 4초 오프닝 킬러 모션 + 32초 초압축 서사 파일럿 생성 완료 (`BILL_GATES_PILOT_MASTER.mp4`)<br>• 1080x1920 세로 풀HD, 씬별 Pillow 볼드 자막 베이킹, Puck 쾌속 TTS 나레이션, 채널 구독 엔딩 완비 | 검증 완료 (output/) |

| **2026-10-28** | Evergreen 빌더 통합 & 출처 명시 | • `scratch/`에 방치되었던 라인업 코드를 `evergreen/builder/`로 통합 (`build_52weeks_lineup.py`, `verify_52weeks.py`)<br>• `build_52weeks_lineup.py`의 출처 사실 명시: 사용자 수작업이 아닌 **이전 AI 에이전트가 10-27에 일괄 생성하여 저장해 둔 파일**임을 확정 기록<br>• 52주 데이터 동기화(`data/` 및 `evergreen/data/`) 및 날짜/규칙 무결점 테스트 완료 | 정상 완료 |

| **2026-10-28** | 임시 파일 전면 정리 및 초기화 | • 사용자 미승인 임시 생성 파일 전면 삭제 완료 (`evergreen/vault/` 전체 및 `evergreen/src/` 내 신규 스크립트 10종 삭제)<br>• 원본 데이터([52weeks.json](file:///g:/내%20드라이브/2_프로젝트/PRJ_starisborn/evergreen/data/52weeks.json)) 및 빌더 원본 100% 보존 상태로 롤백 완료 | 정리 완료 |

| **2026-10-28** | 한국인 롱폼 보류 & 60컷 확장 파이프라인 수립 | • 한국인 인물 AI 왜곡 한계 공식 확인 ➔ 한국인 16명 이미지 생성 전면 보류(Freeze)<br>• 글로벌 퀄리티 100% 보장되는 외국인 36명 전원 대상 '60컷(10~12분 정통 다큐)' 확장 파이프라인 수립<br>• 🚨 **절대 가드레일**: 신규 30컷에 대한 `02_storyboard_fact_checker.py` 전수 팩트 감사(출처 바인딩) 필수 관문 삽입 (`04_expand_to_60cuts.py`)<br>• `batch_foreign_stars_full.py`에 30컷 완주 즉시 60컷 확장으로 무인 자동 연계되는 오케스트레이션 탑재 | 가드레일 수립 완료 |

| **2026-10-29** | 밤샘 31명 완주 & 타 환경 인수인계서 발간 | • 외국인 36명 중 **31명 30컷(약 940장) 완주 완료** (현재 32번째 프레디 머큐리 진행 중)<br>• 타 환경 및 교대 에이전트를 위한 최상위 인수인계 종합 보고서 발행 ([HANDOVER_REPORT.md](file:///C:/Users/user/.gemini/antigravity/brain/7edc21c3-0506-414b-a848-e043063f682c/HANDOVER_REPORT.md))<br>• 60컷 자동 확장 배치 러너(`batch_expand_all_60cuts.py`) 완비 및 실행 치트시트 규격화 | 인수인계 준비 완료 |

| **2026-10-29** | 작업 안전 중단 및 다음 환경 대기 완료 | • 06:36 KST 기준 백그라운드 배치(`task-759`) 안전 종료 완료<br>• **최종 상태**: 31명 완전 완료, 1명(프레디 머큐리 23장) 보존, 4명 미착수<br>• 4중 중복 생성 방지 확인 완료 ➔ 다음 환경에서 `python evergreen/src/batch_foreign_stars_full.py` 1줄로 즉시 프레디 머큐리 24번 컷부터 자동 재개 가능 | 안전 정지 완료 |

| **2026-10-29** | 외국인 36명 30컷 100% 완주 & 60컷 확장 패치 | • 외국인 스타 **36명 전원 30컷(각본+팩트체크+30장 1080p 와이드 이미지) 완주 완료**<br>• 60컷 확장 연계 중 발생한 파라미터 불일치(`get_episode_id`, `audit_storyboard`) 및 `io` 누락 버그 전수 수정 완료<br>• `batch_expand_all_60cuts.py` 및 `04_expand_to_60cuts.py` 100% 연동 정상화 | 패치 완료 & 가동 준비 |

| **2026-10-29** | 60컷 확장 배치 1명 완주 후 안전 중단 | • `W02 데이비드 보위`: 60컷 대본 + 전수 팩트체크 + 60장 이미지 100% 완주<br>• `W03 오드리 헵번`: 60컷 대본 + 팩트체크 완료 후 이미지 58장 생성 시점에 사용자 요청으로 안전 종료 완료 (`task-175`)<br>• 언제든 `python evergreen/src/batch_expand_all_60cuts.py`로 오드리 헵번 잔여 2컷부터 중복 없이 재개 가능 | 안전 중단 완료 |

| **2026-10-29** | 52주 올-글로벌 개편 & W44 빌 게이츠 재개 | • **전략적 개편**: 한국인 16명의 AI 얼굴 왜곡 한계를 극복하기 위해 날짜 팩트 100% 일치 외국 슈퍼스타 16인으로 전면 교체 완료 (`evergreen/data/52weeks.json`, `data/52weeks.json`)<br>• `batch_foreign_stars_full.py`에 `--start` 및 `--end` 옵션 신설 (W44~W03 순환 구간 지원)<br>• **W44 빌 게이츠 30컷 완주 완료** 및 `W45 에마 스톤` 순차 진행 중 (`task-327`) | 정상 가동 중 |

| **2026-10-30** | 롱폼 CapCut 정규화 & 다이내믹 분할 자막 | • `evergreen/src/` 임시 스크립트 전면 정리 및 정규 파이프라인 `06_capcut_documentary_builder.py`로 일원화<br>• 장문 통자막 전면 폐기: `src/06_star_subtitle.py` 공식 계승 216개 호흡별 어절 분할(Dynamic Chunking, 10~18자 단위) 100% 적용<br>• 화면 중앙/상단 거대 텍스트 전면 영구 삭제 및 최하단 1줄 클린 자막(size: 3.8, y: -0.84) 고정 | 검증 완료 |

| **2026-10-30** | CapCut VAD 싱크 & 뱃지 복원 완결 | • CapCut 9.6 홈 화면 미노출 결함 해결: `draft_id`(`60948990-07B5-416d-88DC-5B5D7708B17B`) 3중 완벽 일치 및 썸네일 바인딩 완료<br>• 자막 싱크 결함 해결: FFmpeg `silencedetect` VAD 기반 발화 시작점(`lead_in`) 및 묵음 파형 1:1 결합 (214개 청크)<br>• 화면 상단 뱃지 복원: 60개 전수 컷 2.5초 노출 후 자동 페이드아웃(`size: 2.2`, 좌상단 여백, 이모지 0%)<br>• 화면 중앙 `punch_text` 영구 삭제 완료 (순수 시각 아트워크 90%+ 보존) | CapCut PC 로컬 검증 완료 |

| **2026-10-30** | CapCut 연동 기술 표준화 & PRJ_history 이식 완결 | • CapCut 9.6 멀티 타임라인 C++ 엔진 스키마 완전 해독 및 SSOT 규격서 발행 ([CAPCUT_INTEGRATION_MASTER_SPEC.md](file:///g:/내%20드라이브/2_프로젝트/PRJ_history/.agents/docs/CAPCUT_INTEGRATION_MASTER_SPEC.md))<br>• `PRJ_history/.agents/AGENTS.md` 및 `docs/`에 영구 보존 이식 완료 (타 프로젝트 재개 시 100% 무인 활용 보장)<br>• 듀얼 `draft_content.json` 동기화, SFX `sound_effect` 메타데이터 교정, Gemini AI 210개 호흡 청크 및 옐로우 하이라이트 100% 이식 완료 | 표준화 및 영구 보존 완료 |

| **2026-10-29** | 1일 1영상 최고 트래픽 단일 픽 개편 | • **숏폼 파이프라인 최적화**: 하루 2편(AM/PM) 분산 업로드에서 **당일 최고 트래픽 1인 단일 픽(1일 1영상)** 체제로 전면 개편<br>• `src/star_trend_scout.py`에 `scout_daily_best_star()` 신설 (AM 생일 vs PM 추모 트래픽 점수 맞대결 선별)<br>• `run_daily.py` 및 `.github/workflows/daily_starisborn.yml` 기본 모드를 `--mode best`로 전환 (실행 시간 & API 비용 50% 절감) | 반영 완료 |

| **2026-10-31** | PRJ_history 마스터 엔진 이식 & W44 빌게이츠 60컷 완주 | • `PRJ_history/history_evergreen`의 `11_capcut_ep01_master_builder.py` 806줄 프로덕션 코드를 100% 동일 이식 (`evergreen/src/capcut/w44_bill_gates_master_builder.py`)<br>• CapCut 네이티브 텍스트 버그 원천 배제: Pillow 1920x1080 투명 PNG 헤더 60장 + 자막 272장 사전 베이킹<br>• 6개 Act Charon TTS 합성(816.39초, 13.61분) + faster-whisper 1,237개 단어 실측 1:1 직결<br>• 60장 와이드 이미지 100% 무손실 보존 + FFmpeg 1080p 4단 켄 번스 MP4 비디오 렌더링<br>• 테크 다큐 명곡 BGM(`the_complex.mp3`, CC BY 4.0) 배치 및 유튜브 설명란 템플릿 완비<br>• CapCut PC 슬롯 `1031 (1)`에 5트랙 타임라인 및 듀얼 `draft_content.json` 주입 완결 | 5트랙 E2E 완주 검증 완료 |

| **2026-11-01** | BGM 시드 난수화 & 자막/발음 듀얼트랙 개편 | • `05_star_music.py`: `seed: 42` 고정 해제 및 `random.randint(1, 999999)` 동적 시드 적용 (곡 획일화 해소)<br>• `01_star_script.py`: TTS 낭독용(`narration`)과 화면 자막용(`display_text`) 스키마 원천 분리 (한글 발음 오독 방지 및 아라비아 숫자 깔끔 자막 구현)<br>• `06_star_subtitle.py`: `display_text` 우선 참조 및 `narration` 폴백 하위 호환성 적용 | 무결점 검증 & 푸시 완료 |

| **2026-11-01** | 롱폼 리마스터 v2 & 6트랙 전환 카드 완결 | • **5대 막 전환 카드 & 48kHz Sub-boom SFX 자동 주입**: C-1 좌측 앰버 바 + 중앙 정렬 2.5초 브릿지 카드 5장 렌더링 및 타임라인 배치<br>• **자막 겹침(4분 51초 등) 100% 박멸**: 1프레임(33ms) 인접 자막 자동 클리핑 가드레일 적용 (271개 자막 청크 충돌 0%)<br>• **BGM 4분 끊김 해결**: 14분 전편 심리스 무중단 루프 음원(`the_complex_looped.mp3`, 798초) 생성 및 Track 5 배치<br>• **Cut 01/Cut 12 대본 및 TTS 교정**: '오늘 태어나' 제거 및 'MITS 본사' 명시 반영, Gemini 2.5 Pro TTS & Whisper 재전사 완료<br>• **CapCut 슬롯 `1031 (1)` 주입 완료**: 비디오 65개, 헤더 60개, 자막 271개, 음성 6개, SFX 5개, BGM 1개 (총 6트랙 795.89초 완주) | E2E 검증 완료 |



---



## 5. 다음 교대 에이전트를 위한 인수인계 사항 (To-Do & Handover)

1. **W44 빌 게이츠 CapCut 마스터 프로젝트 (리마스터 v2 주입 완결)**:

   - `evergreen/src/capcut/w44_bill_gates_master_builder.py`로 CapCut PC 슬롯 `1031 (1)`에 795.89초(13.26분) 6트랙 타임라인 주입 완결됨.

   - C-1 좌측 앰버 바 + 중앙 정렬 챕터 전환 카드 5개(2.5초 브릿지) + 48kHz Sub-boom SFX 결합 완료.

   - 4분 51초 자막 겹침 버그 박멸, BGM 14분 무중단 루프, Cut 1 및 Cut 12 내레이션/TTS 교정 완료.

   - 사용자 최종 확인 후 차기 롱폼 대상(W45 에마 스톤, 60컷) 동일 표준 파이프라인 연계.

2. **GitHub Actions 검증**:

   - gemini-3.5-flash 및 global 엔드포인트 코드가 origin/main에 푸시되었습니다.

   - GitHub Secret (GCP_CREDENTIALS_JSON)에 어떤 키(신규 키 또는 기존 7월 키)가 들어가 있어도 모두 100% 양방향 호환되어 정상 작동합니다.

3. **캘린더 현황**:

   - data/calendar_db.json은 10-15 ~ 10-26까지의 정규 라이브 누적 상태를 안전하게 유지 중입니다. (11-30 테스트 데이터는 롤백 완료)

4. **인증 파일 안전**:

   - .gitignore에 	est/가 추가되어 임시 테스트 키가 원격에 절대 커밋되지 않도록 보호 조치 완료.


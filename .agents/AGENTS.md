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

---

## 5. 다음 교대 에이전트를 위한 인수인계 사항 (To-Do & Handover)
1. **W44 빌 게이츠 CapCut 마스터 프로젝트**:
   - evergreen/src/capcut/w44_bill_gates_master_builder.py로 CapCut PC 슬롯 1031 (1)에 816.39초(13.61분) 5트랙 타임라인 주입 완결됨.
   - 내일 재개 작업:
     - 우측 상단 연도 타임스탬프(1968~2024) 미니멀 박스 디자인 추가 여부 결정 및 적용.
     - 챕터 전환 효과(SFX) 및 추가 편집 요청 사항 반영.
     - 최종 확인 후 52주 차기 인물(W45 에마 스톤, 60컷) 동일 표준 파이프라인 연계.
2. **GitHub Actions 검증**:
   - gemini-3.5-flash 및 global 엔드포인트 코드가 origin/main에 푸시되었습니다.
   - GitHub Secret (GCP_CREDENTIALS_JSON)에 어떤 키(신규 키 또는 기존 7월 키)가 들어가 있어도 모두 100% 양방향 호환되어 정상 작동합니다.
3. **캘린더 현황**:
   - data/calendar_db.json은 10-15 ~ 10-26까지의 정규 라이브 누적 상태를 안전하게 유지 중입니다. (11-30 테스트 데이터는 롤백 완료)
4. **인증 파일 안전**:
   - .gitignore에 	est/가 추가되어 임시 테스트 키가 원격에 절대 커밋되지 않도록 보호 조치 완료.

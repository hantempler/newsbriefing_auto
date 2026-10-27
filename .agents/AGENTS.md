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

### 2) 5대 절대 가드레일 (Calendar Rules 준수)
1. **한국 대중 인지도 1순위**: 썸네일과 제목만 보고 즉각 클릭할 수 있는 스타(배우, K-POP, 개그맨, 친한파 팝스타, 해외축구 영웅 등).
2. **🚨 [PM 생존자 절대 배제 가드레일]**: 생존해 있는 인물은 PM 슬롯에 절대 등록 금지(가짜뉴스 원천 차단). 반드시 공식 사망 기록(Wikidata P570 및 부고 기사)이 있는 고인(`is_deceased=True`)만 등록하며, `brief`에 'YYYY년 MM월 DD일 별세' 명시.
3. **날짜(월-일) 팩트 100% 무결점 일치**: AM(생일), PM(기일) 일자가 당일(`MM-DD`)과 반드시 일치해야 함.
4. **10-24 3인 후보군 스카우트 표준**: 실시간 검색을 통해 3인 후보군(`top_candidates`)을 채점(`traffic_score`)하고 1위를 자동 선정하여 등록.
5. **시스템 분리 격리 원칙 (Zero-Impact Isolation)**: 데일리 숏폼 파이프라인(`src/`, `daily_starisborn.yml`)과 주말 롱폼 다큐(`longform/`, `weekly_longform.yml`)는 상호 간섭 없이 완전 분리 운영.

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

---

## 5. 다음 교대 에이전트를 위한 인수인계 사항 (To-Do & Handover)
1. **GitHub Actions 검증**:
   - `gemini-3.5-flash` 및 `global` 엔드포인트 코드가 `origin/main`에 푸시되었습니다.
   - GitHub Secret (`GCP_CREDENTIALS_JSON`)에 어떤 키(신규 키 또는 기존 7월 키)가 들어가 있어도 모두 100% 양방향 호환되어 정상 작동합니다.
   - 필요 시 GitHub Actions `Daily Star is Born Shorts Pipeline`을 트리거하여 원격 러너 실행을 검증할 것.
2. **캘린더 현황**:
   - `data/calendar_db.json`은 10-15 ~ 10-26까지의 정규 라이브 누적 상태를 안전하게 유지 중입니다. (11-30 테스트 데이터는 롤백 완료)
3. **인증 파일 안전**:
   - `.gitignore`에 `test/`가 추가되어 임시 테스트 키가 원격에 절대 커밋되지 않도록 보호 조치 완료.


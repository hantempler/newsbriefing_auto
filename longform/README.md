# 🎬 스타이즈본 주말 롱폼 다큐멘터리: THE ARCHIVE (더 아카이브)

> **안전 격리 원칙 (Zero-Impact Isolation)**:
> 본 `longform/` 디렉토리 내의 모든 코드, 데이터, 출력물은 기존 데일리 숏폼 파이프라인(`src/`, `daily_starisborn.yml`, `data/calendar_db.json`)과 100% 독립적으로 분리 운영됩니다. 데일리 숏폼 시스템에는 어떠한 영향도 주지 않습니다.

---

## 1. 개요
* **포맷**: 16:9 와이드 풀HD/4K 시네마틱 심층 인물 다큐멘터리 (길이: 8분 ~ 12분)
* **발행 주기**: 주 1회 (주말 골든타임)
* **기획 벤치마크**:
  * **Magnates Media** (2.5D 패럴랙스 무빙, 시네마틱 앰비언스, 느와르 연출)
  * **James Jani** (인물의 내면 결핍과 사회적 모순을 파헤치는 탐사 서사)
  * **SunnyV2** (시작 10초 만에 시청자를 사로잡는 콜드 오프닝 & 흥망성쇠 페이싱)

---

## 2. 4막 시네마틱 서사 구조 (4-Act Framework)

```text
[프롤로그: Cold Open] (0:00 ~ 1:30)
 └ 인생에서 가장 충격적이거나 모순적인 순간으로 시작, 호기심 갭(Curiosity Gap) 극대화

[제 1 막: The Genesis] (1:30 ~ 4:00)
 └ 결핍, 가난, 편견, 무명 시절을 버텨내고 자신만의 무기를 벼리던 치열한 기원

[제 2 막: The Zenith & The Fracture] (4:00 ~ 7:30)
 └ 세계의 정점에 오른 황금기, 그리고 마주한 거대한 스캔들, 부상, 배신, 몰락의 위기

[제 3 막: The Legacy] (7:30 ~ 10:00+)
 └ 시련을 딛고 시대의 상징이 된 순간, 그리고 오늘날 우리에게 남긴 삶의 태도와 철학적 여운
```

---

## 3. 디렉토리 구조

```text
longform/
├── README.md                 # 롱폼 프로젝트 안내 및 원칙
├── run_longform.py           # 롱폼 통합 파이프라인 실행 런처
├── src/                      # 롱폼 전용 파이프라인 엔진
│   ├── 01_deep_research.py   # Google Search Grounding 기반 심층 탐사 리서치
│   ├── 02_act_script.py      # 4막 시네마틱 8~12분 장문 대본 및 연출 지시서 생성
│   ├── 03_wide_art.py        # 16:9 와이드 시네마틱 아트워크 생성 (Nano-banana/Flash)
│   ├── 04_narration_tts.py   # 다큐멘터리 전용 저음 마스터링 TTS (Charon / Aoede)
│   └── 05_cinematic_assemble.py # FFmpeg 기반 16:9 켄 번스 & 챕터 렌더러
├── data/                     # 롱폼 전용 아카이브 및 프롬프트 템플릿
└── output/                   # 롱폼 렌더링 결과물 (대본, 이미지, 음성, 완성 영상)
```

# 스타이즈본 캘린더 구축 및 갱신 표준 규칙 (Calendar Rules)

모든 AI 에이전트는 `PRJ_starisborn` 프로젝트에서 인물 캘린더(`data/calendar_db.json` 및 `src/build_calendar_365.py`)를 확장하거나 수정할 때 다음 5대 절대 원칙을 반드시 준수해야 한다.

---

## 1. 인물 선정 5대 절대 원칙
1. **한국 시청자 인지도 1순위 (1030 쇼츠 최적화)**
   - 대한민국 전 국민이 아는 드라마/영화 톱스타, K-POP 레전드, 국민 개그맨, 친한파 할리우드 스타, 해외축구 영웅.
   - 썸네일과 제목만 보고 즉각 클릭할 수 있는 대중적 인물 100%.
2. **슬롯별 목적과 톤앤매너**
   - **AM (오전)**: `오늘 태어난 스타 (생일)` -> **찬사와 축하**, 업적과 매력 강조.
   - **PM (오후)**: `오늘 우리 곁을 떠난 스타 (기일)` -> **따뜻한 추모와 헌정(In Memoriam)**.
     - **🚨 [생존자 절대 배제 가드레일]**: 현재 생존해 있는 살아있는 인물은 PM 슬롯에 절대 등록할 수 없다. (예: 서인국, 드레이크 등 생존자의 생일을 PM에 등록하는 가짜뉴스 행위 엄벌). 반드시 공인된 공식 사망 기록(Wikidata P570 사망일자, 언론 부고 기사)이 있는 **실제 고인(is_deceased=True)**만 등록해야 하며, `brief` 문구에 반드시 'YYYY년 MM월 DD일 별세'를 명시해야 한다.
3. **날짜(월-일) 팩트 100% 무결점 일치**
   - AM 인물의 생년월일은 반드시 해당 날짜(`YYYY-MM-DD`에서 `MM-DD`)와 일치해야 함.
   - PM 인물의 사망일자는 반드시 해당 날짜(`YYYY-MM-DD`에서 `MM-DD`)와 일치해야 함.
   - 추측이나 근사치 날짜 등록 엄금 (반드시 Google Search 또는 Wikidata 교차 검증).
4. **현대 인물 중심 (1960년대 이후 활동)**
   - 원칙적으로 1960년대 이후 활동한 현대 인물을 우선 배정 (단, 마티스·차이콥스키·케플러 등 전 세계적 위인/거장은 예외적 허용).
5. **초상권 및 비방 방지 정책**
   - 논란이 있거나 범죄 이력이 있는 인물은 배제.
   - 영상 및 썸네일은 실사 초상권 문제를 피하기 위해 AI 생성 일러스트를 사용하므로, 시각적 묘사가 뚜렷한 특징 필요.

---

## 2. 데이터 스키마 표준 규격 (10-24 정식 표준)
각 날짜의 항목은 반드시 3인 경합 심사 보고서(`top_candidates`)와 선정 근거(`trend_score`, `trend_reason`)를 포함하는 **10-24 표준 규격**을 준수해야 한다:

```json
{
  "person_name": "웨인 루니",
  "person_name_en": "Wayne Rooney",
  "category": "축구 선수 (스포츠)",
  "event_date": "1985-10-24",
  "keywords": ["맨유 레전드", "박지성", "축구 영웅", "악동"],
  "brief": "한국 축구 팬들의 가슴 속에 영원히 기억될 맨유의 심장, 웨인 루니! 박지성과의 환상적인 호흡으로 감동을 선사한 '우리들의 레전드'.",
  "is_deceased": false,
  "trend_score": 98,
  "trend_reason": "한국 대중 체감 인지도 및 박지성과의 정서적 추억 연결고리가 가장 강력한 1위 메인 스타.",
  "top_candidates": [
    {
      "rank": 1,
      "person_name": "웨인 루니",
      "person_name_en": "Wayne Rooney",
      "category": "축구 선수 (스포츠)",
      "birth_date": "1985-10-24",
      "korean_resonance": "맨유에서 박지성 선수와 함께 황금기를 이끌며 한국 축구 팬들에게 깊은 향수와 추억을 선사.",
      "viral_story_point": "맨유의 전설적인 공격수 드라마틱 성장 서사.",
      "traffic_score": 98
    },
    {
      "rank": 2,
      "person_name": "후보2",
      "person_name_en": "Candidate 2",
      "category": "카테고리",
      "birth_date": "YYYY-MM-DD",
      "korean_resonance": "한국 대중성 분석",
      "viral_story_point": "바이럴 포인트",
      "traffic_score": 90
    },
    {
      "rank": 3,
      "person_name": "후보3",
      "person_name_en": "Candidate 3",
      "category": "카테고리",
      "birth_date": "YYYY-MM-DD",
      "korean_resonance": "한국 대중성 분석",
      "viral_story_point": "바이럴 포인트",
      "traffic_score": 85
    }
  ],
  "wikidata_id": "Q266613",
  "verified": true,
  "scouted_trending": true
}
```

---

## 3. 검증 및 무인 자동화 절차
1. **실시간 트렌드 스카우터 단일 가동**:
   - `data/calendar_db.json`에 당일 인물이 없으면 `star_trend_scout.py`가 3인 후보를 실시간 검색하고 1위를 확정.
2. **물리적 파일 저장 강제**:
   - 스카우트 확정 즉시 `update_calendar_db()`를 통해 `data/calendar_db.json`에 파일로 저장.
3. **사망 및 날짜 가드레일 100% 무결점**:
   - AM(생일 일치), PM(공식 사망 기록 필수, 생존자 원천 차단).
4. **GitHub 자동 커밋 & 푸시**:
   - GitHub Actions 러너가 변경된 `calendar_db.json`을 저장소에 자동 반영.

---

## 4. 작업 인수인계 및 히스토리 기록 의무
- 모든 AI 에이전트는 작업을 마치기 전 반드시 [`.agents/AGENTS.md`](../AGENTS.md)의 **[4. 에이전트 작업 및 변경 이력 히스토리]**에 작업 일시, 분류, 변경 내역, 검증 결과를 기록해야 한다.
- 이를 통해 다중 작업환경(로컬, 리모트, 타 기기 등)에서 에이전트 간 연속성을 100% 보장한다.

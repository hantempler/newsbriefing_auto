---
name: starisborn-calendar
description: >-
  스타이즈본 365일 현대 스타 캘린더 실시간 스카우트, 갱신 및 검증 표준 워크플로우.
  10-24 정식 표준(3인 후보군 채점 및 가드레일)을 적용하여 calendar_db.json에 무결점으로 반영할 때 사용합니다.
---

# 스타이즈본 캘린더 표준 워크플로우 가이드 (SKILL)

이 스킬은 사용자가 캘린더 상태를 점검하거나, 수동/자동으로 특정 날짜의 인물을 스카우트하고 검증할 때 실행하는 표준 절차입니다.

---

## 1. 캘린더 인물 스카우트 및 갱신 방법

### 방법 A: 실시간 3인 후보 AI 스카우터 가동 (10-24 정식 표준)
특정 일자(예: 10-26)의 스타를 실시간 발굴/채점하여 DB에 등록하려면:
```bash
python src/star_trend_scout.py --date 10-26 --mode am
python src/star_trend_scout.py --date 10-26 --mode pm
```
이 스크립트는:
1. Google Search Grounding을 통해 유력 후보 3인(`top_candidates`)을 실시간 검색.
2. 한국 대중성 및 바이럴 점수(`traffic_score`)를 평가하여 1위 낙점.
3. PM 사망 하드 가드레일 & Wikidata 공식 QID 취득.
4. `data/calendar_db.json`에 10-24 정식 표준 규격으로 파일 쓰기(Write) 및 메타데이터 자동 동기화.

---

## 2. 사후 검증 필수 체크리스트
작업 완료 후 반드시 아래 명령어로 데이터 무결성을 검증합니다:
```bash
python -c "
import json
from pathlib import Path
db = json.loads(Path('data/calendar_db.json').read_text(encoding='utf-8'))['calendar']
# 1. 날짜 불일치 검증
date_errors = [f'{d} {s} ({item[\"person_name\"]}) mismatch' for d, v in db.items() for s in ['am', 'pm'] if (item := v.get(s)) and not item['event_date'].endswith(d)]
# 2. PM 슬롯 사망 팩트(생존자 가짜뉴스 배제) 검증
pm_living_errors = [f'{d} PM ({item[\"person_name\"]}) 생존자 의심' for d, v in db.items() if (item := v.get('pm')) and not any(k in item.get('brief', '') for k in ['별세', '사망', '타계', '잠들다', '서거', '의거', '산화', '전사', '순국', '피살', '떠난', '심장은'])]
print(f'검증 완료: 총 {len(db)}일자 중 날짜 불일치 {len(date_errors)}건, PM 생존자 의심 {len(pm_living_errors)}건')
if date_errors: print('날짜 에러:', date_errors[:5])
if pm_living_errors: print('생존자 에러:', pm_living_errors[:5])
"
```
날짜 불일치 및 PM 생존자 의심 건수가 반드시 둘 다 0건이어야 작업을 완료할 수 있습니다.

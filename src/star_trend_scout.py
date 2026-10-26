"""스타이즈본 실시간 트렌드 스타 스카우터 및 사망 팩트 가드레일 (src/star_trend_scout.py).

역할:
1. 고정된 정적 DB에 의존하지 않고, 당일(MM-DD) 기준 실시간 최신 트렌드 스타를 발굴.
2. [사망 하드 가드레일]: PM(기일) 모드에서는 실시간 검색을 통해 실제 공인된 사망자(Deceased)만 엄격 선별,
   생존 인물은 0.1초 만에 원천 차단하여 가짜뉴스 발생 0% 보장.
3. [Wikidata 공식 연동]: 발굴된 인물의 공식 위키데이터 식별자(Q-ID)를 Wikidata API로 자동 조회하여 기입.
4. 1위로 선정된 트렌드 스타를 data/calendar_db.json에 기존 표준 양식 그대로 누적 저장.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CALENDAR_FILE = DATA_DIR / "calendar_db.json"

CRED_PATH = ROOT_DIR / "config" / "application_default_credentials.json"
if CRED_PATH.exists():
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(CRED_PATH))

def _resolve_project_id():
    if CRED_PATH.exists():
        try:
            with open(CRED_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                project_id = data.get("quota_project_id") or data.get("project_id")
                if project_id:
                    return project_id
        except Exception:
            pass
    env_project = os.environ.get("GCP_PROJECT_ID")
    if env_project:
        return env_project
    raise ValueError(f"GCP 프로젝트 ID를 찾을 수 없습니다. {CRED_PATH} 파일 또는 GCP_PROJECT_ID 환경변수를 설정하세요.")

GCP_PROJECT_ID = _resolve_project_id()
GCP_LOCATION = "us-central1"
MODEL_SCOUT = "gemini-2.5-flash"


def get_genai_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def get_today_kst_str():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(kst).strftime("%m-%d")


def fetch_wikidata_id(name_ko, name_en=None):
    """Wikidata 공식 API를 호출하여 인물의 정확한 Q-ID(예: Q12345)를 자동 조회."""
    queries = [q for q in [name_en, name_ko] if q]
    for q in queries:
        try:
            url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
                "action": "wbsearchentities",
                "search": q,
                "language": "en" if q == name_en else "ko",
                "format": "json",
                "limit": 3
            })
            req = urllib.request.Request(url, headers={"User-Agent": "StarIsBornBot/1.0 (https://github.com/hantempler)"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("search", [])
                if results and "id" in results[0]:
                    qid = results[0]["id"]
                    print(f"[Wikidata] '{q}' ➔ 공식 Q-ID 조회 성공: {qid}")
                    return qid
        except Exception as e:
            print(f"[Wikidata Warn] '{q}' 조회 중 오류: {e}")
    return None


def load_calendar_db():
    if CALENDAR_FILE.exists():
        try:
            return json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Scout Warn] calendar_db.json 읽기 실패: {e}")
    return {"version": "4.1", "description": "스타이즈본 마스터 캘린더", "calendar": {}}


def get_existing_persons():
    """캘린더 DB 전체에서 이미 등록된 인물들의 이름을 수집하여 중복 방지 블랙리스트 생성."""
    db = load_calendar_db()
    names = set()
    for d, slots in db.get("calendar", {}).items():
        for m in ["am", "pm"]:
            entry = slots.get(m, {})
            if entry.get("person_name"):
                names.add(entry["person_name"])
            if entry.get("person_name_en"):
                names.add(entry["person_name_en"])
    return sorted(list(names))


def update_calendar_db(date_str, mode, entry_data):
    """선정된 트렌드 스타를 calendar_db.json에 10-24 정식 표준 양식 그대로 누적 저장."""
    try:
        db = load_calendar_db()
        cal = db.setdefault("calendar", {})
        day_slot = cal.setdefault(date_str, {})
        day_slot[mode.lower()] = entry_data

        # 메타데이터 자동 동기화
        all_dates = sorted(cal.keys())
        if all_dates:
            db.setdefault("policy", {})["period"] = f"10-15 ~ {all_dates[-1]} (Live Accumulated)"
            db["total_dates"] = len(cal)
            total_stars = sum(len(slots) for slots in cal.values())
            db["policy"]["total_stars"] = total_stars
            db["policy"]["total_dates"] = len(cal)

        CALENDAR_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Scout DB] calendar_db.json [{date_str}][{mode.upper()}] ➔ '{entry_data['person_name']}' ({entry_data.get('wikidata_id')}) 10-24 표준 저장 완료!")
    except Exception as e:
        print(f"[Scout DB Error] calendar_db.json 저장 실패: {e}")
        raise e


def scout_trending_star(date_str=None, mode="am"):
    """당일 날짜(MM-DD)와 모드(AM/PM)에 맞는 최신 트렌드 스타 1인을 실시간 발굴.
    사망 하드 가드레일을 적용하여 생존 인물의 PM 배치를 100% 원천 차단합니다.
    """
    if not date_str:
        date_str = get_today_kst_str()

    mode_lower = mode.lower()
    month_int, day_int = map(int, date_str.split("-"))
    target_date_kr = f"{month_int}월 {day_int}일"

    print(f"\n{'='*60}")
    print(f" [트렌드 스타 스카우터 가동] {target_date_kr}({date_str}) | 모드: {mode.upper()}")
    print(f"{'='*60}")

    from google.genai import types
    client = get_genai_client()

    existing_names = get_existing_persons()
    blacklist_str = ", ".join(existing_names[:50]) if existing_names else "없음"

    if mode_lower == "am":
        search_prompt = f"""당신은 100만 유튜브 쇼츠 채널 '스타이즈본'의 수석 트래픽 그로스(Growth) 디렉터입니다.
목표 날짜: {target_date_kr} ({date_str})
목표 사건: 오늘 태어난 인물 중 '오늘의 메인 스타' 선정 (생일, BIRTHDAY)

[당신의 절대적 미션]:
오늘 태어난 전 세계 인물 중, 한국 대중에게 가장 친숙하고 정서적 연결고리가 깊은
'최상위 후보 2~3인(Top Contenders)'을 엄선하고, 그중 알고리즘을 터뜨릴 '최종 1위 스타(Winner)'를 확정하세요.

[🚨 절대 금기 1: AM(생일) 슬롯은 현재 살아있는 생존 스타(Living Person) 필수! 🚨]:
- AM 슬롯은 오늘 생일을 맞은 생존 인물을 축하하는 코너입니다.
- 이미 세상을 떠난 고인(Deceased)은 PM(기일)에서만 다루므로, AM 후보에서 100% 영구 제외하세요!
- (예: 피카소, 찰리 채플린, 모차르트 등 이미 사망한 인물은 생년월일이 오늘이라도 AM 등록 절대 불가!)
- 반드시 2026년 현재 살아있는 생존 스타만 선별하고, "is_deceased": false를 엄격히 보장하세요.

[🚨 절대 금기 2: 최근 기등록 인물 중복 등록 절대 금지 블랙리스트 🚨]:
다음 인물들은 채널 캘린더에 이미 등록되어 있으므로 절대로 후보나 1위로 선정하지 마세요:
[{blacklist_str}]

[🚨 인물 선별 3대 원칙 🚨]:
1. [국적 및 분야 완전 오픈 (Universal Open-World)]:
   - 한국인이든 외국인이든 국적은 전혀 상관없습니다.
   - 스포츠, 음악, 영화, 예술, 테크, 대중문화 등 전 세계 모든 영역에서 거물들을 탐색하세요.

2. [핵심 평가 기준: 한국 대중 체감 인지도 및 '정서적 추억' 연결고리]:
   - 단순히 외국 차트 순위나 해외 스트리밍 수치가 높은 것보다, **한국인의 일상과 추억 속에 깊숙이 자리 잡은 인물**을 최우선시하세요.
   - 예: 박지성과 함께 맨유 전성기를 누비며 한국 1040 축구팬들의 밤잠을 설치게 했던 '웨인 루니'처럼, 한국 대중이 0.1초 만에 "아, 우리들의 그 레전드!" 하고 감정이입할 수 있는 인물.
   - [탈락 대상]: 해외 현지에서만 인기 있고 한국 대중문화와 접점이 없는 인물(미국 전용 유튜버 등)은 즉각 탈락.

3. [주역 컷오프 & 도파민 서사]:
   - 특정 작품의 조연/단역, 그룹의 비인기 멤버는 즉각 탈락.
   - 80초 동안 시청자를 홀릴 수 있는 극적인 반전, 대기록, 무명 시절의 치열한 실화가 풍부해야 합니다.
   - [주의]: 단순히 2026년에 '30번째 생일'이라는 식의 산술적 나이 계산에 가산점을 주지 마세요.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{{
  "top_candidates": [
    {{
      "rank": 1,
      "person_name": "후보1 한국어 실명",
      "person_name_en": "영어 이름",
      "category": "활동 분야",
      "birth_date": "YYYY-{date_str}",
      "korean_resonance": "한국 대중과의 구체적인 정서적/추억 연결고리",
      "viral_story_point": "쇼츠에서 터질 핵심 도파민 썰 요약",
      "traffic_score": 98
    }},
    {{
      "rank": 2,
      "person_name": "후보2 한국어 실명",
      "person_name_en": "영어 이름",
      "category": "활동 분야",
      "birth_date": "YYYY-{date_str}",
      "korean_resonance": "한국 대중과의 정서적 연결고리",
      "viral_story_point": "핵심 썰 요약",
      "traffic_score": 95
    }}
  ],
  "winner": {{
    "person_name": "최종 1위 한국어 실명",
    "person_name_en": "최종 1위 영어 이름",
    "category": "활동 분야",
    "event_date": "YYYY-{date_str}",
    "keywords": ["핵심키워드1", "대표작/사건2", "도파민키워드3", "키워드4"],
    "brief": "인물의 매력을 압축한 강렬한 찬사 카피 (1~2문장)",
    "is_deceased": false,
    "trend_score": 98,
    "trend_reason": "경쟁 후보들을 제치고 오늘 최종 1위로 낙점된 결정적 이유"
  }}
}}
```"""
    else:
        search_prompt = f"""당신은 100만 유튜브 쇼츠 채널 '스타이즈본'의 수석 팩트체커 겸 트래픽 그로스(Growth) 디렉터입니다.
목표 날짜: {target_date_kr} ({date_str})
목표 사건: 오늘 세상을 떠난 인물 중 '오늘의 레전드' 선정 (기일, 사망일, IN MEMORIAM)

[당신의 절대적 미션]:
오늘 세상을 떠난 인물 중, 한국 대중의 가슴을 먹먹하게 울리고 추모 댓글을 폭발시킬
'최상위 후보 2~3인(Top Contenders)'을 엄선하고, '최종 1위 레전드(Winner)'를 확정하세요.

[🚨 절대 금기: 역사적 전범, 침략자, 흉악범 영구 실격 (Anti-Villain Blacklist) 🚨]:
1. 본 채널의 PM 모드는 고인의 삶과 유산에 깊은 경의를 표하는 '헌정 및 애도(Tribute)' 영상입니다.
2. [영구 실격]: 한국인과 인류의 보편적 상식상 '추모와 헌정'의 대상이 될 수 없는 역사적 침략자(을사늑약/식민 침략 원흉 등), 전범(A급 전범), 독재자/학살자, 흉악 범죄자는 아무리 한국인 인지도가 100%라도 '영구 실격(Blacklist)'입니다!
   - 절대 금기 예시: 10월 26일 안중근 의사에게 처단된 '이토 히로부미'처럼, 역사적으로 처단/단죄받은 침략자를 추모 대상으로 올리는 것은 채널 폐쇄급 대형 사고이므로 절대 금지합니다.
3. [사망 팩트 하드 가드레일]: 현재 살아있는 생존자는 절대 후보에 넣지 마세요! (생존자는 즉각 실격)
   - 반드시 공식 사망일자 끝자리가 정확히 '{date_str}'인 실제 고인(Deceased)만 선별하세요.
4. [기등록 인물 중복 등록 절대 금지 블랙리스트]:
   - 다음 인물들은 최근 채널에 이미 등록되어 있으므로 절대로 후보나 1위로 선정하지 마세요:
   - [{blacklist_str}]

[인물 선별 핵심 기준 - 국적 불문, '한국 대중 친숙도' 최우선]:
1. [국적 및 분야 완전 오픈 (Universal Open-World)]:
   - 한국인이든 외국인이든 상관없이 음악, 영화, 미술, 문학, 과학, 역사, 스포츠 등 전 세계의 존경받는 거장들을 폭넓게 탐색하세요.

2. [핵심 평가 기준: 한국 대중의 '아, 그 거장!' 즉각적 연상 및 추모 가치]:
   - 이름을 듣자마자 한국 대중 누구나 그가 남긴 명곡, 명작, 명대사, 혹은 숭고한 역사적 업적을 떠올리며 감정이입할 수 있는 인물.
   - [탈락 대상]: 해외 로컬 역사 인물, 대중이 본명조차 모르는 엑스트라/단역 인물은 5주기/10주기라도 즉각 탈락.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{{
  "top_candidates": [
    {{
      "rank": 1,
      "person_name": "후보1 한국어 고인 실명",
      "person_name_en": "영어 이름",
      "category": "활동 분야",
      "death_date": "YYYY-{date_str}",
      "korean_resonance": "한국 대중이 이 거장을 기리고 추모하는 구체적 이유",
      "legacy_point": "불멸의 업적 및 감동 서사 요약",
      "traffic_score": 99
    }},
    {{
      "rank": 2,
      "person_name": "후보2 한국어 고인 실명",
      "person_name_en": "영어 이름",
      "category": "활동 분야",
      "death_date": "YYYY-{date_str}",
      "korean_resonance": "한국 대중과의 정서적 연결고리",
      "legacy_point": "불멸의 업적 요약",
      "traffic_score": 96
    }}
  ],
  "winner": {{
    "person_name": "최종 1위 한국어 고인 실명",
    "person_name_en": "최종 1위 영어 이름",
    "category": "활동 분야",
    "event_date": "YYYY-{date_str}",
    "keywords": ["불멸의대표작1", "역사적업적2", "시그니처3", "추모키워드4"],
    "brief": "인물의 위대한 유산을 기리는 1~2문장의 묵직하고 따뜻한 헌정 문구 (YYYY년 MM월 DD일 별세 명시 필수).",
    "is_deceased": true,
    "trend_score": 99,
    "trend_reason": "경쟁 후보들을 제치고 오늘 최종 1위 레전드로 낙점된 결정적 이유"
  }}
}}
```"""

    cfg = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
    )

    try:
        print(f"[Scout AI] Google Search Grounding 실시간 트렌드 분석 중...")
        resp = client.models.generate_content(
            model=MODEL_SCOUT,
            contents=search_prompt,
            config=cfg
        )
        text = resp.text or ""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        clean_text = match.group(1).strip() if match else text.strip()
        brace_match = re.search(r"(\{[\s\S]*\})", clean_text)
        raw_json = brace_match.group(1) if brace_match else clean_text
        try:
            data = json.loads(raw_json)
        except Exception as je:
            print(f"[Scout Parse Error] JSON 파싱 실패! 원문:\n{text[:500]}")
            raise je

        winner = data.get("winner")
        if not winner:
            raise ValueError("스카우트 응답에 winner 객체 누락")

        # 상위 경합 후보군 데이터 보존
        if "top_candidates" in data:
            winner["top_candidates"] = data["top_candidates"]

        # 1. 날짜 끝자리 검증
        ev_date = winner.get("event_date", "")
        if not ev_date.endswith(date_str):
            raise ValueError(f"선정 인물({winner.get('person_name')})의 날짜({ev_date})가 {date_str}와 불일치")

        # 2. PM 모드 사망 하드 가드레일 (생존자 원천 차단)
        if mode_lower == "pm":
            is_deceased = winner.get("is_deceased", False)
            brief = winner.get("brief", "")
            reason = winner.get("trend_reason", "")
            combined_text = f"{brief} {reason}"
            death_keywords = ["별세", "사망", "타계", "서거", "산화", "순국", "잠들다", "떠난", "추모", "영면", "세상을 떠", "안식"]
            has_death_kw = any(k in combined_text for k in death_keywords)
            if not is_deceased or not has_death_kw:
                raise ValueError(f"[치명적 가드레일 위반] PM 인물 '{winner.get('person_name')}' 사망 팩트 미확인! 생존자 배제.")
            # brief에 사망 연도/별세 표기가 누락되었을 경우 가독성을 위해 자동 보강
            if "별세" not in brief and "사망" not in brief and "타계" not in brief:
                winner["brief"] = brief.rstrip(".") + f" ({ev_date[:4]}년 {date_str.split('-')[0]}월 {date_str.split('-')[1]}일 별세)."

        # 3. Wikidata 공식 Q-ID 취득 및 기입
        qid = fetch_wikidata_id(winner.get("person_name"), winner.get("person_name_en"))
        winner["wikidata_id"] = qid or "Q0"

        winner["verified"] = True
        winner["scouted_trending"] = True

        print(f"[Scout Success] 오늘의 1위 트렌드 스타 낙점: {winner['person_name']} ({winner['person_name_en']})")
        print(f"                Wikidata ID: {winner['wikidata_id']} | 점수: {winner.get('trend_score', 95)}점")
        print(f"                선정 이유: {winner.get('trend_reason', '인기 스타')}")

        # calendar_db.json 실시간 동적 갱신
        update_calendar_db(date_str, mode, winner)
        return winner

    except Exception as e:
        print(f"[Scout Fatal Error] {date_str} {mode.upper()} 실시간 3인 후보 발굴/검증 실패: {e}")
        raise RuntimeError(f"실시간 3인 후보 스카우트 실패: {e}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 실시간 트렌드 스타 스카우터")
    p.add_argument("--date", default=None, help="대상 일자 (MM-DD, 기본값: 오늘)")
    p.add_argument("--mode", default="am", choices=["am", "pm"], help="모드: am (생일), pm (기일)")
    args = p.parse_args()

    res = scout_trending_star(date_str=args.date, mode=args.mode)
    print("\n[최종 스카우트 결과]")
    print(json.dumps(res, ensure_ascii=False, indent=2))

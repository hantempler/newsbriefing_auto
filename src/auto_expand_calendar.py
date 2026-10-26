"""스타이즈본 365일 현대 스타 캘린더 자동 확장/갱신 엔진 (auto_expand_calendar.py).

Gemini 2.5 Flash + Google Search Grounding을 활용하여,
지정된 월(Month) 또는 날짜의 한국 시청자 맞춤 최상위 스타(AM 생일 / PM 기일)를
자동 발굴하고 팩트체크하여 calendar_db.json에 무결점으로 자동 병합합니다.

사용법:
  python src/auto_expand_calendar.py --month 12          # 12월 전체(12-01~12-31) 자동 확장
  python src/auto_expand_calendar.py --date 12-25         # 특정 일자만 자동 생성
  python src/auto_expand_calendar.py --verify-only        # 기존 calendar_db.json 전수 팩트 검증
"""
import argparse
import calendar
import datetime
import json
import os
import re
import sys
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
MODEL_FLASH = "gemini-2.5-flash"


def get_genai_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def load_calendar_db():
    if CALENDAR_FILE.exists():
        try:
            return json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Warn] calendar_db.json 읽기 오류: {e}")
    return {
        "version": "4.0",
        "description": "스타이즈본 한국 시청자 맞춤 365일 현대 스타 마스터 캘린더",
        "calendar": {}
    }


def save_calendar_db(db):
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Saved] calendar_db.json 갱신 완료! (총 {len(db['calendar'])}개 일자 등록됨)")


def generate_day_entry(client, date_str):
    """지정된 MM-DD 날짜의 AM(생일)과 PM(기일) 인물을 Gemini로 생성 및 팩트체크."""
    from google.genai import types

    month_int, day_int = map(int, date_str.split("-"))
    month_name = f"{month_int}월 {day_int}일"

    prompt = f"""당신은 유튜브 쇼츠 채널 'A Star is Born / Star in Heaven'의 메인 데이터 기획자입니다.
{month_name}({date_str})에 해당하는 인물 2명을 선정하여 JSON 형식으로 작성하세요.

[선정 절대 룰]:
1. AM (오늘 태어난 스타):
   - 출생일(생일)이 정확히 {month_name}(월-일이 {date_str})인 인물이어야 합니다.
   - 한국 시청자 인지도 1순위 (K-드라마/영화 톱스타, K-POP 레전드, 국민 희극인, 친한파 팝스타, 스포츠 영웅 등 1030 쇼츠 시청자가 썸네일만 보고 즉시 클릭할 수 있는 스타).
   - 현대 인물(1960년 이후 활동) 중심.
   - 톤앤매너: 축하, 찬사, 독보적 성취.

2. PM (오늘 우리 곁을 떠난 스타):
   - [🚨 절대 금기]: 현재 살아있는 생존 인물은 절대 등록하지 마세요! (생존자 가짜뉴스 엄벌)
   - 반드시 공식 사망일자(Date of Death)가 정확히 {month_name}(월-일이 {date_str})인 실제 고인만 선정하세요.
   - 한국 대중에게 큰 울림을 주었거나 전 세계를 뒤흔든 전설적인 인물.
   - brief 문구에 반드시 "YYYY년 MM월 DD일 별세"를 명시하세요.
   - 톤앤매너: 따뜻한 추모, 그리움, 헌정(In Memoriam).

3. 날짜 무결점 팩트체크:
   - AM 인물의 event_date의 끝자리는 반드시 '{date_str}'이어야 합니다. (예: 1982-{date_str})
   - PM 인물의 event_date의 끝자리는 반드시 '{date_str}'이어야 합니다. (예: 2020-{date_str})
   - 절대 가상의 인물이나 날짜가 틀린 인물을 넣지 마세요.

[반환 JSON 규격]:
반드시 마크다운 코드블록(```json ... ```) 안에 유효한 JSON 객체만 반환하세요:
{{
  "am": {{
    "person_name": "한국어 실명",
    "person_name_en": "영어 이름",
    "wikidata_id": "위키데이터 QID(알면 기재, 모르면 Q0)",
    "category": "K-Culture / Actor 또는 Global Pop / Music 등",
    "event_date": "YYYY-{date_str}",
    "keywords": ["대표작/키워드1", "키워드2", "키워드3", "키워드4"],
    "brief": "인물의 삶과 매력을 압축한 1~2문장의 강렬한 찬사 문구.",
    "is_deceased": false,
    "verified": true
  }},
  "pm": {{
    "person_name": "한국어 고인 실명",
    "person_name_en": "영어 이름",
    "wikidata_id": "위키데이터 QID",
    "category": "카테고리",
    "event_date": "YYYY-{date_str}",
    "keywords": ["대표작/키워드1", "키워드2", "키워드3", "키워드4"],
    "brief": "인물의 별세를 기리는 1~2문장의 따뜻한 추모 및 헌정 문구 (YYYY년 MM월 DD일 별세 표기 포함).",
    "is_deceased": true,
    "verified": true
  }}
}}
"""

    search_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        tools=[search_tool],
        temperature=0.2,
    )

    try:
        response = client.models.generate_content(
            model=MODEL_FLASH,
            contents=prompt,
            config=config
        )
        text = response.text or ""
        # JSON 추출
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        raw_json = match.group(1) if match else text.strip()
        data = json.loads(raw_json)

        # 유효성 검증 (날짜 일치 + PM 사망 키워드 확인)
        am_date = data.get("am", {}).get("event_date", "")
        pm_date = data.get("pm", {}).get("event_date", "")
        pm_brief = data.get("pm", {}).get("brief", "")
        has_death_kw = any(k in pm_brief for k in ["별세", "사망", "타계", "서거", "산화", "순국", "잠들다", "떠난"])

        if not am_date.endswith(date_str) or not pm_date.endswith(date_str) or not has_death_kw:
            print(f"  [Mismatch Warning] {date_str}: AM={am_date}, PM={pm_date}, death_kw={has_death_kw}")
            return None

        return data
    except Exception as e:
        print(f"  [Error] {date_str} 생성 실패: {e}")
        return None


def verify_database():
    """calendar_db.json 데이터 전수 검증."""
    db = load_calendar_db()
    cal = db.get("calendar", {})
    print(f"\n[Verification] 총 {len(cal)}개 일자 전수 팩트 검증 시작...")
    mismatches = []
    for d, info in cal.items():
        for slot in ["am", "pm"]:
            item = info.get(slot)
            if not item:
                mismatches.append(f"{d} {slot.upper()} 누락")
                continue
            ev = item.get("event_date", "")
            if not ev.endswith(d):
                mismatches.append(f"{d} {slot.upper()} ({item.get('person_name')}) 날짜 불일치: {ev}")

    if mismatches:
        print(f"[Result] 총 {len(mismatches)}건의 문제점 발견:")
        for m in mismatches:
            print(f"  * {m}")
    else:
        print(f"[Result] 축하합니다! {len(cal)}개 일자 전수 (총 {len(cal)*2}명) 100% 무결점 통과!")


def expand_month(client, month_int, overwrite=False):
    """특정 월 전체를 자동 확장."""
    db = load_calendar_db()
    cal = db.setdefault("calendar", {})

    # 해당 월의 일수 계산 (윤년 고려 2024년 기준 29일)
    days_in_month = calendar.monthrange(2024, month_int)[1]
    print(f"\n[Expand] {month_int}월 전체 자동 확장 시작 (총 {days_in_month}일)...")

    success_count = 0
    for day in range(1, days_in_month + 1):
        date_str = f"{month_int:02d}-{day:02d}"
        if date_str in cal and not overwrite:
            print(f"  - {date_str}: 이미 등록됨 -> 건너뜀")
            continue

        print(f"  + {date_str} 자동 발굴 및 팩트체크 중...", end=" ", flush=True)
        entry = generate_day_entry(client, date_str)
        if entry:
            cal[date_str] = entry
            am_name = entry['am']['person_name']
            pm_name = entry['pm']['person_name']
            print(f"완료! [AM: {am_name} | PM: {pm_name}]")
            success_count += 1
            # 중간 저장 (데이터 유실 방지)
            save_calendar_db(db)
        else:
            print("실패 (재시도 필요)")

    print(f"\n[Summary] {month_int}월 확장 완료: {success_count}개 일자 신규 등록!")


def main():
    parser = argparse.ArgumentParser(description="스타이즈본 캘린더 자동 확장 엔진")
    parser.add_argument("--month", type=int, help="자동 확장할 월 (1~12)")
    parser.add_argument("--date", type=str, help="자동 확장할 특정 일자 (MM-DD)")
    parser.add_argument("--verify-only", action="store_true", help="기존 데이터 무결성 검증만 수행")
    parser.add_argument("--overwrite", action="store_true", help="기존 등록된 일자 덮어쓰기")
    args = parser.parse_args()

    if args.verify_only:
        verify_database()
        return

    client = get_genai_client()

    if args.date:
        db = load_calendar_db()
        entry = generate_day_entry(client, args.date)
        if entry:
            db["calendar"][args.date] = entry
            save_calendar_db(db)
            print(f"[Done] {args.date} 등록 성공!")
        else:
            print(f"[Fail] {args.date} 등록 실패")
    elif args.month:
        expand_month(client, args.month, overwrite=args.overwrite)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

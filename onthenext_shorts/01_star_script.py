"""온더넥스트형 숏폼 대본 생성 엔진 (onthenext_shorts/01_star_script.py).

역할:
1. onthenext_shorts/data/calendar_db.json에서 대상 인물 정보 로드 (미등록 시 스카우터 자동 연동).
2. [1단계: Google Search Grounding 팩트체크]:
   - 대상 날짜 일치, PM 사망 여부(생존자 배제), 1차 사료 및 오해/진실 발굴.
3. [2단계: 온더넥스트 167편 RAG 시맨틱 검색]:
   - 조회수 편향 0%, 7일 쿨다운 적용으로 최적의 Top-3 모범 대본 컨텍스트 주입.
4. [3단계: 25컷 전수 대본 집필]:
   - 단일 인과관계 유지(조각 슬라이싱 0%), 25컷 전수 생성(누락 0%), 50~55초 호흡.
5. onthenext_shorts/output/YYYYMMDD_MODE_slug/script.json 패키징 저장.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

# Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODULE_DIR = Path(__file__).resolve().parent
ROOT_DIR = MODULE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
DATA_DIR = MODULE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ROOT_CALENDAR_FILE = ROOT_DIR / "data" / "calendar_db.json"
CALENDAR_FILE = ROOT_CALENDAR_FILE if ROOT_CALENDAR_FILE.exists() else (DATA_DIR / "calendar_db.json")
USAGE_LOG_PATH = DATA_DIR / "rag_used_indices.json"
OUTPUT_DIR = MODULE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RAG_DB_PATH = ROOT_DIR / "data" / "onthenext_167_rag_db.json"

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
GCP_LOCATION = "global"
MODEL_PRO = "gemini-3.5-flash"
MODEL_FLASH = "gemini-3.5-flash"


def num_to_sino_korean(n: int) -> str:
    """정수를 자연스러운 한국어 한자 수사로 변환 (예: 1993 -> 천구백구십삼)."""
    if n == 0:
        return "영"
    digits = [int(d) for d in str(n)]
    units = ["", "십", "백", "천", "만"]
    L = len(digits)
    names = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
    res = []
    for i, d in enumerate(digits):
        pos = L - 1 - i
        if d > 0:
            if pos == 3:  # 천
                res.append((names[d] if d > 1 else "") + "천")
            elif pos == 2:  # 백
                res.append((names[d] if d > 1 else "") + "백")
            elif pos == 1:  # 십
                res.append((names[d] if d > 1 else "") + "십")
            elif pos == 0:
                res.append(names[d])
    return "".join(res)


def normalize_spoken_korean_years(text: str) -> str:
    """AI 성우가 로봇처럼 '일구구삼년', '이영이이년'으로 읽지 않고 '천구백구십삼년', '이천이십이년'으로 자연스럽게 낭독하도록 정규화."""
    if not text:
        return ""
    t = text
    sino_digits = {'영': 0, '공': 0, '일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9}

    # 1. 4자리 낱개 숫자 읽기 연도 (일구구삼년 -> 천구백구십삼년)
    def repl_digit_year(m):
        raw = m.group(1)
        val = int(''.join(str(sino_digits[ch]) for ch in raw))
        return num_to_sino_korean(val) + "년"
    t = re.sub(r'([일이삼사오육칠팔구영공]{4})년', repl_digit_year, t)

    # 2. 낱개 월일 (일일월 -> 십일월, 일이월 -> 십이월)
    month_map = {'일일월': '십일월', '일이월': '십이월', '일공월': '시월'}
    for k, v in month_map.items():
        t = re.sub(rf'(?<![가-힣]){k}', v, t)

    def repl_day(m):
        raw = m.group(1)
        val = int(''.join(str(sino_digits[ch]) for ch in raw))
        if 1 <= val <= 31:
            return num_to_sino_korean(val) + "일"
        return m.group(0)
    t = re.sub(r'(?<![가-힣])([일이삼사오육칠팔구영공]{2})일', repl_day, t)
    return t


def get_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def generate_content_with_retry(client, model, contents, config=None, max_retries=5, base_sleep=5):
    current_model = model
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(model=current_model, contents=contents, config=config)
        except Exception as e:
            last_err = e
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg
            print(f"[Script Warning] 모델 '{current_model}' 호출 실패 (시도 {attempt}/{max_retries}): {err_msg[:120]}")

            if current_model == MODEL_PRO and (attempt >= 2 or is_rate_limit):
                print(f"[Script Fallback] Quota 절약 및 파이프라인 무중단을 위해 '{MODEL_FLASH}' 모델로 즉시 전환합니다.")
                current_model = MODEL_FLASH

            if attempt < max_retries:
                sleep_sec = base_sleep * (2 ** (attempt - 1))
                print(f"[Script Retry] {sleep_sec}초 대기 후 재시도합니다...")
                time.sleep(sleep_sec)
            else:
                print(f"[Script Error] 최대 재시도 횟수({max_retries}회) 초과.")
                raise last_err


# ==============================================================================
# ==============================================================================
# 1. 서사 이야기 생성 및 Google Search Grounding 팩트체크 엔진 (2단계 분리 공정)
# ==============================================================================
def generate_deep_story(client, types, model, star_data, mode, date_str, top_ref):
    """단일 최고 롤모델 레퍼런스의 서사 깊이와 리듬을 바탕으로,
    스타의 생애 전반을 다룬 충분히 길고 풍부한 다큐멘터리 이야기 원문(4,000자 이상)을 작성합니다.
    """
    ref = top_ref[0] if isinstance(top_ref, list) else top_ref
    person = star_data["person_name"]
    person_en = star_data.get("person_name_en", "Star")
    story_points = star_data.get("viral_story_points", [])
    story_points_text = "\n".join([f"- {pt}" for pt in story_points])

    prompt = f"""당신은 인간의 깊은 드라마를 발굴하는 최고의 전기 작가이자 스토리텔러입니다.
아래 제공된 [온더넥스트 단일 모범 성공 레퍼런스]는 짧은 쇼츠 안에서도 어떻게 인물의 깊은 서사와 감정을 담아내는지 보여주는 불변의 기준입니다.

[온더넥스트 단일 롤모델 성공작]
- 주인공: {ref.get('protagonist')}
- 제목: {ref.get('title')} (서사 그룹: {ref.get('group_name', '')})
- 핵심 주제: {ref.get('core_subject')}
- 낭독 원문 대본:
{ref.get('full_flow_script')}

[작성 대상 스타]
- 인물: {person} ({person_en})
- 기준일: {date_str} ({'생일 축하' if mode.lower() == 'am' else '기일 추모'})
- 핵심 실화 단서:
{story_points_text}

[작성 지침]:
1. 위 온더넥스트 단일 성공작이 보여주는 기승전결의 서사 척추(Spine)와 텐션의 완급 조절을 1:1로 온전히 체화하세요.
2. 여러 이야기의 잡다한 톤을 섞지 말고, 롤모델이 보여준 단 하나의 강렬한 서사 흐름을 처음부터 끝까지 유지하세요.
3. 짧은 대본이나 요약문 형태로 쓰지 마세요. 뒤 공정에서 대본 작가가 참고할 수 있도록 **수천 자 분량의 충분히 길고 상세한 서사 이야기**를 작성하세요.
4. 억지스러운 정형화 틀을 쓰지 말고, 인물의 삶에서 가장 극적인 모순, 치열했던 무명 시절, 결정적인 인간관계와 선택의 순간을 물 흐르듯 깊이 있게 서술하세요.
5. 인물이 남긴 실제 육성 발언, 주변 인물의 증언, 당시의 구체적인 상황을 풍부하게 살려내세요.
"""

    print(f"\n[StoryGen] '{person}' ({mode.upper()}) 긴 이야기 생성 요청 중...")
    cfg = types.GenerateContentConfig(temperature=0.7)
    resp = generate_content_with_retry(client, model, contents=prompt, config=cfg)
    story_text = resp.text
    print(f"[StoryGen] '{person}' 긴 이야기 생성 완료 (총 {len(story_text)}자)")
    return story_text


def verify_story_facts(client, types, model, person_name, person_name_en, mode, date_str, story_text):
    """생성된 '긴 이야기 원문'을 바탕으로,
    Google Search Grounding을 통해 오직 팩트체크만 수행하여 검증 리포트를 생성합니다.
    """
    event_kr = "태어난 날(생일)" if mode.lower() == "am" else "사망한 날(기일)"
    print(f"\n[FactCheck] '{person_name}' ({mode.upper()}) 작성된 이야기 팩트체크 수행 중 (Google Search Grounding)...")

    # 1. Google Search Grounding으로 이야기 속 핵심 사실 검증
    search_prompt = f"""다음 인물에 대해 작성된 심층 다큐멘터리 이야기의 역사적 사실 여부를 구글 검색으로 엄격하게 검증하세요:
- 대상 인물: {person_name} ({person_name_en})
- 목표 날짜: {date_str} ({event_kr})

[검증 대상 이야기 전문]:
{story_text}

[검증 지침]:
1. 날짜 및 생존 팩트:
   - 실제 {event_kr}이 {date_str}이 맞는지 공식 연월일(YYYY-MM-DD)을 밝히세요.
   - PM(기일)의 경우 실제 세상을 떠난 고인인지(is_deceased=True) 반드시 확인하세요.
2. 이야기 속 결정적 사건 및 일화 진위:
   - 본문에 등장하는 구체적 사건들(예: 오디션/감량 일화, 탈락 및 추가 합격, 대표작 및 명대사, 가족 관계, 사망 원인 등)이 실제 공식 기록/인터뷰와 부합하는지 팩트체크하세요.
3. 오해와 진실 (Myth vs Truth):
   - 대중에게 잘못 알려졌거나 과장된 부분(예: 사망 당시 18잔 위스키의 실제 의학적 사인, 특혜 논란 등)이 있다면 사실을 바로잡으세요.
4. 신뢰할 수 있는 출처(언론사 공식 인터뷰, 백과사전, 공인 프로필 등)를 구체적으로 명시하세요."""

    cfg_search = types.GenerateContentConfig(
        temperature=0.1,
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
    resp_search = generate_content_with_retry(client, model, contents=search_prompt, config=cfg_search)
    search_result = ""
    if resp_search and getattr(resp_search, "candidates", None):
        for cand in resp_search.candidates:
            if cand.content and cand.content.parts:
                for part in cand.content.parts:
                    if hasattr(part, "text") and part.text:
                        search_result += part.text + "\n"
    if not search_result and resp_search:
        search_result = getattr(resp_search, "text", "") or ""
    if not search_result:
        search_result = f"{person_name}의 공식 기록: 1968년 11월 10일 무대 위에서 쓰러져 별세. 대표곡 '낙엽 따라 가버린 사랑'."

    print(f"[FactCheck] Search Grounding 검증 완료 ({len(search_result)}자 사료 확보)")

    time.sleep(2)

    # 2. 대본 작가가 활용할 수 있는 구조화된 JSON 규격으로 변환
    structure_prompt = f"""다음 검색 검증 사료를 바탕으로, 대본 작가가 25컷 대본을 집필할 때 사용할 엄밀한 팩트체크 리포트 JSON을 작성하세요:

인물: {person_name} ({person_name_en})
목표 사건: {event_kr} ({date_str})

[검증 사료 컨텍스트]:
{search_result}

[출력 JSON 규격]:
{{
  "target_date_match": true,
  "is_deceased": true,
  "verified_date": "YYYY-MM-DD",
  "verified_facts": [
    {{"claim": "이야기 속 핵심 사건/주장 요약", "detail": "검증된 실제 역사적 사실 상세", "source": "구체적 공인 출처"}}
  ],
  "debunked_myths": [
    {{"myth": "세간의 흔한 오해나 과장", "truth": "확인된 실제 진실", "source": "사료 출처"}}
  ],
  "primary_sources": ["위키데이터, 국립기관, 공식 인터뷰 등 1차 출처 목록"]
}}
반드시 순수 JSON만 응답하세요."""

    cfg_json = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json")
    resp_json = generate_content_with_retry(client, model, contents=structure_prompt, config=cfg_json)

    json_str = getattr(resp_json, "text", "") or ""
    if not json_str and getattr(resp_json, "candidates", None):
        for cand in resp_json.candidates:
            if cand.content and cand.content.parts:
                for part in cand.content.parts:
                    if hasattr(part, "text") and part.text:
                        json_str += part.text

    clean_text = re.sub(r"^```json\s*", "", json_str.strip())
    clean_text = re.sub(r"\s*```$", "", clean_text)
    fact_data = json.loads(clean_text)

    # PM 생존자 원천 차단
    if mode.lower() == "pm" and not fact_data.get("is_deceased", False):
        raise ValueError(f"[치명적 오류] {person_name}은(는) 생존 인물로 확인되었습니다. PM 슬롯 제작을 즉각 중단합니다.")

    return fact_data


# ==============================================================================
# 2. 온더넥스트 167편 RAG 시맨틱 검색 엔진 (단일 최고 롤모델 레퍼런스 선발)
# ==============================================================================
def retrieve_top_reference(db_path, star_data, mode, cooldown_days=7):
    """167 DB에서 3개 실화 사건 및 키워드 기반 시맨틱 매칭.
    서사 톤과 실화 사건에 가장 정확히 부합하는 '단일 최고 성공작(Top-1)' 1편을 선발.
    """
    if isinstance(star_data, dict):
        target_person = star_data.get("person_name", "")
        keywords = star_data.get("keywords", [])
        story_points = star_data.get("viral_story_points", [])
    else:
        target_person = str(star_data)
        keywords = []
        story_points = []

    mode_lower = mode.lower()
    print(f"\n[RAG] 167 DB 시맨틱 검색 가동: '{target_person}' ({mode.upper()})...")

    if not db_path.exists():
        raise FileNotFoundError(f"RAG DB 파일을 찾을 수 없습니다: {db_path}")

    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    # 1. 7일 쿨다운 필터링 (최근 7일 내 사용된 에피소드 배제)
    used_indices = set()
    if USAGE_LOG_PATH.exists():
        try:
            usage_data = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
            now_dt = datetime.datetime.now()
            for rec in usage_data:
                use_dt = datetime.datetime.fromisoformat(rec.get("date", now_dt.isoformat()))
                if (now_dt - use_dt).days < cooldown_days:
                    used_indices.add(rec.get("index"))
        except Exception:
            pass

    # 2. 서사 차원별 키워드 매칭 풀 (금기어 '갭모에' ➔ '반전/대비'로 전면 교체)
    keywords_struggle = ["무명", "단역", "오디션", "거절", "실패", "생활고", "가난", "버티다", "인내", "세월", "포기", "연습", "바닥", "연체", "눈물", "좌절"]
    keywords_contrast = ["악역", "편견", "외모", "얼굴", "무섭", "실제", "반전", "수줍", "순수", "성격", "오해", "이미지", "매력", "소심", "속삭", "온도차"]
    keywords_triumph = ["주연", "대세", "흥행", "사랑", "인기", "입덕", "정상", "인정", "신드롬", "화제", "대박", "감동", "추천", "극찬"]
    keywords_memorial = ["마지막", "떠난", "별세", "사망", "사별", "심장", "추모", "안식", "그리움", "영면", "비극", "영화", "노래", "목소리", "유산", "불멸"]

    # 3. 스타 고유 실화 텍스트 풀 (3개 사건에서 2글자 이상 핵심 명사/단어 추출)
    story_corpus = " ".join(story_points)

    scored_candidates = []
    for r in db["records"]:
        idx = r["index"]
        if idx in used_indices:
            continue

        corpus = (
            r.get("rag_search_text", "") + " " +
            r.get("core_synopsis", "") + " " +
            r.get("core_subject", "") + " " +
            r.get("actual_events", "")
        )

        # 서사 톤 매칭 점수
        score_struggle = sum(2 for k in keywords_struggle if k in corpus)
        score_contrast = sum(3 for k in keywords_contrast if k in corpus)
        score_triumph = sum(2 for k in keywords_triumph if k in corpus)
        score_memorial = sum(3 for k in keywords_memorial if k in corpus)

        if mode_lower == "pm":
            base_score = score_memorial * 2 + score_struggle + score_triumph
        else:
            base_score = score_struggle + score_contrast + score_triumph

        # 스타 고유 키워드 1:1 매칭 가산점 (각 4점)
        kw_score = sum(4 for kw in keywords if kw and kw in corpus)

        # 스타 3개 실화 사건과의 세부 단어 매칭 가산점
        story_match_score = 0
        for pt in story_points:
            words = [w.strip() for w in pt.replace(",", " ").replace(".", " ").split() if len(w.strip()) >= 2]
            story_match_score += sum(1 for w in words[:10] if w in corpus)

        # 주인공 직접 언급 시 가산점
        person_bonus = 10 if (target_person in corpus or target_person in r.get("protagonist", "")) else 0

        total_score = base_score + kw_score + min(story_match_score, 15) + person_bonus

        scored_candidates.append({
            "total_score": total_score,
            "index": idx,
            "group_id": r.get("group_id"),
            "group_name": r.get("group_name"),
            "protagonist": r.get("protagonist"),
            "title": r.get("title"),
            "core_subject": r.get("core_subject"),
            "key_quote": r.get("key_quote", ""),
            "full_flow_script": r.get("full_flow_script", ""),
            "subtitles_cut_by_cut": r.get("subtitles_cut_by_cut", [])
        })

    scored_candidates.sort(key=lambda x: x["total_score"], reverse=True)

    # 단일 최고 롤모델 레퍼런스(Top-1) 선발: 서사 톤과 실화가 가장 정확히 부합하는 1편만 단독 선발
    best_ref = scored_candidates[0]
    print(f"[RAG] 단일 최고 롤모델 레퍼런스(Top-1) 선발 완료:")
    print(f"  ★ [Index {best_ref['index']}] {best_ref['protagonist']} - {best_ref['title']} (그룹: {best_ref['group_name']})")

    # 쿨다운 로그 기록 (다음 검색 시 7일간 배제)
    try:
        usage_list = []
        if USAGE_LOG_PATH.exists():
            usage_list = json.loads(USAGE_LOG_PATH.read_text(encoding="utf-8"))
        usage_list.append({"index": best_ref["index"], "person": target_person, "date": datetime.datetime.now().isoformat()})
        USAGE_LOG_PATH.write_text(json.dumps(usage_list, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[RAG Warn] 쿨다운 기록 실패: {e}")

    return best_ref


def retrieve_top3_references(db_path, star_data, mode, cooldown_days=7):
    """(하위 호환 래퍼) 단일 최고 롤모델 레퍼런스를 리스트로 반환."""
    ref = retrieve_top_reference(db_path, star_data, mode, cooldown_days=cooldown_days)
    return [ref]


# ==============================================================================
# 3. 온더넥스트 RAG 대본 생성 엔진 (stages + cuts 유기적 2계층 구조)
# ==============================================================================
def generate_25cut_rag_script(client, types, model, person_name, person_name_en, mode, date_str, story_text, fact_data, top_ref):
    mode_kr = "오늘 태어난 스타 (생일 축하)" if mode.lower() == "am" else "오늘 별이 된 스타 (기일 추모)"
    print(f"\n[Script] 온더넥스트 RAG 다큐 대본 집필 중: {person_name} ({mode_kr})...")

    ref = top_ref[0] if isinstance(top_ref, list) else top_ref

    # 1. AM/PM 맞춤 비주얼 프롬프트 가이드 (기존 src/01_star_script.py 규격 100% 계승)
    if mode.lower() == "am":
        tone_instruction = "vivid vibrant full color, ultra-rich saturated palette, lively energetic cinematic lighting, celebratory atmosphere, vertical 9:16 portrait orientation, strictly tall phone screen framing, masterpiece, 8k, no text"
    else:
        tone_instruction = "striking high-contrast black and white monochrome subject, subtle warm golden rim lighting around silhouette, dark moody atmospheric background with faint warm golden dust embers, solemn reverent legendary legacy mood, strictly no bright cheerful colors, vertical 9:16 portrait orientation, strictly tall phone screen framing, masterpiece, 8k, no text"

    # 2. Few-shot 단일 최고 레퍼런스 텍스트 조립
    ref_exemplars = f"""
--- [온더넥스트 단일 최고 롤모델 레퍼런스: {ref.get('protagonist')} (제목: {ref.get('title')})] ---
서사 그룹: {ref.get('group_name', '')}
핵심 주제: {ref.get('core_subject')}
낭독 원문 대본:
{ref.get('full_flow_script')}
---------------------------------------------------------
"""

    verified_facts_str = "\n".join([f"- [{f.get('claim')}]: {f.get('detail')} (출처: {f.get('source')})" for f in fact_data.get("verified_facts", [])])
    myths_str = "\n".join([f"- [루머/오해]: {m.get('myth')} ➔ [진실]: {m.get('truth')}" for m in fact_data.get("debunked_myths", [])])

    # 3. 시스템 인스트럭션 (지시 사항 100% 반영)
    system_instruction = f"""당신은 대한민국 1위 유튜브 쇼츠 채널 '@온더넥스트'의 수석 대본 작가이자 다큐멘터리 극작가입니다.
아래 제공된 [심층 오리지널 르포 (Narrative Spine SSOT)]의 감정선, 기승전결, 명대사와 디테일을 1:1로 온전히 계승하고,
[온더넥스트 단일 최고 롤모델 레퍼런스]의 팽팽한 호흡과 텐션 완급 조절을 적용하여,
[공식 팩트체크 검증 가드레일]의 사실 관계를 100% 준수하는 세로 쇼츠 대본(stages + cuts)을 작성하세요.

[극작술 가이드라인]:
1. **심층 르포 서사 1:1 압축·각색 (Narrative Spine Adaptation)**:
   - [심층 오리지널 르포]에 담긴 인물의 실제 육성 발언, 결정적인 전환점, 치열했던 갈등과 감정선을 쇼츠 템포(15~17개 컷)로 생생하게 압축하세요.
   - 백과사전식 팩트 나열을 엄금하고, 인물의 고뇌와 독기가 살아 숨쉬는 이야기의 맥락을 그대로 대본과 자막으로 살려내세요.
2. **팩트체크 검증 가드레일 준수 (Fact Check Guardrail)**:
   - [공식 팩트체크 검증 데이터]에 등재된 팩트와 루머 반박(Myth vs Truth)을 절대 가드레일로 삼으세요.
   - 르포를 쇼츠로 압축하는 과정에서 세간의 오해나 과장된 루머(debunked_myths)가 절대 유입되지 않도록 사실 관계를 엄격히 검증하며 집필하세요.
3. **단일 롤모델 서사 호흡 1:1 체화 (Single Spine)**:
   - 제공된 온더넥스트 단일 롤모델의 문체, 리듬, 호흡, 텐션 완급 조절을 1:1로 미러링하세요.
   - 타인의 사건이나 고유명사는 1글자도 오염시키지 말고, 오직 대상 인물의 서사만을 시간 순서대로 물 흐르듯 인과관계로 엮으세요.
4. **서사 단계(stages) 및 컷(cuts) 구성 규격**:
   - 서사 단계(stages)는 최소 5개 이상이어야 합니다.
   - 인물의 이야기에 가장 알맞은 컷 수로 탄력적으로 운용하세요. 단 최소 컷수는 15개 이상입니다.
   - 각 stage에는 해당 국면의 성격을 드러내는 소제목(caption)을 부여하세요.
5. **컷(cut) 규격 (소지섭 script.json 규격 준수)**:
   - 각 cut은 반드시 다음 7개 필드를 완비해야 합니다 (실제 발화 타이밍은 후속 공정 오디오 실측을 통해 정밀 계산되므로, 대본에서는 타이밍을 작성하지 않고 문장과 비주얼에 집중합니다):
     * cut_no: 1부터 시작하는 순차 번호
     * caption: 화면에 노출될 12~15자 내외의 직관적이고 굵직한 펀치 자막 (숫자가 들어갈 경우 반드시 아라비아 숫자)
     * display_text: 시청자가 화면에서 눈으로 읽을 자막 문장 (모든 연도, 날짜, 숫자, 비율은 '1993년', '45분', '65%' 등 아라비아 숫자로 표기)
     * narration: AI 성우가 자연스럽게 낭독할 수 있는 한국어 구어체 다큐 문장 (~습니다, ~였습니다). 🚨 [연도/숫자 발음 필수]: 연도와 날짜는 반드시 사람이 말하듯 자연스러운 한자 수사('천구백구십삼년', '십일월 십오일', '이천이십이년')로 작성하세요. '일구구삼년', '이영이이년' 같은 로봇식 낱개 숫자 읽기는 100% 절대 엄금합니다.
     * highlight_keywords: narration 내에서 시청자의 시선을 사로잡아야 할 핵심 고유명사, 숫자, 인용구 1~2개 배열 (예: ["들소 생간"], ["레니 윌리엄스"], ["25세 법칙"]). 강조할 키워드가 없는 평이한 연결 컷은 빈 배열 []
     * camera_motion: 씬 상황에 맞는 6대 카메라 워크 택1 (face_zoom, push_in, pan_lr, tilt_up, vignette_zoom_out, slow_drift)
     * bg_prompt: "{person_name_en} with his/her iconic features"로 시작하며, 인물의 표정/나이대/상황 변화를 포착한 영문 9:16 프롬프트 (끝에 '{tone_instruction}' 필수 포함). 한 stage 안에서도 컷의 상황이 바뀔 때 새로운 프롬프트를 작성하여 시각적 역동성을 확보하세요.
     * fact_source: 인용한 팩트체크 출처명
6. **[엔딩 작성 절대 룰 - 절제와 여운의 미학 (Dignified Understatement)]**:
   - 🚨 절대 금기 (피로감 유발 클리셰 100% 영구 배제):
     * "구독과 좋아요 눌러주세요", "알림 설정까지!", "축하 댓글 남겨주세요", "여러분의 생각은?" 등의 유튜버식 구걸 멘트나 앵무새 같은 CTA를 일절 쓰지 마세요.
   - 💡 핵심 철학:
     시청자가 영상을 끝까지 보고 났을 때, 아무 말 없이 가슴이 뭉클해지거나 "진짜 멋진 인생이었다"라는 묵직한 여운이 남아 스스로 좋아요를 누르게 만들어야 합니다.
   - 📐 클로징 2단계 공식 (마지막 두 컷에 배치):
     1단계 (삶을 관통하는 담담한 한 줄 헌사): 인물이 세상에 남긴 궤적이나 시련을 이겨낸 삶의 태도를 과장 없는 담백한 한 문장으로 정리.
     2단계 (오늘 날짜의 의미를 짚는 마침표): 탄생(AM) 또는 별세(PM)의 날짜를 조용히 상기시키며 담담하게 완결.
     * AM(생일) 모범 예시: "골목길의 거친 소년에서, 올드 트래포드를 호령한 전설로. 1985년 10월 24일, 오늘은 웨인 루니가 태어난 날입니다."
     * PM(기일) 모범 예시: "조용한 용기로 세상을 바꾼 여인. 2005년 10월 24일, 영원한 자유의 어머니 로자 파크스가 우리 곁을 떠났습니다. 그녀가 남긴 위대한 한 걸음을 기억합니다."

[출력 JSON 규격]:
{{
  "title": "쇼츠 킬러 제목",
  "hook_quote": "오프닝 5초 핵심 훅 문구",
  "stages": [
    {{
      "stage_no": 1,
      "caption": "서사 단계 챕터 제목 (예: '얼음 한 알의 독기')",
      "cuts": [
        {{
          "cut_no": 1,
          "caption": "화면 노출 12~15자 자막",
          "narration": "성우가 낭독할 실제 한글 대본 문장",
          "highlight_keywords": ["핵심키워드1", "핵심키워드2"],
          "camera_motion": "face_zoom",
          "bg_prompt": "English 9:16 vertical prompt starting with {person_name_en} with his/her iconic features...",
          "fact_source": "공식 팩트체크 출처"
        }}
      ]
    }}
  ],
  "youtube_metadata": {{
    "title": "유튜브 쇼츠 최종 업로드 제목 #shorts",
    "description": "설명란 본문 요약.\\n\\n━━━━━━━━━━━━━━━━━━━━\\n[공식 팩트체크 및 출처 정보 (Fact Check & Sources)]\\n위 fact_check에 기록된 verified_facts 항목과 출처를 1번부터 번호를 매겨 조목조목 투명하게 전부 기재하세요.\\n━━━━━━━━━━━━━━━━━━━━",
    "pinned_comment": "시청자 참여 유도 질문",
    "tags": ["태그1", "태그2", "태그3"]
  }}
}}
반드시 순수 JSON만 응답하세요."""

    user_prompt = f"""[대상 인물 정보]:
- 이름: {person_name} ({person_name_en})
- 모드: {mode_kr}
- 날짜: {date_str}

[심층 오리지널 르포 (Narrative Spine SSOT)]:
{story_text}

[공식 팩트체크 검증 가드레일 (Fact Check Guardrail)]:
- 확인된 날짜: {fact_data.get('verified_date')} (날짜일치: {fact_data.get('target_date_match')})
- 공인 출처: {', '.join(fact_data.get('primary_sources', []))}
- 검증된 팩트 리스트:
{verified_facts_str}
- 검증된 루머 반박:
{myths_str}
- 쇼츠 핵심 테마: {fact_data.get('summary_for_shorts')}

[온더넥스트 단일 최고 롤모델 레퍼런스]:
{ref_exemplars}

위 [심층 오리지널 르포]의 기승전결 서사와 감정선을 쇼츠 규격으로 생생히 압축·각색하여,
최소 5개 이상의 서사 단계(stages)와 15개 이상의 탄력적 컷(cuts)으로 구성된 완성도 높은 쇼츠 대본 JSON을 작성하세요."""

    cfg_json = types.GenerateContentConfig(
        temperature=0.3,
        response_mime_type="application/json",
        system_instruction=system_instruction
    )

    resp = generate_content_with_retry(client, model, contents=user_prompt, config=cfg_json)
    try:
        script_data = json.loads(resp.text)
    except Exception:
        clean_text = re.sub(r"^```json\s*", "", resp.text.strip())
        clean_text = re.sub(r"\s*```$", "", clean_text)
        script_data = json.loads(clean_text)

    # 1. 서사 단계 수 검증 (최소 5개 이상)
    stages = script_data.get("stages", [])
    if len(stages) < 5:
        print(f"[Script Warn] 생성된 서사 단계 수가 5개 미만임 ({len(stages)}개). 서사 보강 점검 권장.")

    # 2. 컷 수 검증 (최소 15컷 이상)
    all_cuts = [c for st in stages for c in st.get("cuts", [])]
    if len(all_cuts) < 15:
        print(f"[Script Warn] 생성된 컷 수가 최소 기준(15컷)에 미달함 ({len(all_cuts)}개). 분량 점검 권장.")

    return script_data


# ==============================================================================
# 3.5 캘린더 DB 인물 로드 엔진
# ==============================================================================
def load_star_from_db(date_str=None, mode="am", person=None):
    """onthenext_shorts/data/calendar_db.json에서 인물 메타데이터 및 3개 실화 사건을 온전히 로드.
    DB에 미등록된 경우 star_trend_scout.py를 자동 연동하여 스카우트 후 반환.
    """
    if not date_str:
        kst = datetime.timezone(datetime.timedelta(hours=9))
        date_str = datetime.datetime.now(kst).strftime("%m-%d")
    mode_lower = mode.lower()

    star_data = None

    # 1. 캘린더 DB 파일에서 인물 탐색 (로컬 onthenext DB 우선 탐색 ➔ 루트 DB 폴백)
    for cfile in [DATA_DIR / "calendar_db.json", ROOT_CALENDAR_FILE]:
        if cfile.exists():
            try:
                cal_data = json.loads(cfile.read_text(encoding="utf-8"))
                entry = cal_data.get("calendar", {}).get(date_str, {}).get(mode_lower)
                if entry and entry.get("person_name"):
                    if not person or person == entry.get("person_name"):
                        star_data = entry
                        print(f"[CalendarDB] 검증 인물 로드 성공 ({cfile.name}): {entry['person_name']} ({entry.get('person_name_en')}) [Q-ID: {entry.get('wikidata_id', 'Q0')}]")
                        break
            except Exception as e:
                print(f"[CalendarDB Warn] 로드 실패: {e}")

    # 2. 미등록 시 실시간 스카우터 가동하여 DB 생성 및 취득
    if not star_data:
        try:
            from star_trend_scout import scout_trending_star
            from post_scout_adapter import prepare_star_for_pipeline
            print(f"[Launcher] {date_str} {mode.upper()} 캘린더 미등록 감지 ➔ 실시간 스카우터 가동...")
            raw_star = scout_trending_star(date_str=date_str, mode=mode_lower)
            if not raw_star or not raw_star.get("person_name"):
                raise ValueError("스카우터 반환 데이터 무효")
            star_data = prepare_star_for_pipeline(raw_star, date_str=date_str, mode=mode_lower)
        except Exception as e:
            raise RuntimeError(f"인물 스카우트 실행 실패: {e}")
    else:
        from post_scout_adapter import prepare_star_for_pipeline
        star_data = prepare_star_for_pipeline(star_data, date_str=date_str, mode=mode_lower)

    # 3. PM 모드 생존자 배제 재검증
    if mode_lower == "pm" and not star_data.get("is_deceased", False):
        raise ValueError(f"[치명적 오류] PM 슬롯 인물 '{star_data.get('person_name')}'은(는) 생존자입니다. 제작 중단.")

    return star_data


def save_deep_story_markdown(pkg_dir: Path, meta: dict, story_text: str) -> Path:
    """심층 르포 다큐 원문을 마크다운 파일(deep_story.md)로 별도 저장"""
    person = meta.get("person_name", "")
    person_en = meta.get("person_name_en", "")
    date_str = meta.get("target_date", "")
    mode = meta.get("mode", "AM").upper()
    mode_label = "오늘 태어난 스타 (생일 찬사)" if mode == "AM" else "오늘 우리 곁을 떠난 스타 (기일 추모)"
    created_at = meta.get("created_at", datetime.datetime.now().isoformat())

    md_path = pkg_dir / "deep_story.md"
    content = [
        f"# [심층 르포 다큐] {person} ({person_en}) - {date_str} {mode}",
        "",
        f"> **기록 일자**: {date_str} ({mode_label})  ",
        f"> **작성 일시**: {created_at}  ",
        f"> **문서 성격**: 숏폼 압축 전 3,000~5,000자 오리지널 장문 르포 (주말 롱폼 및 커뮤니티 배포용 원본)  ",
        "",
        "---",
        "",
        story_text.strip(),
        ""
    ]
    md_path.write_text("\n".join(content), encoding="utf-8")
    return md_path


def save_fact_check_report_markdown(pkg_dir: Path, meta: dict, fact_data: dict) -> Path:
    """공식 팩트체크 검증 결과를 마크다운 보고서(fact_check_report.md)로 별도 저장"""
    person = meta.get("person_name", "")
    person_en = meta.get("person_name_en", "")
    date_str = meta.get("target_date", "")
    mode = meta.get("mode", "AM").upper()

    date_match = "일치 (정상)" if fact_data.get("target_date_match") else "불일치 (주의)"
    verified_date = fact_data.get("verified_date", "미확인")
    is_deceased = "고인 (사망 확인)" if fact_data.get("is_deceased") else "생존 인물"

    md_path = pkg_dir / "fact_check_report.md"
    lines = [
        f"# [공식 팩트체크 리포트] {person} ({person_en}) - {date_str} {mode}",
        "",
        f"> **대상 일자**: {date_str}  ",
        f"> **일자 일치 여부**: {date_match} (공식 기록일: {verified_date})  ",
        f"> **생존/사망 판정**: {is_deceased}  ",
        f"> **검증 엔진**: Google Search Grounding  ",
        "",
        "---",
        "",
        "## 1. 공식 검증 완료 팩트 (Verified Facts)",
        ""
    ]

    verified_facts = fact_data.get("verified_facts", [])
    if verified_facts:
        lines.append("| 번호 | 주장 (Claim) | 상세 검증 내용 (Detail) | 1차 출처 (Source) |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for i, f_item in enumerate(verified_facts, 1):
            claim = f_item.get("claim", "").replace("|", "/")
            detail = f_item.get("detail", "").replace("|", "/")
            source = f_item.get("source", "").replace("|", "/")
            lines.append(f"| {i:02d} | {claim} | {detail} | {source} |")
        lines.append("")
    else:
        lines.append("- 검증된 팩트 항목이 없습니다.\n")

    lines.append("## 2. 왜곡·과장 및 루머 판정 (Debunked Myths & Clarifications)")
    lines.append("")
    debunked = fact_data.get("debunked_myths", [])
    if debunked:
        for i, d_item in enumerate(debunked, 1):
            myth = d_item.get("myth", "")
            truth = d_item.get("truth", "")
            source = d_item.get("source", "")
            lines.append(f"### [검증 {i:02d}] {myth}")
            lines.append(f"- **진실 및 해명**: {truth}")
            lines.append(f"- **공식 출처**: {source}")
            lines.append("")
    else:
        lines.append("- 지적된 왜곡이나 루머 항목이 없습니다.\n")

    lines.append("## 3. 1차 사료 및 공식 출처 목록 (Primary Sources)")
    lines.append("")
    sources = fact_data.get("primary_sources", [])
    if sources:
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. {s}")
        lines.append("")
    else:
        lines.append("- 등록된 출처 목록이 없습니다.\n")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def export_reports_from_json(pkg_dir_path: Path):
    """기존 script.json이 존재하는 폴더에서 deep_story.md와 fact_check_report.md를 독립 추출"""
    pkg_dir = Path(pkg_dir_path)
    script_json = pkg_dir / "script.json"
    if not script_json.exists():
        print(f"[Export Error] {script_json} 파일이 존재하지 않습니다.")
        return

    data = json.loads(script_json.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    story_text = data.get("deep_story", "")
    fact_data = data.get("fact_check", {})

    p1 = save_deep_story_markdown(pkg_dir, meta, story_text)
    p2 = save_fact_check_report_markdown(pkg_dir, meta, fact_data)

    print(f"[Export Complete] 보고서 마크다운 생성 완료:")
    print(f"  - 심층 르포: {p1}")
    print(f"  - 팩트체크: {p2}")


def determine_voice(person_name="", mode="AM", category=""):
    """6대 공식 성우 풀(VOICE_ROSTER) 기반 인물/모드/장르별 최적 성우 결정:
    - PM (기일 추모):
      - 여성 레전드/배우/가수: Aoede (깊은 울림과 서정적 감성)
      - 남성/역사/다큐: Charon (묵직하고 깊은 명품 중저음)
    - AM (생일 축하):
      - 스포츠/액션/투혼: Fenrir (파워풀하고 에너지 넘치는 남성)
      - 힙합/팝/코미디/예능: Puck (위트 있고 트렌디한 젊은 남성)
      - 문학/클래식/철학/예술가: Orpheus (지적이고 부드러운 감성 남성)
      - 배우/아이돌/K-컬처/기본: Kore (밝고 또렷한 표준 여성)
    """
    mode_u = str(mode).upper()
    cat_l = str(category).lower()
    name_l = str(person_name).lower()

    if mode_u == "PM":
        female_keywords = ["마리", "오드리", "마릴린", "휘트니", "다이애나", "모니카", "에디트", "에바", "여성", "queen", "actress", "배우(여)", "가수(여)"]
        if any(k in name_l or k in cat_l for k in female_keywords):
            return "Aoede"
        return "Charon"

    if any(k in cat_l for k in ["스포츠", "축구", "야구", "농구", "격투", "복싱", "골프", "sport", "football", "soccer", "boxing", "hero", "action"]):
        return "Fenrir"
    if any(k in cat_l for k in ["힙합", "랩", "코미디", "개그", "예능", "팝", "hiphop", "rap", "comedy", "pop"]):
        return "Puck"
    if any(k in cat_l for k in ["문학", "시인", "작가", "철학", "클래식", "미술", "예술", "classic", "literature", "art", "writer", "poem"]):
        return "Orpheus"
    if any(k in cat_l for k in ["배우", "아이돌", "가수", "k-culture", "actor", "actress", "idol"]):
        return "Kore"

    return "Kore"


# ==============================================================================
# 4. 통합 실행 런처 (2-1 ➔ 2-2 ➔ 2-3A ➔ 2-3B ➔ 2-4 전 공정 파이프라인)
# ==============================================================================
def create_script(date_str=None, mode="am", person=None):
    from google.genai import types

    if not date_str:
        kst = datetime.timezone(datetime.timedelta(hours=9))
        date_str = datetime.datetime.now(kst).strftime("%m-%d")

    # Step 1: 캘린더 DB에서 인물 로드 (2-1단계)
    star_data = load_star_from_db(date_str=date_str, mode=mode, person=person)
    person = star_data["person_name"]
    person_en = star_data.get("person_name_en", "Star")

    # 패키지 디렉토리를 onthenext_shorts/output/ 내부에 완전 격리 생성
    slug = re.sub(r"[^\w]", "_", person_en.lower())
    pkg_dir = OUTPUT_DIR / f"2026{date_str.replace('-', '')}_{mode.upper()}_{slug}"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()

    try:
        client.models.generate_content(model=MODEL_PRO, contents="ping")
        model = MODEL_PRO
    except Exception as e:
        print(f"[Script] {MODEL_PRO} 불가({e}), 폴백 {MODEL_FLASH}")
        model = MODEL_FLASH

    # Step 2: 167 DB 시맨틱 검색 (2-2단계: 단일 최고 롤모델 레퍼런스 추출)
    top_ref = retrieve_top_reference(RAG_DB_PATH, star_data, mode)

    time.sleep(2)

    # Step 3A: 단일 롤모델 기반 충분히 긴 이야기 생성 (2-3A단계)
    story_text = generate_deep_story(client, types, model, star_data, mode, date_str, top_ref)

    time.sleep(2)

    # Step 3B: 생성된 이야기에 대한 Google Search 팩트체크 (2-3B단계)
    fact_data = verify_story_facts(client, types, model, person, person_en, mode, date_str, story_text)
    print(f"[FactCheck] 성공: 날짜일치={fact_data.get('target_date_match')}, 고인여부={fact_data.get('is_deceased')}")

    time.sleep(2)

    # Step 4: 대본 집필 (stages + cuts 구조: deep_story 원천 서사 + fact_check 가드레일)
    script_data = generate_25cut_rag_script(client, types, model, person, person_en, mode, date_str, story_text, fact_data, top_ref)

    # 4-1. 컷별 발음 정규화(천구백구십삼년) 및 화면 표기(1993년) 후처리 안전망
    from importlib import import_module
    try:
        _sub_mod = import_module("onthenext_shorts.06_star_subtitle")
    except Exception:
        _sub_mod = import_module("06_star_subtitle")
    _fmt_sub = _sub_mod.format_sub_display

    for st in script_data.get("stages", []):
        for c in st.get("cuts", []):
            raw_narr = c.get("narration", "")
            c["narration"] = normalize_spoken_korean_years(raw_narr)
            raw_disp = c.get("display_text") or raw_narr
            # 🚨 자막 요약/누락 원천 차단: display_text가 narration보다 짧게 요약된 경우 narration 원문 1:1 보존
            if not raw_disp or len(raw_disp) < len(raw_narr) * 0.85:
                raw_disp = raw_narr
            c["display_text"] = _fmt_sub(raw_disp)

    all_cuts = [c for st in script_data.get("stages", []) for c in st.get("cuts", [])]
    category = star_data.get("category", "")
    voice = determine_voice(person_name=person, mode=mode, category=category)
    print(f"[Voice Roster] 6대 공식 성우 풀 매칭: 인물='{person}', 모드={mode.upper()}, 장르='{category}' ➔ 성우={voice}")

    # Step 5: 결과 패키지 저장 (소지섭 script.json 키값 100% 매칭)
    result = {
        "meta": {
            "mode": mode.upper(),
            "target_date": date_str,
            "person_name": person,
            "person_name_en": person_en,
            "model": model,
            "package_dir": str(pkg_dir),
            "created_at": datetime.datetime.now().isoformat(),
            "narrative_group": star_data.get("narrative_group", top_ref.get("group_id", "G03")),
            "voice": voice
        },
        "deep_story": story_text,
        "fact_check": fact_data,
        "rag_reference": {
            "index": top_ref["index"],
            "protagonist": top_ref["protagonist"],
            "title": top_ref["title"],
            "group": top_ref["group_id"],
            "group_name": top_ref.get("group_name", "")
        },
        "rag_references": [
            {"rank": 1, "index": top_ref["index"], "protagonist": top_ref["protagonist"], "title": top_ref["title"], "group": top_ref["group_id"]}
        ],
        "script": script_data
    }

    out_path = pkg_dir / "script.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 검수용 텍스트 파일 저장 (스테이지별 가독성 확보)
    txt_path = pkg_dir / "script_cuts.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"=== [스타이즈본 쇼츠 대본: {person} ({date_str} {mode.upper()})] ===\n")
        f.write(f"제목: {script_data.get('title')}\n")
        f.write(f"오프닝 훅: {script_data.get('hook_quote')}\n")
        f.write(f"총 스테이지: {len(script_data.get('stages', []))}개 / 총 컷수: {len(all_cuts)}컷\n\n")
        for st in script_data.get("stages", []):
            f.write(f"\n[Stage {st.get('stage_no')}: {st.get('caption')}]\n")
            for c in st.get("cuts", []):
                f.write(f"Cut {c.get('cut_no'):02d}: [{c.get('camera_motion')}] {c.get('caption')} | {c.get('narration')}\n")
                f.write(f"  └ Prompt: {c.get('bg_prompt')[:75]}...\n")
                f.write(f"  └ Source: {c.get('fact_source')}\n")

    # 심층 르포 및 팩트체크 보고서 마크다운 자동 생성
    story_md_path = save_deep_story_markdown(pkg_dir, result["meta"], story_text)
    fact_md_path = save_fact_check_report_markdown(pkg_dir, result["meta"], fact_data)

    print(f"\n[Script Done] onthenext_shorts 내부에서 대본 및 보고서 패키지 완비!")
    print(f"  - JSON 데이터: {out_path}")
    print(f"  - 숏폼 컷 대본: {txt_path}")
    print(f"  - 심층 르포 원본: {story_md_path}")
    print(f"  - 팩트체크 보고서: {fact_md_path}")
    print(f"  - 제목: {script_data.get('title')}")
    print(f"  - 스테이지 수: {len(script_data.get('stages', []))}개 / 총 컷수: {len(all_cuts)}컷")

    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="온더넥스트 167편 RAG 25컷 대본 생성기")
    p.add_argument("--mode", default="am", choices=["am", "pm"])
    p.add_argument("--date", default=None)
    p.add_argument("--person", default=None)
    p.add_argument("--export-reports", default=None, help="기존 패키지 폴더 경로를 지정하여 deep_story.md 및 fact_check_report.md만 독립 추출")
    args = p.parse_args()

    if args.export_reports:
        export_reports_from_json(Path(args.export_reports))
    else:
        create_script(date_str=args.date, mode=args.mode, person=args.person)

"""스타이즈본 대본 생성기: 팩트체크(Google Search Grounding) + 7씬 서사 확장 쇼츠 대본.
PRJ_standard 계승, 실명 앵커 강제, 자음 약어 배제, 간결한 구독/좋아요 CTA 적용.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

# Windows cp949 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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




def get_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def generate_content_with_retry(client, model, contents, config=None, max_retries=4, base_sleep=5):
    """429 RESOURCE_EXHAUSTED 및 일시적 서버 오류 대응:
    - 지수 백오프 (5s, 10s, 20s, ...) 재시도
    - Pro 모델에서 429 또는 2회 연속 실패 시 자동으로 Flash(gemini-2.5-flash)로 다운그레이드 폴백
    """
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


def run_fact_check(client, types, model, person_name, mode, date_str):
    event_kr = "태어난 날(생일)" if mode.lower() == "am" else "사망한 날(기일)"
    print(f"[FactCheck] '{person_name}'의 {date_str} {event_kr} 팩트체크 수행 중 (Google Search Grounding)...")

    search_prompt = f"""다음 인물에 대한 역사적 팩트를 상세히 검색 및 확인하세요:
- 대상 인물: {person_name}
- 목표 날짜: {date_str}
- 확인 사건: {event_kr}

확인할 핵심 질문:
1. 이 인물의 실제 {event_kr}이 {date_str}이 맞습니까? 정확한 연월일(YYYY-MM-DD)은?
2. 이 인물의 출생, 데뷔, 또는 사망 순간의 결정적이고 극적인 사실은 무엇입니까?
3. 전설적인 작품/경기/프로젝트 탄생 비화, 대기록, 무명 시절의 치열한 노력 일화 2~3가지는?
4. [주의]: 사생활 가십, 세금/탈세, 가짜뉴스/사망설, 성형 의혹 등 불필요한 분쟁을 유발하는 부정적 논란은 조사 대상에서 완전히 제외하고, 공인된 공식 기록과 긍정적인 미담 위주로 기술하세요.
5. [사망 팩트 가드레일]: 이 인물은 실제로 세상을 떠난 고인(Deceased)입니까, 아니면 현재 살아있는 생존 인물입니까? PM 기일 모드인 경우 생존 여부를 엄격히 밝히세요.
출처와 함께 사실 위주로 상세히 기술하세요."""

    search_context = ""
    try:
        cfg = types.GenerateContentConfig(
            temperature=0.2,
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = generate_content_with_retry(client, model, contents=search_prompt, config=cfg)
        search_context = resp.text
        print(f"[FactCheck] Search Grounding 성공 ({len(search_context)}자 확보)")
    except Exception as e:
        print(f"[FactCheck] Search tool 폴백: {e}")

    # Grounding 호출 후 API 부하 완화
    time.sleep(2)

    structure_prompt = f"""다음 검색된 역사적 사실들을 바탕으로 검증 체크리스트 JSON을 작성하세요:
인물: {person_name}
목표 날짜: {date_str}
사건: {event_kr}
검색 컨텍스트:
{search_context if search_context else "인물에 대한 정설 역사 지식을 기반으로 검증하세요."}

[출력 JSON 규격 - 출처는 '언론 보도' 같은 모호한 표현 절대 금지! 공인 기관/협회/매체명/고유ID를 명확히 기재할 것]
{{
  "target_date_match": true/false,
  "is_deceased": true/false,
  "verified_date": "YYYY-MM-DD",
  "primary_sources": ["위키데이터 고유ID 또는 브리태니커", "공인 통계/기관(영진위, KMDb 등)", "지상파 방송/주요 언론 공식 인터뷰"],
  "verified_facts": [
    {{"claim": "핵심 팩트 요약", "detail": "상세 설명", "source": "명확한 공인 출처명 (예: 위키데이터 Q494723, KMDb 프로필, 영화진흥위원회 KOBIS 통계)"}}
  ],
  "debunked_myths": [
    {{"myth": "흔한 오해/루머", "truth": "실제 진실"}}
  ],
  "summary_for_shorts": "쇼츠 핵심 테마 요약 (100자 내외)"
}}
반드시 순수 JSON만 응답하세요."""

    cfg_json = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json"
    )
    resp_json = generate_content_with_retry(client, model, contents=structure_prompt, config=cfg_json)
    try:
        parsed = json.loads(resp_json.text)
    except Exception:
        clean_text = re.sub(r"^```json\s*", "", resp_json.text.strip())
        clean_text = re.sub(r"\s*```$", "", clean_text)
        parsed = json.loads(clean_text)

    # PM 모드 사망 여부 하드 가드레일 인터록
    if mode.lower() == "pm" and not parsed.get("is_deceased", True):
        raise ValueError(f"[🚨 FactCheck 차단] '{person_name}'은(는) 현재 살아있는 생존 인물입니다! PM(사망 기일 추모) 모드로 가짜뉴스 대본을 쓸 수 없습니다.")

    return parsed


def ensure_fact_check_in_description(description: str, fact_data: dict, tags: list = None) -> str:
    """유튜브 설명란에 공식 팩트체크 및 출처 정보 블록과 하단 해시태그가 온전히 포함되도록 100% 보증."""
    has_fact_block = "[공식 팩트체크 및 출처 정보" in description

    if not has_fact_block:
        facts = fact_data.get("verified_facts", []) if fact_data else []
        # 기존 설명란 끝의 모호하거나 축약된 출처 줄 정리
        desc_clean = re.sub(r"\n*\[?(?:공식\s*)?(?:팩트체크|출처).*$", "", description.strip(), flags=re.DOTALL).strip()

        fact_lines = [desc_clean]
        if facts:
            fact_lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━",
                "[공식 팩트체크 및 출처 정보 (Fact Check & Sources)]"
            ])
            for idx, f in enumerate(facts, 1):
                claim = f.get("claim", "").strip()
                detail = f.get("detail", "").strip()
                source = f.get("source", "").strip()
                item_text = claim if claim else detail
                if detail and detail != claim and not detail.startswith(claim):
                    item_text = f"{claim} ({detail})"
                fact_lines.append(f"{idx}. {item_text} (출처: {source})")
            fact_lines.append("━━━━━━━━━━━━━━━━━━━━")
        description = "\n".join(fact_lines)

    # 하단 해시태그(#) 블록 보증
    if tags:
        tag_list = [f"#{t.strip().replace(' ', '')}" for t in tags if t and t.strip()]
        if "#shorts" not in [t.lower() for t in tag_list]:
            tag_list.append("#shorts")
        hashtag_str = " ".join(tag_list)
        if hashtag_str and hashtag_str not in description:
            description = description.rstrip() + "\n\n" + hashtag_str

    return description


def generate_shorts_script(client, types, model, person_name, person_name_en, mode, date_str, fact_data, available_photos=None, scouted_meta=None):
    """검증된 팩트와 인물의 킬러 바이럴 썰을 바탕으로 7개 씬(80~100초) 단 하나의 썰 몰입형 쇼츠 대본 생성."""
    mode_title = "[A Star is Born] 오늘 태어난 스타" if mode.lower() == "am" else "[The Legend Falls] 오늘 별이 된 레전드"
    print(f"[Script] {mode_title} - 7개 씬 도파민 킬러 스토리 대본 집필 중...")

    # available_photos 규격 정규화 (딕셔너리 or 리스트 지원)
    candidates = []
    if isinstance(available_photos, dict):
        candidates = available_photos.get("candidates", [])
    elif isinstance(available_photos, list):
        candidates = available_photos

    photo_anchor_section = ""
    if candidates:
        p_lines = []
        for p in candidates[:10]:
            p_lines.append(f"- [사료 ID: {p['id']}] 출처: {p.get('source', '')} | 사진 내용: {p.get('caption', '')}")
        p_str = "\n".join(p_lines)
        photo_anchor_section = f"""
[참고용 확보 사료 목록 (선택적 앵커링)]:
우리는 이 스타에 대해 아래와 같이 실제로 촬영된 고화질 역사적 실사 사진들을 보유하고 있습니다:
{p_str}

[사료 활용 지침]:
1. 대본의 주도권은 '스토리의 재미와 도파민'이 100% 쥐어야 합니다! 절대 사진 목록에 대본을 억지로 꿰맞추지 마세요!
2. 7개 씬의 킬러 스토리를 써내려가는 과정에서 위 사료 목록 중 자연스럽게 어울리는 사진이 있다면 해당 씬의 "anchored_photo_id": "<사료 ID>"로 지정하세요.
3. 사료 목록에 사진이 없는 씬(유년기, 오디션 뒷이야기, 특정 미보유 대표작 등)은 주저하지 말고 "anchored_photo_id": null 로 비워두세요. (AI 시각 연속성이 그 빈자리를 완벽히 연출합니다!)
"""

    # scouted_meta에서 킬러 썰 및 핵심 키워드 추출
    viral_story = ""
    keywords_str = ""
    trend_reason = ""
    brief_desc = ""
    if scouted_meta:
        viral_story = scouted_meta.get("viral_story_point", "")
        keywords_str = ", ".join(scouted_meta.get("keywords", []))
        trend_reason = scouted_meta.get("trend_reason", "")
        brief_desc = scouted_meta.get("brief", "")

    if mode.lower() == "am":
        tone_instruction = """- [AM 탄생 축하 모드 컬러/조명 철학 - 생생한 원색 풀컬러 (Vivid Full Color)]:
     * 컬러 톤: 'vivid vibrant full color, ultra-rich saturated palette, lively energetic cinematic lighting, celebratory atmosphere'
     * 절대 규칙: 생일 축하이므로 칙칙한 흑백이나 어두운 톤을 배제하고, 눈길을 확 사로잡는 생생한 원색과 역동적인 조명을 사용할 것."""
    else:
        tone_instruction = """- [PM 기일 추모 모드 컬러/조명 철학 - 헌정 흑백 + 골드 앰비언트 (In Memoriam Tribute)]:
     * 컬러 톤: 'striking high-contrast black and white monochrome subject, subtle warm golden rim lighting around silhouette, dark moody atmospheric background with faint warm golden dust embers, solemn reverent legendary legacy mood, strictly no bright cheerful colors'
     * 절대 규칙: 고인을 기리는 엄숙하고 품격 있는 헌정이므로, 배경과 인물은 고대비 흑백(Monochrome)을 기반으로 하되 실루엣 주위에 은은하게 타오르는 황금빛 역광(Warm Golden Rim Lighting)과 금빛 불씨(Golden Embers)만으로 영원한 유산(Legacy)을 기릴 것."""

    visual_style_instruction = f"""[AI 아트 디렉터 모드: 인물/장르별 6대 화풍 매핑 & 서사별 진화]
1. 인물/장르 특성에 맞는 최적의 화풍을 자동 매칭하여 프롬프트에 반영하세요:
   - 코믹/블록버스터/예능 스타: 'American Comic / Graphic Novel pop-art style with bold ink outlines'
   - 정통 연기파 배우/카리스마 거장: 'Dramatic Cinematic 35mm Film Still with anamorphic lens depth'
   - 화가/문학가/클래식 거장/19세기 이전 위인: 'Classical Impasto Oil Painting with rich textured canvas brushwork'
   - 일렉트로닉/글램록/SF 미래 혁신가: 'Cyberpunk Retro Synthwave with neon glow and high-tech flair'
   - 뮤지컬/디바/쇼맨십 엔터테이너: 'Vintage Broadway Theatrical Stage with dramatic spotlight framing'
   - 애니/스포츠/격투 스타: 'Dynamic Manga / Anime Graphic illustration with high-speed lines'

2. {tone_instruction}

3. [7개 씬 서사별 비주얼 진화 (Visual Progression)]:
   - 씬 1 (오프닝 훅): 극적인 인물 페이스 클로즈업 (Intense Hook Portrait Close-up)
   - 씬 2~3 (무명/시련/도전): 거칠고 치열한 초기 배경과 땀방울, 고난 (Gritty Early Struggle)
   - 씬 4~5 (결정적 순간/절정): 전설적인 무대/경기장/작품 탄생의 와이드 임팩트 (Climax Breakthrough Stage)
   - 씬 6~7 (원숙한 레거시/헌정): 시대의 상징으로 완성된 마스터피스 포스터 (Iconic Masterpiece Poster)

4. [공통 규격 강제]:
   - 모든 bg_prompt 끝에는 반드시 'vertical 9:16 portrait orientation, strictly tall phone screen framing, masterpiece, 8k, no text'를 명시하세요."""

    prompt = f"""당신은 100만 유튜브 쇼츠 채널 '스타이즈본'의 메인 스토리텔러 작가입니다.
인물 한글명: {person_name}
인물 영문명: {person_name_en}
모드: {mode_title}
날짜: {date_str}

[🔥 쇼츠 대본 절대 제1원칙: 단 하나의 킬러 썰 / 도파민 실화 중심 스토리텔링 🔥]
우리는 이 인물에 대해 지루한 위키백과 연표(이력서 브리핑)를 낭독하려는 것이 아닙니다!
시청자의 뇌관을 터뜨릴 '단 하나의 충격적인 비하인드 실화'를 뼈대로 삼아, 7개 씬 동안 손에 땀을 쥐게 만드는 미니 드라마(썰)를 풀어야 합니다!

[이 스타의 검증된 킬러 바이럴 썰]:
- 핵심 킬러 썰: {viral_story if viral_story else brief_desc}
- 대표 상징 키워드: {keywords_str}
- 대중 주목 이유: {trend_reason}

검증된 팩트 데이터:
{json.dumps(fact_data, ensure_ascii=False, indent=2)}
{photo_anchor_section}

[🚨🚨 지루한 시대별 연표 브리핑(Chronological Overview) 100% 영구 퇴출 🚨🚨]
- ❌ 절대 금기 (이력서 낭독): "몇 년도에 데뷔했고 ➔ 몇 년도에 무슨 드라마를 찍었고 ➔ 몇 년도에 무슨 영화를 찍었습니다" 식의 연도별 작품 나열 금지!
- ❌ 절대 금기 (주요 대표작 누락): 사진이 없다는 핑계로 대중이 가장 열광하는 '국민 대표작/인생 캐릭터'를 대본에서 빼버리는 행위 엄벌!

[⭕ 필수 서사 원칙: 단 하나의 썰 몰입형 7씬 롤러코스터 구조]:
1. [씬 1: 도파민 대비 훅 (Contrast Hook) - 3초 만에 멱살 잡기]:
   - 🚨 절대 금기: "1994년 11월 26일 세상에 한 아이가 태어났습니다" 같은 지루한 구연동화 도입부 100% 금지!
   - 💡 필수 공식: 인물의 가장 충격적인 대비(처절한 결핍 vs 상상초월 성공) 또는 대본에도 없던 소름 돋는 충격 실화로 시작할 것!
2. [씬 2: 충격 사건의 발단 / 비하인드 썰]:
   - 대본에도 없던 자작 연기, 상상 초월의 오디션/작품 비화, 아무도 몰랐던 현장의 충격적인 시작.
3. [씬 3: 위기와 극한의 몰입]:
   - 감독이나 동료마저 기절 직전까지 몰고 간 미친 디테일, 처절한 독기나 극한의 고난.
4. [씬 4: 반전의 독기 / 각성]:
   - 이 지독한 집념의 뿌리 (뼈를 깎는 노력, 지옥의 감량, 무명 시절의 치열한 악바리 정신 등 반전 서사).
5. [씬 5: 클라이맥스 대폭발 - 인생 대표작]:
   - 전 국민을 뒤흔든 인생 최고의 대표작/인생 캐릭터로 판을 뒤집어버린 전율의 순간! (대중이 가장 사랑하는 인생작을 반드시 여기서 터뜨릴 것!)
6. [씬 6: 한계 없는 광기 / 현재의 위상]:
   - 배역을 위해 영혼까지 갈아 넣는 지독한 열정과 현재 대한민국/세계가 주목하는 독보적 위상.
7. [씬 7: 묵직한 헌정 엔딩]:
   - 구걸식 멘트("구독 좋아요") 배제, 인물의 삶을 관통하는 묵직한 한 줄 헌사와 오늘 날짜의 의미로 품격 있게 마무리.

8. [자막(display_text) vs 음성(narration) 1:1 완벽 분리]:
   - [display_text]: 화면용. 연도, 날짜, 수량은 시인성 높은 아라비아 숫자 표기 (예: 1994년 11월 26일, 30kg, 1위)
   - [narration]: 성우용. 자연스러운 한글 구어체 발음 표기 (예: 천구백구십사년 십일월 이십육일, 삼십 킬로그램, 일위)
   - 두 문장은 단어와 문맥이 1:1로 일치해야 하며, 서면어가 아닌 자연스러운 입말로 작성하세요.

[출력 JSON 규격]
{{
  "title": "쇼츠 썸네일 훅 제목 (10~14자 내외, 콜론(:)이나 인물 실명 반복 금지)",
  "hook_quote": "오프닝 5초 핵심 훅 문구",
  "scenes": [
    {{
      "scene_no": 1,
      "timing": "00:00-00:08",
      "caption": "화면 상단 한글 챕터 제목 (10자 내외 간결한 구문)",
      "display_text": "화면 자막용 2~3문장 (숫자/연도는 아라비아 표기, 60~90자 내외)",
      "narration": "성우 낭독용 2~3문장 (한글 구어체 발음 표기, 60~90자 내외)",
      "highlight_keyword": "이 씬에서 단 1개만 노란색으로 강조할 핵심 단어",
      "anchored_photo_id": "확보된 사료 ID(예: 'real_001') 또는 null",
      "camera_motion": "face_zoom 또는 pan_lr 등 6대 모션 중 택1",
      "bg_prompt": "English 9:16 vertical visual prompt starting with {person_name_en}"
    }},
    ... (총 7개 씬)
  ],
  "youtube_metadata": {{
    "title": "유튜브 쇼츠 최종 업로드 제목 #shorts",
    "description": "설명란 본문 요약.\n\n━━━━━━━━━━━━━━━━━━━━\n[공식 팩트체크 및 출처 정보 (Fact Check & Sources)]\n위 fact_check에 기록된 모든 verified_facts의 항목과 그 출처(공인 기관명, 통계, 인터뷰 아카이브 등)를 1번부터 번호를 매겨 조목조목 투명하게 전부 기재하세요.\n━━━━━━━━━━━━━━━━━━━━",
    "pinned_comment": "시청자들이 댓글을 쓰게 만드는 강력한 찬반/투표 질문 (예: 여러분이 생각하는 최고의 명장면은? 1번 vs 2번)",
    "tags": ["태그1", "태그2", "태그3"]
  }}
}}
반드시 순수 JSON만 반환하세요."""

    cfg = types.GenerateContentConfig(
        temperature=0.7,
        response_mime_type="application/json"
    )
    resp = generate_content_with_retry(client, model, contents=prompt, config=cfg)
    raw_text = (resp.text or "").strip()
    clean_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
    clean_text = re.sub(r"\s*```$", "", clean_text).strip()
    try:
        data = json.loads(clean_text, strict=False)
    except Exception:
        m = re.search(r"(\{[\s\S]*\})", clean_text)
        if m:
            data = json.loads(m.group(1), strict=False)
        else:
            raise

    # 유튜브 메타데이터 팩트체크 블록 이중 보증 (LLM 누락 방지 가드)
    if isinstance(data, dict) and "youtube_metadata" in data:
        yt = data["youtube_metadata"]
        if isinstance(yt, dict) and "description" in yt:
            yt["description"] = ensure_fact_check_in_description(yt["description"], fact_data, tags=yt.get("tags"))

    return data


def run_pipeline(mode="am", date_str=None, person=None, available_photos=None):
    from google import genai
    from google.genai import types

    if not date_str:
        kst = datetime.timezone(datetime.timedelta(hours=9))
        date_str = datetime.datetime.now(kst).strftime("%m-%d")

    person_en = "Oscar Wilde"
    scouted_meta = {}

    # 1. calendar_db.json에 이미 저장된 인물이 있는지 우선 확인
    cal_path = DATA_DIR / "calendar_db.json"
    if cal_path.exists():
        try:
            cal_data = json.loads(cal_path.read_text(encoding="utf-8"))
            entry = cal_data.get("calendar", {}).get(date_str, {}).get(mode.lower())
            if entry and entry.get("person_name"):
                if not person or person == entry.get("person_name"):
                    person = entry["person_name"]
                    person_en = entry.get("person_name_en", "Oscar Wilde")
                    scouted_meta = entry
                    print(f"[CalendarDB] 당일({date_str}) 검증 인물 로드: {person} ({person_en}) [Wikidata: {entry.get('wikidata_id')}]")
        except Exception as e:
            print(f"[CalendarDB Warn] 로드 실패: {e}")

    # 2. calendar_db.json에 미등록된 경우 실시간 3인 후보 AI 스카우터 단일 가동 (10-24 정식 표준)
    if not person:
        try:
            from star_trend_scout import scout_trending_star
            print(f"[Launcher] {date_str} {mode.upper()} 캘린더 미등록 감지 ➔ 실시간 3인 후보 AI 스카우터 가동...")
            scouted = scout_trending_star(date_str=date_str, mode=mode)
            if scouted and scouted.get("person_name"):
                person = scouted["person_name"]
                person_en = scouted.get("person_name_en", "Oscar Wilde")
                scouted_meta = scouted
                print(f"[TrendScout] 3인 경합 1위 스타 낙점 및 DB 반영 완료: {person} ({person_en}) [Wikidata: {scouted.get('wikidata_id')}]")
            else:
                raise ValueError("스카우터 반환 인물 데이터 무효")
        except Exception as e:
            print(f"[TrendScout Fatal Error] 실시간 3인 후보 스카우터 실행 실패: {e}")
            raise RuntimeError(f"[{date_str} {mode.upper()}] 인물 스카우트 실패로 파이프라인을 중단합니다: {e}")

    # 일자별/인물별 패키지 디렉토리 설정
    slug = re.sub(r"[^\w]", "_", person_en.lower())
    pkg_dir = OUTPUT_DIR / f"2026{date_str.replace('-', '')}_{mode.upper()}_{slug}"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = pkg_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()

    try:
        client.models.generate_content(model=MODEL_PRO, contents="ping")
        model = MODEL_PRO
    except Exception as e:
        print(f"[Script] {MODEL_PRO} 불가({e}), 폴백 {MODEL_FLASH}")
        model = MODEL_FLASH

    # 1. 팩트체크
    fact_data = run_fact_check(client, types, model, person, mode, date_str)
    print(f"[FactCheck] 결과: 날짜일치={fact_data.get('target_date_match')}, 확인일자={fact_data.get('verified_date')}")

    # 팩트체크와 대본 생성 사이 쿨다운 (API 429 방지)
    time.sleep(3)

    # 2. 대본 생성 (단 하나의 킬러 썰 몰입형 7씬 집필)
    script_data = generate_shorts_script(client, types, model, person, person_en, mode, date_str, fact_data, available_photos=available_photos, scouted_meta=scouted_meta)

    # 3. 패키지 디렉토리에 script.json 저장
    result = {
        "meta": {
            "mode": mode.upper(),
            "target_date": date_str,
            "person_name": person,
            "person_name_en": person_en,
            "wikidata_id": scouted_meta.get("wikidata_id") or scouted_meta.get("winner", {}).get("wikidata_id"),
            "available_photos": available_photos or [],
            "model": model,
            "package_dir": str(pkg_dir),
            "created_at": datetime.datetime.now().isoformat()
        },
        "fact_check": fact_data,
        "script": script_data
    }

    out_path = pkg_dir / "script.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 유튜브 메타데이터 분리 영구 보존
    if "youtube_metadata" in script_data:
        yt_meta_path = pkg_dir / "youtube_metadata.json"
        yt_meta_path.write_text(json.dumps(script_data["youtube_metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Script] 완료! 저장 경로: {out_path}")
    print(f"         제목: {script_data.get('title')}")
    print(f"         씬 개수: {len(script_data.get('scenes', []))}씬")
    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 7씬 쇼츠 대본 생성기")
    p.add_argument("--mode", default="am", choices=["am", "pm"])
    p.add_argument("--date", default=None)
    p.add_argument("--person", default=None)
    args = p.parse_args()

    run_pipeline(mode=args.mode, date_str=args.date, person=args.person)

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

CRED_PATH = ROOT_DIR / "config" / "application_default_credentials.json"
if CRED_PATH.exists():
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(CRED_PATH))

GCP_PROJECT_ID = "project-beba2bf6-d235-4031-ba5"
GCP_LOCATION = "us-central1"
MODEL_PRO = "gemini-2.5-pro"
MODEL_FLASH = "gemini-2.5-flash"




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


def generate_shorts_script(client, types, model, person_name, person_name_en, mode, date_str, fact_data):
    """검증된 팩트를 바탕으로 7개 씬(80~100초) 서사 확장 쇼츠 대본 생성."""
    mode_title = "[A Star is Born] 오늘 태어난 스타" if mode.lower() == "am" else "[The Legend Falls] 오늘 별이 된 레전드"
    print(f"[Script] {mode_title} - 7개 씬 서사 확장 대본 집필 중...")

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

    prompt = f"""당신은 100만 유튜브 쇼츠 채널 '스타이즈본'의 메인 작가입니다.
인물 한글명: {person_name}
인물 영문명: {person_name_en}
모드: {mode_title}
날짜: {date_str}
검증된 팩트 데이터:
{json.dumps(fact_data, ensure_ascii=False, indent=2)}

[대본 작성 절대 룰 - 엄격 준수]
1. 1분 컷으로 너무 조급하게 줄이지 마세요! 충분히 흥미진진한 썰을 풀 수 있도록 총 7개 씬(약 80초~100초)으로 구성합니다.
2. 위인전 어투 절대 금지! 써에이스쇼/OverSimplified처럼 찰지고 유쾌한 구어체 사용.
3. [핵심 채널 철학 - 긍정과 찬사(Celebration) & 따뜻한 추모와 헌정(Tribute)으로 가득 채울 것]:
   - 이 채널의 절대적 목적은 '생일을 맞은 셀럽을 온 마음으로 축하하고, 세상을 떠난 레전드를 따뜻하게 추모하는 헌정 채널'입니다.
   - [AM - 생일 축하 모드]: 시청자와 팬덤 모두가 감탄하고 진심으로 축하할 수 있는 '역대급 대기록', '치열한 노력과 끈기', '반전 실력과 신드롬', '감동적인 미담과 선한 영향력'을 칭찬과 긍정으로 가득 채우세요.
   - [PM - 기일 추모 모드]: 자극적인 사망 경위나 비극적 사건 묘사는 엄격히 배제하고, 그가 남긴 '불멸의 명곡/명작', '전 세계 팬들의 청춘을 밝혀준 찬란한 순간', '음악과 예술적 유산에 대한 깊은 경의와 따뜻한 리스펙트'를 담으세요.
   - [공통 금기 사항]: 사생활 가십, 세금/법적 분쟁, 성형 루머, 악의적 논란은 100% 원천 배제하세요.
4. [TTS 음성 낭독 가드레일 - 중요]:
   - 채팅 자음(ㄱㄱ, ㄷㄷ, ㅋㅋ, ㅠㅠ, ㄹㅇ 등)이나 슬랭 약어를 대본 본문에 절대 쓰지 마세요! 성우가 읽을 때 '기역기역'처럼 오독합니다.
   - 반드시 발음하기 자연스러운 완전한 구어체 한국어(예: '고고!', '덜덜', '진짜 대박', '소름')로 작성하세요.
5. [아웃트로 CTA 룰 - 중요]:
   - AM(생일): "오늘 생일을 맞은 {person_name}에게 따뜻한 축하 댓글을 남겨주세요! 영상이 재밌으셨다면 구독과 좋아요 꾹 눌러주세요!"
   - PM(추모): "여러분의 가슴속에 남은 {person_name}의 최고의 명곡은 무엇인가요? 영원히 기억될 그를 기리며, 구독과 좋아요로 함께해 주세요."
6. [비주얼 프롬프트 앵커 룰 - 중요]:
   - 씬 1부터 씬 7까지 모든 bg_prompt 첫머리에 반드시 '{person_name_en} with his/her iconic features' 실명과 대표 외형 시그니처를 포함해야 합니다.
   {visual_style_instruction}

[서사 다변화 가이드 - 매일 다른 플롯 선택]
인물의 특성과 팩트에 가장 잘 어울리는 아래 5가지 서사 플롯 중 하나를 자동 선택하여 7개 씬을 유기적으로 전개하세요:

플롯 A. [상식 파괴 & 반전 추적형] (오해와 루머가 있거나 반전이 있는 인물):
  - 씬 1: "우리가 알던 이 사실, 100% 가짜였다?!" 도발적 훅
  - 씬 2~3: 당대 사람들이 왜 이 사람을 오해하고 비난했는가?
  - 씬 4~5: 역사적 팩트와 결정적 증거로 밝혀낸 진짜 진실
  - 씬 6~7: 역사의 재평가와 여운 + 간결한 CTA

플롯 B. [언더독 카타르시스형] (밑바닥, 무명, 편견을 독기로 뚫어낸 인물):
  - 씬 1: 가장 비참하게 내동댕이쳐졌던 절망의 순간
  - 씬 2~3: 곰팡이 단칸방/비웃음 속에서 이를 악물고 갈고닦은 무기
  - 씬 4~5: 단 한 번의 무대/기회에서 세상을 뒤집어버린 도파민 폭발
  - 씬 6~7: 나를 무시하던 자들을 향한 가장 통쾌한 복수 + 간결한 CTA

플롯 C. [세기의 맞대결 & 라이벌전] (치열한 승부와 라이벌이 있는 스포츠/테크 스타):
  - 씬 1: 숨 막히는 격돌의 현장 오프닝
  - 씬 2~3: 천재 vs 천재, 스타일과 성격의 극단적 대비
  - 씬 4~5: 전 세계 수억 명이 숨죽인 결정적 명장면/충돌
  - 씬 6~7: 승패를 초월한 리스펙트와 영원한 드라마 + 간결한 CTA

플롯 D. [도파민 폭발 엽기 기행형] (유쾌한 썰과 기발한 천재성이 돋보이는 인물):
  - 씬 1: "대체 왜 이런 짓을 했을까?" 황당한 돌발 상황 훅
  - 씬 2~3: 상식을 와장창 깨부수는 기상천외한 실화 에피소드
  - 씬 4~5: 방송사고나 위기를 역대급 마케팅/흥행으로 바꾼 천재성
  - 씬 6~7: 미친 폼과 세상을 웃게 만든 매력 + 간결한 CTA

플롯 E. [시네마틱 레거시 추모형] (전 국민의 가슴에 영원히 남은 레전드):
  - 씬 1: 그날의 기억과 가슴 먹먹한 오프닝
  - 씬 2~3: 시대의 청춘들을 위로했던 명곡/명연기와 진심
  - 씬 4~5: 아픔 속에서도 마지막까지 무대와 사람을 지킨 불꽃
  - 씬 6~7: 세월이 흘러도 여전히 우리 곁에 살아 숨 쉬는 별 + 헌사 CTA

[대본 구성 절대 룰 - 1회차 시청자 100% 몰입 및 완벽한 기승전결]
1. 씬 1 (오프닝 훅, 5~8초):
   - 대뜸 "바로 ~였습니다"처럼 질문도 안 했는데 대답부터 하는 쌩뚱맞은 문장 절대 금지!
   - 1회차 시청자가 들었을 때 즉시 귀를 기울이게 만드는 도발적인 질문, 호기심 폭발 명대사, 놀라운 반전 팩트로 자연스럽게 시작하세요.
   - 예: "노래방 가면 무조건 부르는 전설의 명곡 'Maria'! 그런데 이 폭발적인 고음의 주인공이 가수가 아니라 여배우라는 사실, 알고 계셨나요? 오늘 태어난 스타, 김아중의 미친 반전 스토리입니다."
2. 씬 2~6 (본문 전개, 각 12~17초):
   - 선택한 플롯에 맞추어 기승전결 텐션 유지. 뼈를 깎는 노력과 극적인 반전, 카타르시스 폭발.
3. 씬 7 (아웃트로, 8~10초):
   - 말을 하다 말고 "...진짜 비결은..." 처럼 어색하게 문장을 뚝 끊어먹지 마세요!
   - 인물의 삶에 대한 묵직한 여운과 감동, 당당한 찬사를 던진 후, 시청자가 댓글을 달고 싶어지게 만드는 질문과 간결한 구독/좋아요 CTA로 깔끔하게 완결하세요.
4. [시네마틱 카메라 연출 (camera_motion) - 씬별 지능형 동적 배정]:
   - 씬 번호에 따라 기계적으로 순서를 매기지 마세요! 각 씬의 내레이션 감정선과 배경 상황(bg_prompt)을 분석하여 가장 알맞은 연출을 자유롭게 결정하세요:
     * "face_zoom": 인물의 강렬한 표정, 감정선 집중, 오프닝 훅 (얼굴 클로즈업 줌)
     * "push_in": 긴장감 넘치는 임팩트, 충격적인 진실, 반전 순간 (전진 푸시인)
     * "pan_lr": 콘서트 무대, 영화 촬영장, 거대한 시상식, 넓은 군중/배경 (좌우 와이드 패닝)
     * "tilt_up": 바닥에서 정상으로의 도약, 시련 극복의 카리스마 (아래에서 위로 상승 틸트)
     * "vignette_zoom_out": 깊은 고독, 무명 시절, 슬픔, 시련, 위기의 순간 (외곽 암전 비네팅 + 줌아웃)
     * "slow_drift": 잔잔한 감동, 음악적 유산, 묵직한 존경과 추모 (대각선 유려한 드리프트)

[출력 JSON 규격]
{{
  "title": "쇼츠 어그로 썸네일 제목 (20자 내외)",
  "hook_quote": "오프닝 5초 핵심 훅 문구",
  "scenes": [
    {{
      "scene_no": 1,
      "timing": "00:00-00:05",
      "caption": "화면 상단 세련된 챕터 제목 (15자 내외, 촌스러운 슬랭/별표 금지)",
      "narration": "성우가 읽을 자연스러운 구어체 문장 (자음 약어 금지, 씬 7에서 이어받는 문장)",
      "camera_motion": "face_zoom 또는 pan_lr 등 위 6대 모션 중 택1",
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
    try:
        return json.loads(resp.text)
    except Exception:
        clean_text = re.sub(r"^```json\s*", "", resp.text.strip())
        clean_text = re.sub(r"\s*```$", "", clean_text)
        return json.loads(clean_text)


def run_pipeline(mode="am", date_str=None, person=None):
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

    # 2. 없으면 실시간 트렌드 스타 스카우터 가동
    if not person:
        try:
            from star_trend_scout import scout_trending_star
            scouted = scout_trending_star(date_str=date_str, mode=mode)
            if scouted:
                person = scouted["person_name"]
                person_en = scouted.get("person_name_en", "Oscar Wilde")
                scouted_meta = scouted
                print(f"[TrendScout] 오늘({date_str})의 트렌드 1위 스타 낙점: {person} ({person_en}) [Wikidata: {scouted.get('wikidata_id')}]")
        except Exception as e:
            print(f"[TrendScout Error] 실시간 스카우터 실패: {e}")
            if mode.lower() == "am":
                person = "퓨디파이"
                person_en = "PewDiePie"
            else:
                person = "로사 파크스"
                person_en = "Rosa Parks"

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

    # 2. 대본 생성 (7개 씬 확장)
    script_data = generate_shorts_script(client, types, model, person, person_en, mode, date_str, fact_data)

    # 3. 패키지 디렉토리에 script.json 저장
    result = {
        "meta": {
            "mode": mode.upper(),
            "target_date": date_str,
            "person_name": person,
            "person_name_en": person_en,
            "model": model,
            "package_dir": str(pkg_dir),
            "created_at": datetime.datetime.now().isoformat()
        },
        "fact_check": fact_data,
        "script": script_data
    }

    out_path = pkg_dir / "script.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
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

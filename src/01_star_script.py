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
  "recommended_plot": "PLOT_A | PLOT_B | PLOT_C | PLOT_D | PLOT_E 중 최적 1개 선택 (루브릭: PM기일추모=PLOT_E, 오해/상식파괴=PLOT_A, 빈곤/무명/질병/낙방극복=PLOT_B, 라이벌/결승전격돌=PLOT_C, 기상천외/돌발행동=PLOT_D)",
  "plot_reason": "선택한 플롯의 결정적 근거 팩트 1문장 요약",
  "core_conflict": "이 인물의 생애를 관통하는 단 하나의 극적 충돌 또는 결핍 요약",
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

    recommended_plot = fact_data.get("recommended_plot", "PLOT_B")
    plot_reason = fact_data.get("plot_reason", "인물의 핵심 생애에 최적화된 서사")
    core_conflict = fact_data.get("core_conflict", "시련과 결핍을 딛고 스스로를 증명한 여정")

    prompt = f"""당신은 100만 유튜브 쇼츠 채널 '스타이즈본'의 메인 작가입니다.
인물 한글명: {person_name}
인물 영문명: {person_name_en}
모드: {mode_title}
날짜: {date_str}
사전 판정된 최적 서사 플롯: {recommended_plot}
판정 근거: {plot_reason}
단 하나의 핵심 갈등: {core_conflict}

검증된 팩트 데이터:
{json.dumps(fact_data, ensure_ascii=False, indent=2)}

[대본 작성 5대 절대 룰 - 엄격 준수]
1. 1분 컷으로 너무 조급하게 줄이지 마세요! 충분히 흥미진진한 썰을 풀 수 있도록 총 7개 씬(약 80초~100초)으로 구성합니다.
2. 위인전 어투 및 연대기적 나열 절대 금지! 써에이스쇼/OverSimplified처럼 찰지고 몰입감 넘치는 구어체 사용.
3. [팩트 선별 절대 규칙 - '위인전 일대기 나열' 엄격 금지]:
   - 검색된 팩트 목록 전체를 시간순(어린시절 ➔ 데뷔 ➔ 미담)으로 다 읊으려고 하지 마세요!
   - 선택된 플롯의 핵심 갈등({core_conflict})과 무관한 팩트(단순 출생지, 학력, 자잘한 미담)는 과감히 100% 버리세요.
   - 오직 선택된 플롯의 '단 하나의 극적 사건'을 입증하는 핵심 팩트 2~3개만 골라, 씬 2~6에서 현미경처럼 깊게 파고드세요.
4. [TTS 낭독 음성 및 대본 작성 가이드]:
   - [성우 낭독 대본 (narration)]: AI 성우가 오독하지 않도록 자연스러운 구어체 한국어로 작성하세요. 연도와 날짜, 숫자는 성우가 가장 자연스럽게 읽을 수 있는 발음('천구백팔십오년 시월 이십사일', '이천이십년 시월 삼십일일')으로 작성합니다.
   - 자막 표시는 시스템이 전체 대본을 100% 보존하면서 시인성 높은 아라비아 숫자로 자동 변환하므로, 내레이션 문장을 요약하거나 줄이지 마세요.
   - 채팅 자음(ㄱㄱ, ㄷㄷ, ㅋㅋ, ㅠㅠ, ㄹㅇ 등)이나 슬랭 약어 사용 절대 금지.
5. [비주얼 프롬프트 앵커 룰 - 중요]:
   - 씬 1부터 씬 7까지 모든 bg_prompt 첫머리에 반드시 '{person_name_en} with his/her iconic features' 실명과 대표 외형 시그니처를 포함해야 합니다.
   {visual_style_instruction}

[5대 서사 플롯별 씬 1(오프닝 훅) & 씬 7(클로징) 전용 절대 공식]
현재 인물에게 지정된 플롯은 [{recommended_plot}]입니다. 아래 해당 플롯의 전용 공식만을 철저하게 적용하여 씬 1과 씬 7을 집필하세요:

■ 플롯 A. [상식 파괴 & 반전 추적형] (대중의 오해/루머를 깨부수는 서사)
  - 씬 1 훅: 질문형(~알고 계셨나요?) 절대 금지! ➔ 세상이 속았던 "충격적인 가짜 상식 폭로"로 직결.
    (예: "수십 년간 전 세계가 철석같이 믿었던 이 역사, 사실은 100% 새빨간 거짓말이었습니다.")
  - 씬 2~3: 당대 사람들이 왜 이 사람을 오해하고 비난했는가?
  - 씬 4~5: 결정적 역사적 증거로 밝혀낸 진짜 진실의 카타르시스
  - 씬 6: 편견을 박살 낸 인물의 뚝심과 진가
  - 씬 7 클로징: 날짜 나열 금지 ➔ "마침내 밝혀진 진짜 진실"에 대한 묵직한 마침표.
    (예: "편견이 역사를 가릴 때, 끝까지 진실을 지켜낸 이 사람. 비로소 역사가 제자리를 찾았습니다.")

■ 플롯 B. [언더독 카타르시스형] (밑바닥, 결핍, 굴욕을 독기로 뚫어낸 인간 승리 서사)
  - 씬 1 훅: 생일/이름 나열 금지! ➔ 인물 생애에서 "가장 비참했던 굴욕과 차가운 거절의 순간"으로 직결.
    (예: "통장 잔고 24달러. 샌드위치를 씹던 심사위원의 비웃음을 견뎌야 했던 청년이 있었습니다.")
  - 씬 2~3: 단칸방과 냉대 속에서 이를 악물고 갈고닦은 단 하나의 무기
  - 씬 4~5: 단 한 번의 기회에서 세상을 뒤집어버린 도파민 폭발
  - 씬 6: 나를 무시하던 자들을 향한 가장 통쾌한 증명
  - 씬 7 클로징: 오늘 날짜 강박 탈피 ➔ "보란 듯이 증명해낸 거인의 포옹과 시청자 위로".
    (예: "세상이 당신을 무시할 때 기억하세요. 가장 깊은 어둠 속에서, 가장 눈부신 별이 태어납니다.")

■ 플롯 C. [세기의 맞대결 & 라이벌전] (치열한 승부와 라이벌이 있는 스포츠/테크 스타 서사)
  - 씬 1 훅: 숨 막히는 "격돌 1초 전의 현장 중계"로 직결.
    (예: "경기 종료 10초 전, 전 세계 5억 명이 숨죽인 가운데 두 천재의 눈빛이 정면으로 부딪쳤습니다.")
  - 씬 2~3: 천재 vs 천재, 스타일과 성격의 극단적 대비
  - 씬 4~5: 전 세계 수억 명이 숨죽인 결정적 명장면/충돌
  - 씬 6: 역사상 최고의 승부를 완성한 투지와 집념
  - 씬 7 클로징: 승패를 초월한 "위대한 리스펙트의 유산".
    (예: "서로가 있었기에 도달할 수 있었던 전설의 높이. 이것이 우리가 두 거인을 기억하는 이유입니다.")

■ 플롯 D. [도파민 폭발 엽기 기행형] (기발한 천재성과 유쾌한 낭만의 서사)
  - 씬 1 훅: "모두를 경악시킨 희대의 돌발 사건"으로 직결.
    (예: "생방송 도중 갑자기 옷을 찢어버린 희대의 방송사고! 그런데 이 모든 게 철저한 계획이었다면?")
  - 씬 2~3: 상식을 와장창 깨부수는 기상천외한 실화 에피소드
  - 씬 4~5: 방송사고나 위기를 역대급 마케팅/흥행으로 바꾼 천재성
  - 씬 6: 미친 폼과 세상을 웃게 만든 진짜 인간적 매력
  - 씬 7 클로징: "상식에 갇히길 거부한 유쾌한 천재성의 낭만".
    (예: "세상의 모든 룰을 비웃으며 자신만의 판을 짠 사람. 진짜 천재는 언제나 유쾌한 법입니다.")

■ 플롯 E. [시네마틱 레거시 추모형] (전 국민의 가슴에 영원히 남은 레전드 헌정 서사)
  - 씬 1 훅: 가슴을 먹먹하게 만드는 "공감각적 시대 정서 훅".
    (예: "비 내리는 밤, 라디오에서 이 목소리가 흘러나오면 온 국민이 하던 일을 멈추었습니다.")
  - 씬 2~3: 시대의 청춘들을 위로했던 명곡/명연기와 진심
  - 씬 4~5: 아픔 속에서도 마지막까지 무대와 사람을 지킨 불꽃
  - 씬 6: 세월이 흘러도 여전히 우리 곁에 살아 숨 쉬는 별
  - 씬 7 클로징: "영원히 꺼지지 않는 별빛을 향한 조용한 헌사".
    (예: "그는 떠났지만, 그가 남긴 멜로디는 여전히 우리 청춘의 가장 시린 구석을 안아주고 있습니다.")

[시네마틱 카메라 연출 (camera_motion) - 씬별 지능형 동적 배정]
- 각 씬의 내레이션 감정선과 배경 상황(bg_prompt)에 맞추어 자유롭게 배정하세요:
  * "face_zoom": 강렬한 표정, 감정선 집중, 오프닝 훅
  * "push_in": 긴장감 넘치는 임팩트, 충격적인 진실, 반전
  * "pan_lr": 무대, 경기장, 군중, 넓은 배경 와이드 패닝
  * "tilt_up": 바닥에서 정상으로의 도약, 카리스마
  * "vignette_zoom_out": 깊은 고독, 무명 시절, 슬픔, 결핍
  * "slow_drift": 잔잔한 감동, 묵직한 존경과 추모

[출력 JSON 규격]
{{
  "narrative_plot": "{recommended_plot}",
  "plot_selection_reason": "선택한 플롯의 이유 1문장",
  "core_conflict": "{core_conflict}",
  "title": "쇼츠 썸네일 훅 제목 (10~14자 내외, 콜론(:)이나 인물 실명 반복 금지, 예: '버스 한 칸이 바꾼 세상')",
  "hook_quote": "오프닝 5초 핵심 훅 문구 (선택한 플롯 스타일 엄격 반영)",
  "scenes": [
    {{
      "scene_no": 1,
      "timing": "00:00-00:05",
      "caption": "화면 상단 세련된 한글 챕터 제목 (10자 내외 간결한 명사형 구문, 영문 금지)",
      "narration": "성우가 읽을 자연스러운 구어체 문장 (자음 약어 금지, 지정된 플롯 씬 1 공식 준수)",
      "camera_motion": "face_zoom 또는 push_in 등 위 6대 모션 중 택1",
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

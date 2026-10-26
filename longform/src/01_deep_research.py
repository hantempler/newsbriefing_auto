"""롱폼 심층 리서치 엔진 (The Deep Research Engine)
해외 탐사 저널리즘(James Jani) & 다큐멘터리(Magnates Media) 스타일을 위한
Google Search Grounding 기반 인물 심층 다각도 조사 모듈.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

LONGFORM_SRC = Path(__file__).resolve().parent
LONGFORM_DIR = LONGFORM_SRC.parent
ROOT_DIR = LONGFORM_DIR.parent
OUTPUT_DIR = LONGFORM_DIR / "output"
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
GCP_LOCATION = "us-central1"
MODEL_PRO = "gemini-2.5-pro"
MODEL_FLASH = "gemini-2.5-flash"


def get_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def generate_content_with_retry(client, model, contents, config=None, max_retries=4, base_sleep=5):
    current_model = model
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return client.models.generate_content(model=current_model, contents=contents, config=config)
        except Exception as e:
            last_err = e
            err_msg = str(e)
            print(f"[Research Warning] 모델 '{current_model}' 호출 실패 (시도 {attempt}/{max_retries}): {err_msg[:120]}")
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg or attempt >= 2:
                if current_model == MODEL_PRO:
                    print(f"[Research Fallback] {MODEL_FLASH}로 전환하여 재시도...")
                    current_model = MODEL_FLASH
            time.sleep(base_sleep * attempt)
    raise last_err


def conduct_deep_research(person_name: str, english_name: str = "", category: str = "", focus_theme: str = "") -> dict:
    """인물에 대한 8~12분 시네마틱 다큐멘터리용 심층 탐사 리서치 수행."""
    from google.genai import types
    client = get_client()

    print(f"\n=======================================================")
    print(f"🔍 [Longform Deep Research] 대상 인물: {person_name} ({english_name})")
    print(f"=======================================================")

    search_prompt = f"""당신은 넷플릭스와 해외 탐사 다큐멘터리(James Jani, Magnates Media)의 수석 리서처입니다.
다음 인물에 대해 8~12분 분량의 시네마틱 인물 다큐멘터리를 제작하기 위한 방대하고 깊이 있는 사실 조사를 수행하세요:

- 인물명: {person_name} ({english_name})
- 분야: {category}
- 집중 탐구 테마: {focus_theme if focus_theme else '인물의 인생에서 가장 극적인 모순, 위기, 그리고 불멸의 성취'}

필수 조사 영역:
1. [Cold Open 후보]: 이 인물의 생애에서 가장 극적인 순간, 아무도 예상치 못했던 충격적 사건이나 모순적 장면은?
2. [The Genesis (기원과 결핍)]: 유년기의 지독한 가난, 편견, 신체적/환경적 한계, 그리고 그 속에서 싹튼 비정상적인 집념과 재능의 발현 과정.
3. [The Zenith (세계의 정점)]: 세계 최고의 자리에 오른 결정적 사건, 라이벌과의 세기적 대결, 대중을 열광시킨 시그니처 순간.
4. [The Fracture & Crisis (균열과 시련)]: 정점에 도달한 뒤 찾아온 치명적 부상, 스캔들, 여론의 십자포화, 혹은 시스템의 탄압과 내면의 고통.
5. [The Legacy (부활과 불멸의 유산)]: 고난을 극복하고 역사가 된 방식, 그가 현대 사회와 후대에 남긴 삶의 태도와 철학적 울림.
6. [Lesser-Known Anecdotes]: 대중에게 잘 알려지지 않은 결정적 비화 3가지.
7. [Visual & Atmosphere Notes]: 이 인물의 시대를 상징하는 배경, 의상, 조명 톤, 상징적 오브제(16:9 시네마틱 아트워크 프롬프트 제작용 단서).

검증된 팩트와 생생한 정황 묘사를 바탕으로 심도 있게 조사하세요."""

    search_context = ""
    try:
        cfg = types.GenerateContentConfig(
            temperature=0.25,
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
        resp = generate_content_with_retry(client, MODEL_PRO, contents=search_prompt, config=cfg)
        search_context = resp.text
        print(f"[Deep Research] Search Grounding 성공: {len(search_context)}자 확보")
    except Exception as e:
        print(f"[Deep Research] Search Grounding 폴백 (기본 지식베이스 활용): {e}")

    time.sleep(2)

    structure_prompt = f"""다음 조사 내용을 바탕으로 8~12분 다큐멘터리 제작을 위한 구조화된 심층 리서치 도시에(Dossier) JSON을 작성하세요:

조사 텍스트:
{search_context if search_context else "인물에 대한 역사적 공인 사실과 정설을 바탕으로 작성하세요."}

[출력 JSON 스키마]:
{{
  "person": {{
    "name_kr": "{person_name}",
    "name_en": "{english_name}",
    "lifespan": "출생년도-사망년도 (생존시 출생년도-현재)",
    "primary_title": "이 인물을 정의하는 압도적인 수식어",
    "category": "{category}"
  }},
  "dossier": {{
    "cold_open_hook": {{
      "moment_title": "충격적/극적 오프닝 사건 타이틀",
      "year_or_date": "사건 시점",
      "dramatic_contrast": "이 순간이 던지는 거대한 물음과 모순 (시청자가 끝까지 보게 만드는 호기심 갭)",
      "vivid_scene_description": "오프닝 화면으로 묘사할 수 있는 감각적 장면 디테일"
    }},
    "act1_genesis": {{
      "childhood_struggle": "유년기의 결핍, 가난, 혹은 맞닥뜨린 사회적 장벽",
      "defining_spark": "인생을 바꾸게 된 최초의 계기 또는 은사의 발견",
      "relentless_effort": "남들이 보지 못한 곳에서 쏟아부은 치열한 노력 비화"
    }},
    "act2_zenith_and_fracture": {{
      "pinnacle_moment": "세계 정상에 우뚝 선 불멸의 명장면과 대기록",
      "unseen_cost": "성공의 이면에 숨겨져 있던 고립, 번아웃, 혹은 인간적 대가",
      "the_crisis": "인생을 송두리째 흔든 최대의 위기, 스캔들, 혹은 시련"
    }},
    "act3_legacy": {{
      "the_redemption": "위기를 정면 돌파하거나 수용하며 완성한 성숙과 역사적 승리",
      "enduring_philosophy": "이 인물의 삶이 오늘날 우리에게 던지는 묵직한 메시지",
      "immortal_quote": "인물의 실제 육성 명언 (한국어 번역 및 원문)"
    }},
    "secret_anecdotes": [
      {{"title": "비화 1 제목", "detail": "생생한 구체적 사실"}},
      {{"title": "비화 2 제목", "detail": "생생한 구체적 사실"}},
      {{"title": "비화 3 제목", "detail": "생생한 구체적 사실"}}
    ],
    "visual_world_building": {{
      "color_palette": "시네마틱 컬러 팔레트 (예: 차가운 코발트 블루와 거친 골드 앰비언트)",
      "era_details": "당대 배경의 건축, 거리, 의상 질감, 날씨 디테일",
      "symbolic_objects": ["상징적 오브제 1", "오브제 2", "오브제 3"]
    }}
  }}
}}
반드시 순수 JSON만 응답하세요."""

    cfg_json = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json"
    )
    resp_json = generate_content_with_retry(client, MODEL_PRO, contents=structure_prompt, config=cfg_json)

    raw_text = resp_json.text.strip()
    try:
        data = json.loads(raw_text)
    except Exception:
        clean = re.sub(r"^```json\s*", "", raw_text)
        clean = re.sub(r"\s*```$", "", clean)
        data = json.loads(clean)

    safe_name = re.sub(r"[^\w\-_]", "_", person_name)
    out_file = OUTPUT_DIR / f"{safe_name}_deep_research.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ [Deep Research 완료] 저장 경로: {out_file}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="롱폼 심층 리서치 엔진")
    parser.add_argument("--person", type=str, default="웨인 루니", help="인물명 (한글)")
    parser.add_argument("--en", type=str, default="Wayne Rooney", help="인물명 (영문)")
    parser.add_argument("--category", type=str, default="축구 선수 / 레전드", help="분야")
    parser.add_argument("--theme", type=str, default="거리의 싸움꾼 소년이 잉글랜드 역사상 가장 위대한 골잡이가 되기까지의 드라마", help="테마")
    args = parser.parse_args()

    conduct_deep_research(args.person, args.en, args.category, args.theme)

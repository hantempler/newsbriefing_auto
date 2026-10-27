"""롱폼 4막 시네마틱 대본 작성기 (The 4-Act Cinematic Scriptwriter)
James Jani(탐사 서사) + Magnates Media(시네마틱 미장센) + SunnyV2(흥망성쇠 페이싱) 문법을
결합하여 8~12분(9개 씬)의 프리미엄 장문 다큐멘터리 대본 및 연출 지시서를 생성합니다.
"""
import argparse
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
GCP_LOCATION = "global"
MODEL_PRO = "gemini-3.5-flash"
MODEL_FLASH = "gemini-3.5-flash"


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
            print(f"[Script Warning] 모델 '{current_model}' 호출 실패 (시도 {attempt}/{max_retries}): {err_msg[:120]}")
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota exceeded" in err_msg or attempt >= 2:
                if current_model == MODEL_PRO:
                    print(f"[Script Fallback] {MODEL_FLASH}로 전환하여 재시도...")
                    current_model = MODEL_FLASH
            time.sleep(base_sleep * attempt)
    raise last_err


def create_4act_script(dossier_data: dict) -> dict:
    """심층 리서치 도시에(Dossier)를 기반으로 8~12분 4막 시네마틱 대본 생성."""
    from google.genai import types
    client = get_client()

    person_info = dossier_data.get("person", {})
    p_kr = person_info.get("name_kr", "주인공")
    p_en = person_info.get("name_en", "")
    p_title = person_info.get("primary_title", "")
    p_lifespan = person_info.get("lifespan", "")

    print(f"\n=======================================================")
    print(f"✍️ [Longform 4-Act Scriptwriting] {p_kr} ({p_en}) 시네마틱 대본 집필 시작")
    print(f"=======================================================")

    dossier_json_str = json.dumps(dossier_data, ensure_ascii=False, indent=2)

    script_prompt = f"""당신은 넷플릭스 오리지널 다큐멘터리와 James Jani, Magnates Media 스타일의 최고급 시네마틱 다큐멘터리 수석 각본가입니다.
제공된 리서치 도시에를 바탕으로, 시청자가 8~12분 동안 숨죽이고 몰입할 수 있는 **'4막 9씬(Scene 1~9)' 장문 다큐멘터리 대본**을 집필하세요.

[대상 인물]:
- 성명: {p_kr} ({p_en})
- 수식어: {p_title} ({p_lifespan})

[리서치 도시에 데이터]:
{dossier_json_str}

=======================================================
[핵심 연출 및 문법 원칙 - 반드시 준수]
1. **톤앤매너**: 
   - 가벼운 유튜버 말투("여러분 안녕하세요", "구독 좋아요", "신기하지 않나요?") 절대 금지.
   - 단단하고 서늘하며 지적인 다큐멘터리 내레이션 톤. 문장은 호흡이 명확하고 리듬감이 넘쳐야 함.
   - 인물의 업적만 찬양하지 말고, 그가 마주했던 내면의 공포, 고독, 시대의 잔혹한 모순을 솔직하게 파헤칠 것.
2. **분량 가이드라인**:
   - 총 영상 길이: 약 8분 ~ 10분.
   - 총 9개 씬으로 구성되며, 각 씬당 내레이션은 한국어 250~350자 내외로 충실하고 깊이 있게 서술할 것 (총 내레이션 약 2,500 ~ 3,000자).
3. **4막 서사 구성**:
   - **프롤로그 (Scene 1~2)**: [Cold Open] 인생에서 가장 모순적이고 극적인 순간으로 바로 진입. 시청자에게 풀리지 않는 질문을 던져 결박함.
   - **제1막 (Scene 3~4)**: [The Genesis] 어두운 유년기, 결핍과 가난, 아무도 믿어주지 않던 시절, 그러나 피어오른 광기와도 같은 재능.
   - **제2막 (Scene 5~7)**: [The Zenith & The Fracture] 전 세계를 발아래 둔 황금기와 세기의 명장면 ➡️ 그리고 찾아온 충격적인 균열, 스캔들, 여론의 십자포화, 나락의 위기.
   - **제3막 (Scene 8~9)**: [The Legacy] 상처를 딛고 일어선 성숙과 구원 ➡️ 그가 역사와 오늘날 우리에게 남긴 불멸의 삶의 태도와 울림 있는 에필로그.
4. **16:9 와이드 비주얼 프롬프트 (Visual Prompt)**:
   - 씬마다 16:9 가로형 와이드 비율의 고화질 시네마틱 일러스트 프롬프트(영문)를 작성할 것.
   - Anamorphic lens, 8k resolution, dramatic volumetric lighting, cinematic color grading, hyper-realistic character likeness, no text, vertical ratio 금지.
=======================================================

[출력 JSON 규격]:
{{
  "title": "다큐멘터리 제목 (예: 거리의 투사에서 붉은 제국의 황제로: 웨인 루니의 모든 것)",
  "subtitle": "부제 (예: 왜 세상은 그 천재의 야성을 두려워하면서도 열광했는가)",
  "target_duration_minutes": "8-10분",
  "recommended_voice": "Charon (중저음 남성) 또는 Fenrir 또는 Aoede",
  "soundtrack_concept": "전체 음악 컨셉 요약 (예: 음울한 런던의 첼로에서 시작하여 폭발하는 오케스트라 힙합)",
  "scenes": [
    {{
      "scene_num": 1,
      "act": "Prologue",
      "chapter_title": "챕터 제목 (예: 1. 악마의 재능, 심판대에 서다)",
      "estimated_duration_sec": 55,
      "narration": "씬 1 한국어 내레이션 전문 (250~350자. 흡인력 있는 호흡과 딕션)",
      "visual_prompt": "16:9 Cinematic wide-angle illustration prompt in English, hyper-realistic, photorealistic, atmospheric lighting, 8k, no text",
      "camera_direction": "2.5D Parallax slow push-in, subtle film grain, dynamic lighting pulse",
      "audio_cues": "BGM 및 효과음 지시문 (예: 저음의 심장 박동음, 군중의 웅성거림이 먹먹하게 페이드아웃)"
    }},
    ... (Scene 2부터 Scene 9까지 총 9개 씬 완전 수록)
  ],
  "youtube_metadata": {{
    "title": "유튜브 업로드용 매력적인 롱폼 제목 (클릭을 부르는 호기심 갭)",
    "description": "타임스탬프가 포함된 고급스러운 영상 설명글 전문",
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
  }}
}}
반드시 순수 JSON만 응답하세요."""

    cfg_json = types.GenerateContentConfig(
        temperature=0.35,
        response_mime_type="application/json"
    )

    resp_json = generate_content_with_retry(client, MODEL_PRO, contents=script_prompt, config=cfg_json)
    raw_text = resp_json.text.strip()
    try:
        script_data = json.loads(raw_text)
    except Exception:
        clean = re.sub(r"^```json\s*", "", raw_text)
        clean = re.sub(r"\s*```$", "", clean)
        script_data = json.loads(clean)

    safe_name = re.sub(r"[^\w\-_]", "_", p_kr)

    # 1. JSON 저장
    out_json = OUTPUT_DIR / f"{safe_name}_cinematic_script.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)

    # 2. 사람이 읽기 편한 Markdown 리포트 자동 생성
    out_md = OUTPUT_DIR / f"{safe_name}_cinematic_script.md"
    _export_script_markdown(script_data, person_info, out_md)

    print(f"✅ [4-Act Script 집필 완료]")
    print(f"   - JSON 파일: {out_json}")
    print(f"   - Markdown 리뷰: {out_md}")

    return script_data


def _export_script_markdown(script: dict, person: dict, path: Path):
    lines = []
    lines.append(f"# 🎬 [시네마틱 롱폼 다큐멘터리 대본] {script.get('title', '')}\n")
    lines.append(f"> **부제**: {script.get('subtitle', '')}  \n")
    lines.append(f"> **인물**: {person.get('name_kr', '')} ({person.get('name_en', '')}) | **예상 러닝타임**: {script.get('target_duration_minutes', '8~10분')}  \n")
    lines.append(f"> **추천 보이스**: {script.get('recommended_voice', 'Charon')} | **사운드 컨셉**: {script.get('soundtrack_concept', '')}\n")
    lines.append("\n---\n")

    scenes = script.get("scenes", [])
    for s in scenes:
        lines.append(f"### 📍 Scene {s.get('scene_num', '')} [{s.get('act', '')}] : {s.get('chapter_title', '')}")
        lines.append(f"* **예상 시간**: 약 {s.get('estimated_duration_sec', 60)}초")
        lines.append(f"* **카메라 & 연출**: `{s.get('camera_direction', '')}`")
        lines.append(f"* **음향 & BGM**: `{s.get('audio_cues', '')}`")
        lines.append(f"\n> 🎙️ **내레이션**:\n> \n> {s.get('narration', '')}\n")
        lines.append(f"```text\n[16:9 Visual Prompt]:\n{s.get('visual_prompt', '')}\n```\n")
        lines.append("---\n")

    yt = script.get("youtube_metadata", {})
    lines.append("## 📺 유튜브 메타데이터\n")
    lines.append(f"* **추천 업로드 제목**: `{yt.get('title', '')}`\n")
    lines.append(f"* **설명글 및 챕터 타임라인**:\n\n```text\n{yt.get('description', '')}\n```\n")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="롱폼 4막 대본 생성기")
    parser.add_argument("--dossier", type=str, default="", help="기존 조사된 dossier json 경로")
    args = parser.parse_args()

    if args.dossier and Path(args.dossier).exists():
        with open(args.dossier, "r", encoding="utf-8") as f:
            dossier = json.load(f)
    else:
        # 기본 파일럿 인물: 웨인 루니 테스트
        from longform.src._01_deep_research import conduct_deep_research  # wait, relative import
        pass

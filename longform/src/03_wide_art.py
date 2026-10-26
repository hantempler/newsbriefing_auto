"""롱폼 16:9 와이드 시네마틱 아트워크 생성기 (Widescreen Visual Art Engine)
16:9 가로형 (1920x1080) 시네마틱 다큐멘터리 전용 일러스트/사진 생성 모듈.
표준: gemini-nano-banana-2.1 (폴백: gemini-2.5-flash-image), location=global.
"""
import argparse
import io
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
MODEL_IMAGE = "gemini-nano-banana-2.1"
MODEL_FALLBACK = "gemini-2.5-flash-image"


def get_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def fit_16_9_widescreen(raw_bytes: bytes, out_path: Path, target_size=(1920, 1080)):
    """Pillow를 사용하여 무조건 16:9 (1920x1080) 가로 시네마틱 비율로 스마트 크롭/피팅 후 고화질 JPEG 저장."""
    from PIL import Image, ImageOps
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        fitted = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(str(out_path), format="JPEG", quality=95)
    except Exception as e:
        print(f"[Image Warning] Pillow 16:9 피팅 실패({e}), 원본 바이트 저장...")
        out_path.write_bytes(raw_bytes)


def generate_scene_art(prompt: str, out_path: Path) -> bool:
    """단일 16:9 시네마틱 프롬프트에 대한 고해상도 이미지 생성."""
    from google.genai import types
    client = get_client()

    # 프롬프트에 16:9 와이드 및 시네마틱 렌더링 키워드 강화
    enhanced_prompt = f"16:9 widescreen cinematic film still, {prompt}, anamorphic lens flare, photorealistic 8k, dramatic atmospheric lighting, no text, masterpiece"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    models_to_try = [MODEL_IMAGE, MODEL_FALLBACK]

    for model_name in models_to_try:
        try:
            print(f"🎨 [16:9 Art Engine] 모델 '{model_name}' 렌더링 시도...")
            cfg = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            resp = client.models.generate_content(
                model=model_name,
                contents=enhanced_prompt,
                config=cfg
            )
            raw_bytes = None
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                    raw_bytes = part.inline_data.data
                    break

            if raw_bytes:
                fit_16_9_widescreen(raw_bytes, out_path, target_size=(1920, 1080))
                print(f"✅ [16:9 Art 완료] {out_path.name} (1920x1080)")
                return True
        except Exception as e:
            print(f"[Image Warning] 모델 '{model_name}' 실패: {e}")
            time.sleep(2)

    return False


def generate_all_scene_images(script_json_path: str, max_scenes: int = 9) -> list:
    """대본의 모든 씬(Scene 1~9)에 대해 16:9 와이드 아트워크를 순차 생성."""
    path = Path(script_json_path)
    if not path.exists():
        print(f"[Error] 대본 파일을 찾을 수 없습니다: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    title_safe = re.sub(r"[^\w\-_]", "_", data.get("title", "documentary")[:20])
    scenes_dir = OUTPUT_DIR / f"{title_safe}_images"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    scenes = data.get("scenes", [])[:max_scenes]
    generated_files = []

    print(f"\n🖼️ [Widescreen Art Batch] 총 {len(scenes)}개 씬 이미지 생성 시작...")
    for s in scenes:
        s_num = s.get("scene_num", 1)
        prompt = s.get("visual_prompt", "")
        out_file = scenes_dir / f"scene_{s_num:02d}.jpg"
        if out_file.exists() and out_file.stat().st_size > 5000:
            print(f"⏩ [Skip] Scene {s_num} 이미지 이미 존재함: {out_file.name}")
            generated_files.append(str(out_file))
            continue

        ok = generate_scene_art(prompt, out_file)
        if ok:
            generated_files.append(str(out_file))
        time.sleep(2)  # API 쿼터 안전 딜레이

    return generated_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="16:9 와이드 아트워크 생성기")
    parser.add_argument("--script", type=str, default="", help="대본 JSON 파일 경로")
    parser.add_argument("--test_prompt", type=str, default="", help="단일 테스트 프롬프트")
    args = parser.parse_args()

    if args.test_prompt:
        out = OUTPUT_DIR / "test_wide_16_9.jpg"
        generate_scene_art(args.test_prompt, out)
    elif args.script:
        generate_all_scene_images(args.script)

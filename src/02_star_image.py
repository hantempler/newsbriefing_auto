"""스타이즈본 이미지 생성기: 9:16 세로형 쇼츠 일러스트 생성.
PRJ_standard의 02_image.py 계승 + 절대/상대 경로 지원.
표준: gemini-nano-banana-2.1 (폴백: gemini-2.5-flash-image), location=global.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"

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

PROMPT_DEFAULT = (
    "Oscar Wilde with his iconic shoulder-length wavy hair, wearing a purple velvet coat, "
    "smug dandy expression, hyper-realistic retro pop-art caricature, vivid cinematic lighting, vertical 9:16 poster style, 8k, no text"
)


def _gen(client, types, model, prompt):
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )


def _save_fitted_image(raw_bytes, out_path, target_size=(1080, 1920)):
    """Pillow를 사용하여 무조건 9:16 (1080x1920) 세로 비율로 스마트 크롭/피팅 후 고화질 JPEG 저장."""
    import io
    from PIL import Image, ImageOps
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        fitted = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(out_path, format="JPEG", quality=95)
    except Exception as e:
        print(f"[Image Warning] Pillow 9:16 피팅 실패({e}), 원본 바이트 직접 저장...")
        Path(out_path).write_bytes(raw_bytes)


def run_image_test(prompt=PROMPT_DEFAULT, out_path="star_image.jpg"):
    from google import genai
    from google.genai import types

    out = Path(out_path)
    if not out.is_absolute():
        out = OUTPUT_DIR / out_path
    out.parent.mkdir(parents=True, exist_ok=True)

    client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)
    import time
    resp = None
    for attempt in range(4):
        try:
            resp = _gen(client, types, MODEL_IMAGE, prompt)
            break
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_sec = attempt * 5 + 5
                print(f"[Image] 429 쿼터 한도 감지, {wait_sec}초 대기 후 재시도 ({attempt + 1}/4)...")
                time.sleep(wait_sec)
                continue
            print(f"[Image] {MODEL_IMAGE} 실패({e}), 폴백 {MODEL_FALLBACK}")
            try:
                resp = _gen(client, types, MODEL_FALLBACK, prompt)
                break
            except Exception as e2:
                if "429" in str(e2) or "RESOURCE_EXHAUSTED" in str(e2):
                    wait_sec = attempt * 5 + 5
                    print(f"[Image] 폴백 429 쿼터 한도 감지, {wait_sec}초 대기 후 재시도...")
                    time.sleep(wait_sec)
                    continue
                raise

    saved = False
    if resp and resp.candidates:
        candidate = resp.candidates[0]
        content = getattr(candidate, "content", None)
        parts_list = getattr(content, "parts", None) if content else []
        for part in (parts_list or []):
            if getattr(part, "inline_data", None) and part.inline_data:
                _save_fitted_image(part.inline_data.data, out)
                saved = True
                break
            elif getattr(part, "text", None):
                print(f"[Image] text: {part.text[:80]}")

    # 파트가 없거나 안전 필터로 차단된 경우: 캐릭터 상표명 치환 후 재시도
    if not saved:
        print("[Image] 안전 필터 또는 빈 파트 감지, 프롬프트 정제 후 재시도...")
        clean_p = re.sub(r"(Spider-Man|Iron Man|Hulk|Thor|X-Men|Marvel|Avengers)", "superheroes and comic heroes", prompt, flags=re.IGNORECASE)
        try:
            resp_fallback = _gen(client, types, MODEL_FALLBACK, clean_p)
            if resp_fallback and resp_fallback.candidates:
                c2 = resp_fallback.candidates[0]
                cnt2 = getattr(c2, "content", None)
                for part in (getattr(cnt2, "parts", None) or []):
                    if getattr(part, "inline_data", None) and part.inline_data:
                        _save_fitted_image(part.inline_data.data, out)
                        saved = True
                        break
        except Exception as e_fb:
            print(f"[Image] 정제 재시도 실패: {e_fb}")

    # 최후의 수단: 같은 폴더 내 이전 씬 이미지 복사하여 파이프라인 무중단 보장
    if not saved:
        prev_images = sorted(out.parent.glob("scene_*.jpg"))
        if prev_images:
            import shutil
            shutil.copyfile(prev_images[-1], out)
            print(f"[Image] 폴백 이미지 대체 적용 완료: {prev_images[-1].name} -> {out.name}")
            saved = True

    if not saved:
        raise RuntimeError(f"이미지 파트 생성 최종 실패: {out}")

    print(f"[Image] 저장: {out.name} ({out.stat().st_size / 1e3:.0f} KB)")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 9:16 세로형 이미지 생성")
    p.add_argument("--prompt", default=PROMPT_DEFAULT)
    p.add_argument("--out", default="test_image.jpg")
    a = p.parse_args()
    run_image_test(a.prompt, a.out)

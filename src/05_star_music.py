"""스타이즈본 BGM 생성기 (Lyria 2 lyria-002, predict REST).
PRJ_standard의 05_music.py 계승 + 절대/상대 경로 지원.
32.8초 WAV 반환. AM/PM 모드별 프리셋 자동 적용.
"""
import argparse
import base64
import json
import os
import sys
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
GCP_LOCATION = "us-central1"
MODEL = "lyria-002"

PROMPT_AM = "Upbeat quirky funk jazz with bouncy bass, brass horns, lively and energetic rhythm, 30s instrumental"
PROMPT_PM = "Cinematic mellow lo-fi hip-hop with warm electric piano, vinyl crackle, nostalgic and reflective, 30s instrumental"


def run_music_test(prompt=None, mode="am", out_path="star_bgm.wav"):
    import google.auth
    from google.auth.transport.requests import Request
    import requests

    out = Path(out_path)
    if not out.is_absolute():
        out = OUTPUT_DIR / out_path
    out.parent.mkdir(parents=True, exist_ok=True)

    if not prompt:
        prompt = PROMPT_AM if mode.lower() == "am" else PROMPT_PM

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())

    url = (
        f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT_ID}"
        f"/locations/{GCP_LOCATION}/publishers/google/models/{MODEL}:predict"
    )
    print(f"[Music] 요청 ({mode.upper()} 모드): {MODEL}")
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {creds.token}"},
        json={"instances": [{"prompt": prompt, "seed": 42}]},
        timeout=300,
    )
    r.raise_for_status()

    preds = r.json().get("predictions", [])
    if not preds:
        raise RuntimeError(f"예측 결과 없음: {r.text[:200]}")

    p0 = preds[0]
    b64 = p0.get("audioContent") or p0.get("bytesBase64Encoded")
    if not b64:
        raise RuntimeError(f"오디오 키 없음: {list(p0.keys())}")

    out.write_bytes(base64.b64decode(b64))
    print(f"[Music] 저장: {out.name} ({out.stat().st_size / 1e3:.0f} KB)")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 BGM 생성")
    p.add_argument("--mode", default="am", choices=["am", "pm"])
    p.add_argument("--prompt", default=None)
    p.add_argument("--out", default="test_bgm.wav")
    a = p.parse_args()
    run_music_test(prompt=a.prompt, mode=a.mode, out_path=a.out)

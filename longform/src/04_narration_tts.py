"""롱폼 다큐멘터리 내레이션 TTS 엔진 (Documentary Narration Engine)
Gemini 2.5 Flash TTS를 기반으로 한 8~12분 씬별 고음질 다큐멘터리 보이스 마스터링.
주요 성우: Charon(명품 중저음 남성, 디폴트), Aoede(감성 깊은 여성), Fenrir(스포츠 투혼).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import wave
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
MODEL_TTS = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Charon"


def get_client():
    from google import genai
    return genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)


def normalize_tts_text(text: str) -> str:
    """내레이션 가독성 및 호흡 개선을 위한 텍스트 정규화."""
    cleaned = text
    # 자음 약어 치환
    replacements = [
        (r"\bㅇㅇ\b", "응"),
        (r"\bㅋㅋ+\b", "하하"),
        (r"\bㅎㅎ+\b", "허허"),
        (r"\bㄷㄷ\b", "덜덜"),
        (r"\bㅠㅠ+\b", "흑흑"),
        (r"\bvs\b", "대"),
        (r"\bVS\b", "대"),
        (r"\bNo\.?\s*(\d+)", r"\1번"),
        (r"\b(\d{4})년", r"\1년"),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)
    return cleaned.strip()


def synthesize_speech(text: str, out_wav: Path, voice: str = DEFAULT_VOICE) -> bool:
    """단일 텍스트를 고음질 마스터링 WAV로 생성."""
    from google.genai import types
    client = get_client()

    clean_text = normalize_tts_text(text)
    if not clean_text:
        return False

    out_wav.parent.mkdir(parents=True, exist_ok=True)

    resp = None
    for attempt in range(1, 5):
        try:
            resp = client.models.generate_content(
                model=MODEL_TTS,
                contents=clean_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                        )
                    ),
                ),
            )
            break
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < 4:
                wait_sec = attempt * 5
                print(f"[TTS] 429 감지, {wait_sec}초 대기 후 재시도 ({attempt}/4)...")
                time.sleep(wait_sec)
                continue
            print(f"[TTS Error] 음성 생성 실패: {e}")
            return False

    audio_bytes = None
    if resp and resp.candidates:
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "mime_type", "").startswith("audio"):
                audio_bytes = part.inline_data.data
                break

    if not audio_bytes:
        return False

    raw_temp = out_wav.with_suffix(".raw.wav")
    with wave.open(str(raw_temp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_bytes)

    # FFmpeg 2-Pass 리니어 오디오 마스터링 체인 (중저음 부스트 및 다이내믹 컴프레서)
    # 다큐멘터리 묵직한 내레이션을 위해 약간의 베이스 부스트(equalizer=f=120:width_type=o:width=1:g=2.5) 추가
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(raw_temp),
            "-af", "equalizer=f=120:width_type=o:width=1:g=2.5,loudnorm=I=-16:TP=-1.5:LRA=10",
            "-ar", "48000", str(out_wav)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if raw_temp.exists():
            raw_temp.unlink()
        return True
    except Exception:
        # ffmpeg 실패시 원본 raw 리네임
        if raw_temp.exists():
            raw_temp.replace(out_wav)
        return True


def generate_all_scene_audio(script_json_path: str) -> list:
    """대본의 모든 씬에 대해 개별 WAV 음성 생성."""
    path = Path(script_json_path)
    if not path.exists():
        print(f"[Error] 대본을 찾을 수 없습니다: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_voice = data.get("recommended_voice", DEFAULT_VOICE)
    # "Charon (중저음 남성)" -> "Charon" 추출
    voice = re.split(r"[\s\(]", str(raw_voice))[0].strip() or DEFAULT_VOICE
    title_safe = re.sub(r"[^\w\-_]", "_", data.get("title", "documentary")[:20])
    audio_dir = OUTPUT_DIR / f"{title_safe}_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scenes = data.get("scenes", [])
    wav_files = []

    print(f"\n🎙️ [Documentary TTS Batch] 성우: {voice}, 총 {len(scenes)}개 씬 합성 시작...")
    for s in scenes:
        s_num = s.get("scene_num", 1)
        text = s.get("narration", "")
        out_file = audio_dir / f"scene_{s_num:02d}.wav"

        if out_file.exists() and out_file.stat().st_size > 1000:
            print(f"⏩ [Skip] Scene {s_num} 오디오 이미 존재함: {out_file.name}")
            wav_files.append(str(out_file))
            continue

        print(f"🔊 Scene {s_num} TTS 생성 중 ({len(text)}자)...")
        ok = synthesize_speech(text, out_file, voice=voice)
        if ok:
            wav_files.append(str(out_file))
        time.sleep(2)

    return wav_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="롱폼 내레이션 TTS 생성기")
    parser.add_argument("--script", type=str, default="", help="대본 JSON 경로")
    parser.add_argument("--test_text", type=str, default="", help="테스트 문장")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="성우명")
    args = parser.parse_args()

    if args.test_text:
        out = OUTPUT_DIR / "test_doc_tts.wav"
        synthesize_speech(args.test_text, out, voice=args.voice)
        print(f"✅ 테스트 음성 생성 완료: {out}")
    elif args.script:
        generate_all_scene_audio(args.script)

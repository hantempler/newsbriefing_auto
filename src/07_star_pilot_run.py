"""스타이즈본 일괄 에셋 생성 오케스트레이터:
대본 JSON -> 씬별(7씬) 9:16 이미지 + TTS 음성(정규화 적용) + BGM + 실사 썸네일 일괄 생성.
일자별/인물별 패키지 디렉토리(output/YYYYMMDD_AM_인물명/)에 격리 저장.
"""
import argparse
import json
import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"

sys.path.insert(0, str(SRC_DIR))
CRED_PATH = ROOT_DIR / "config" / "application_default_credentials.json"
if CRED_PATH.exists():
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(CRED_PATH))

from importlib import import_module as _im
run_image = _im("02_star_image").run_image_test
run_tts = _im("03_star_tts").run_tts_test
run_music = _im("05_star_music").run_music_test
generate_thumbnail = _im("09_star_thumbnail").generate_shorts_thumbnail


def main(script_path, overwrite_tts=False):
    p = Path(script_path)
    if not p.is_absolute():
        p = ROOT_DIR / script_path

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    script = data["script"]
    mode = meta.get("mode", "AM").lower()

    # 패키지 디렉토리 결정
    pkg_dir = Path(meta.get("package_dir", p.parent))
    assets_dir = pkg_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    person_name = meta.get("person_name", "오스카 와일드")
    person_en = meta.get("person_name_en", "Oscar Wilde")
    hook_quote = script.get("hook_quote", script.get("title", "오늘 태어난 스타"))

    print(f"============================================================")
    print(f"[PilotRun] 스타이즈본 에셋 일괄 생성 시작 (7씬 서사 확장)")
    print(f"           인물: {person_name} ({person_en}), 모드: {mode.upper()}")
    print(f"           패키지 경로: {pkg_dir}")
    print(f"           씬 수: {len(script['scenes'])}씬")
    print(f"============================================================")

    # 0. 대본 분위기 및 인물 맞춤 성우 자동 배정
    selected_voice = meta.get("voice")
    if not selected_voice:
        try:
            get_rec_voice = _im("03_star_tts").get_recommended_voice
            selected_voice = get_rec_voice(person_name, mode, meta.get("category", ""))
        except Exception:
            selected_voice = "Kore"
    print(f"[PilotRun] 맞춤 보이스 선정 완료: {selected_voice}")

    # 1. 씬별 9:16 이미지 및 TTS 생성
    for sc in script["scenes"]:
        n = sc["scene_no"]
        img_file = assets_dir / f"scene_{n}.jpg"
        tts_file = assets_dir / f"scene_{n}.wav"

        bg_prompt = sc.get("bg_prompt", "")
        if "vertical 9:16" not in bg_prompt:
            bg_prompt += ", vertical 9:16 poster style, 8k, no text"

        if img_file.exists() and img_file.stat().st_size > 10000:
            print(f"[PilotRun] Scene {n} 이미지 이미 존재 (스킵)")
        else:
            print(f"\n[PilotRun] Scene {n}/{len(script['scenes'])} 이미지 생성 중...")
            run_image(bg_prompt, out_path=str(img_file))

        narration = sc.get("narration", "")
        if tts_file.exists() and tts_file.stat().st_size > 5000 and not overwrite_tts:
            print(f"[PilotRun] Scene {n} TTS 내레이션 이미 존재 (스킵)")
        else:
            print(f"[PilotRun] Scene {n}/{len(script['scenes'])} TTS 내레이션 생성 중 (Voice: {selected_voice})...")
            run_tts(narration, voice=selected_voice, out_path=str(tts_file))

    # 2. 맞춤 BGM 생성
    bgm_file = assets_dir / "bgm.wav"
    if bgm_file.exists() and bgm_file.stat().st_size > 10000:
        print(f"[PilotRun] BGM 이미 존재 (스킵)")
    else:
        print(f"\n[PilotRun] Lyria BGM 생성 중 ({mode.upper()} 모드)...")
        run_music(mode=mode, out_path=str(bgm_file))

    # 3. 실사 썸네일 생성
    thumb_file = pkg_dir / "thumbnail.jpg"
    target_date = meta.get("target_date", "10-16").replace("-", ".")
    years = meta.get("years", "")
    thumb_hook = script.get("title", hook_quote)
    print(f"\n[PilotRun] 시네마틱 실사 썸네일 합성 중 ({target_date}, 모드: {mode.upper()})...")
    generate_thumbnail(
        person_name=person_name,
        person_name_en=person_en,
        hook_title=thumb_hook,
        out_path=str(thumb_file),
        target_date=target_date,
        mode=mode,
        years=years
    )

    print(f"\n============================================================")
    print(f"[PilotRun] 성공! 모든 에셋 생성 완료:")
    print(f"           - 에셋 폴더: {assets_dir}")
    print(f"           - 썸네일: {thumb_file}")
    print(f"============================================================")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="대본 JSON 기반 에셋 일괄 생성")
    p.add_argument("--script", required=True, help="script.json 파일 경로")
    p.add_argument("--overwrite-tts", action="store_true", help="기존 TTS 음성을 새 마스터링 체인으로 강제 재생성")
    args = p.parse_args()
    main(args.script, overwrite_tts=args.overwrite_tts)

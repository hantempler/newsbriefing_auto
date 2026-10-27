"""롱폼 통합 파이프라인 런처 (Longform Pipeline Runner)
기존 데일리 숏폼 파이프라인과 100% 분리 운영되는 주말 시네마틱 다큐멘터리 런처입니다.

사용법 예시:
  # 1. 파일럿 대본 생성 (리서치 + 4막 시네마틱 각본 작성)
  python longform/run_longform.py --person "웨인 루니" --en "Wayne Rooney" --category "스포츠/축구" --step script

  # 2. 16:9 이미지 및 TTS까지 풀 생성
  python longform/run_longform.py --person "로자 파크스" --en "Rosa Parks" --category "인권/역사" --step all
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Windows cp949 인코딩 처리
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

LONGFORM_DIR = Path(__file__).resolve().parent
ROOT_DIR = LONGFORM_DIR.parent
OUTPUT_DIR = LONGFORM_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 롱폼 src 경로 추가
sys.path.insert(0, str(LONGFORM_DIR / "src"))


def get_modules():
    import importlib.util
    def load_mod(name, file_path):
        spec = importlib.util.spec_from_file_location(name, file_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    mod_research = load_mod("research", LONGFORM_DIR / "src" / "01_deep_research.py")
    mod_script = load_mod("script", LONGFORM_DIR / "src" / "02_act_script.py")
    mod_art = load_mod("art", LONGFORM_DIR / "src" / "03_wide_art.py")
    mod_tts = load_mod("tts", LONGFORM_DIR / "src" / "04_narration_tts.py")
    mod_assemble = load_mod("assemble", LONGFORM_DIR / "src" / "05_cinematic_assemble.py")
    return mod_research, mod_script, mod_art, mod_tts, mod_assemble


def run_pipeline(person: str, en: str, category: str, theme: str, step: str = "script"):
    print(f"\n=======================================================")
    print(f"🎬 [STAR IS BORN : THE ARCHIVE] 롱폼 다큐멘터리 파이프라인 가동")
    print(f"🎯 대상: {person} ({en}) | 분야: {category}")
    print(f"🛡️ 모드: 데일리 숏폼 100% 완전 격리 모드 (Zero Impact)")
    print(f"=======================================================\n")

    mod_research, mod_script, mod_art, mod_tts, mod_assemble = get_modules()

    safe_name = re.sub(r"[^\w\-_]", "_", person)
    dossier_file = OUTPUT_DIR / f"{safe_name}_deep_research.json"
    script_file = OUTPUT_DIR / f"{safe_name}_cinematic_script.json"

    # Step 1: Deep Research
    dossier_data = None
    if dossier_file.exists():
        print(f"📂 [Cache] 기존 리서치 도시에 파일 재사용: {dossier_file.name}")
        with open(dossier_file, "r", encoding="utf-8") as f:
            dossier_data = json.load(f)
    else:
        print(f"🚀 [Step 1] Google Search Grounding 심층 탐사 리서치 시작...")
        dossier_data = mod_research.conduct_deep_research(person, en, category, theme)

    if step == "research":
        print("🏁 리서치 단계 완료.")
        return

    # Step 2: 4-Act Cinematic Script
    script_data = None
    if script_file.exists() and step not in ["force_script"]:
        print(f"📂 [Cache] 기존 시네마틱 대본 재사용: {script_file.name}")
        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)
    else:
        print(f"\n🚀 [Step 2] 4막 시네마틱 8~10분 장문 각본 집필 시작...")
        script_data = mod_script.create_4act_script(dossier_data)

    if step == "script":
        print("\n🏁 [성공] 4막 시네마틱 대본 및 연출 기획서 집필이 완료되었습니다!")
        md_file = OUTPUT_DIR / f"{safe_name}_cinematic_script.md"
        print(f"👉 사람 검토용 리포트: {md_file}")
        return script_data

    # Step 3: 16:9 Artwork Generation
    if step in ["art", "all"]:
        print(f"\n🚀 [Step 3] 16:9 가로형 와이드 시네마틱 아트워크 생성 시작...")
        mod_art.generate_all_scene_images(str(script_file))

    # Step 4: Narration TTS
    if step in ["tts", "all"]:
        print(f"\n🚀 [Step 4] 다큐멘터리 전용 저음 마스터링 내레이션 TTS 생성 시작...")
        mod_tts.generate_all_scene_audio(str(script_file))

    # Step 5: Full Documentary Assembly
    if step in ["assemble", "all"]:
        print(f"\n🚀 [Step 5] 16:9 풀HD 다큐멘터리 최종 영상 합성 및 렌더링 시작...")
        mod_assemble.assemble_full_documentary(str(script_file))

    print("\n🎉 [완료] 주말 롱폼 제작 파이프라인의 모든 요청 작업이 성공적으로 종료되었습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="롱폼 통합 파이프라인 런처")
    parser.add_argument("--person", type=str, default="웨인 루니", help="인물명 (한글)")
    parser.add_argument("--en", type=str, default="Wayne Rooney", help="인물명 (영문)")
    parser.add_argument("--category", type=str, default="스포츠 / 축구 레전드", help="분야")
    parser.add_argument("--theme", type=str, default="길거리 싸움꾼 소년이 잉글랜드 역사상 가장 위대한 골잡이가 되기까지의 드라마", help="테마")
    parser.add_argument("--step", type=str, default="script", choices=["research", "script", "art", "tts", "assemble", "all"], help="실행 단계")
    args = parser.parse_args()

    run_pipeline(args.person, args.en, args.category, args.theme, args.step)

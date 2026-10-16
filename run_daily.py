"""스타이즈본 일일 통합 런처 (One-Click Daily Pipeline).
날짜와 모드(AM/PM)만 지정하면:
1. 팩트체크 및 7씬 서사 대본 생성 (Gemini 2.5 Pro + Search Grounding)
2. 9:16 이미지 7장 + TTS 음성 7개(2-Pass 리니어 고정게인) + Lyria BGM 1곡 + 실사 썸네일 일괄 생성
3. 듀얼 자막 + 6대 동적 카메라 무빙 + SFX + 오디오 덕킹 최종 MP4 합성
4. (선택/자동) 유튜브 쇼츠 자동 업로드 (11_star_upload.py)
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
OUTPUT_DIR = ROOT_DIR / "output"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_pipeline(mode="am", date_str=None, person=None, upload=False, privacy="private", publish_at=None):
    if not date_str:
        # 기본값: 오늘 날짜 (MM-DD)
        today = datetime.datetime.now()
        date_str = today.strftime("%m-%d")

    mode_label = "🌅 [A Star is Born - 탄생 편]" if mode.lower() == "am" else "🌃 [The Legend Falls - 기일 편]"
    print(f"\n{'='*65}")
    print(f"  [스타이즈본 파이프라인 가동] {mode_label}")
    print(f"  날짜: {date_str} / 인물: {person if person else '(캘린더 DB 자동 매칭)'}")
    if upload:
        print(f"  유튜브 업로드: 활성화 (공개상태: {privacy.upper()})")
    print(f"{'='*65}\n")

    # Step 1. 팩트체크 및 대본 생성
    print("▶ [Step 1/4] Google Search Grounding 팩트체크 및 7씬 서사 대본 생성...")
    sys.path.insert(0, str(SRC_DIR))
    import importlib.util
    script_mod_path = SRC_DIR / "01_star_script.py"
    spec1 = importlib.util.spec_from_file_location("star_script", str(script_mod_path))
    star_script = importlib.util.module_from_spec(spec1)
    spec1.loader.exec_module(star_script)

    script_path = star_script.run_pipeline(mode=mode, date_str=date_str, person=person)
    pkg_dir = Path(script_path).parent
    print(f"[Launcher] 패키지 디렉토리 확정: {pkg_dir}")

    # Step 2. 에셋 일괄 생성 (이미지 7장 + TTS 7개 + BGM 1곡 + 실사 썸네일)
    print("\n▶ [Step 2/4] 9:16 이미지 7장 + TTS 음성 7개 + BGM + 실사 썸네일 생성...")
    cmd2 = [sys.executable, str(SRC_DIR / "07_star_pilot_run.py"), "--script", str(script_path)]
    subprocess.run(cmd2, check=True)

    # Step 3. 최종 세로형 쇼츠 합성 (다이내믹 자막 + 6대 동적 무빙 + SFX + 오디오 덕킹)
    print("\n▶ [Step 3/4] 다이내믹 자막 + 카메라 무빙 + SFX + 오디오 덕킹 최종 쇼츠 MP4 렌더링...")
    cmd3 = [sys.executable, str(SRC_DIR / "08_star_assemble.py"), "--script", str(script_path)]
    subprocess.run(cmd3, check=True)

    final_video = pkg_dir / "final_shorts.mp4"
    print(f"\n{'='*65}")
    print(f"  [영상 렌더링 완료!] 100% 최종 쇼츠 MP4 완성: {final_video.name}")
    print(f"{'='*65}\n")

    # Step 4. 유튜브 자동 업로드 (옵션)
    if upload:
        print(f"\n▶ [Step 4/4] YouTube 쇼츠 자동 업로드 중 (Privacy: {privacy.upper()})...")
        cmd4 = [
            sys.executable, str(SRC_DIR / "11_star_upload.py"),
            "--package", str(pkg_dir),
            "--privacy", privacy
        ]
        if publish_at:
            cmd4.extend(["--publish-at", publish_at])
        subprocess.run(cmd4, check=True)
        print(f"[Launcher] 유튜브 쇼츠 등록 프로세스 완료!")

    return pkg_dir


def run_full_daily(date_str=None, upload=True, privacy="private"):
    """자정 자동화용: 하루 2편(AM 탄생 + PM 기일) 연속 일괄 생성 및 업로드."""
    if not date_str:
        today = datetime.datetime.now()
        date_str = today.strftime("%m-%d")

    print(f"\n#################################################################")
    print(f"  [스타이즈본 일일 2편(AM + PM) 무인 전자동 파이프라인 가동]")
    print(f"  기준 일자: {date_str} (자정 자동 배치)")
    print(f"#################################################################\n")

    # 1. AM 편 생성 및 업로드
    print("\n>>> [1/2] AM 탄생 편 가동 시작 <<<")
    run_pipeline(mode="am", date_str=date_str, upload=upload, privacy=privacy)

    # 2. PM 편 생성 및 업로드
    print("\n>>> [2/2] PM 기일 편 가동 시작 <<<")
    run_pipeline(mode="pm", date_str=date_str, upload=upload, privacy=privacy)

    print(f"\n#################################################################")
    print(f"  [대성공] 오늘({date_str}) AM/PM 쇼츠 2편 일괄 제작 및 업로드 완료!")
    print(f"#################################################################\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 통합 쇼츠 런처")
    p.add_argument("--mode", default="am", choices=["am", "pm", "both"], help="제작 모드: am (아침), pm (저녁), both (자정 일괄 2편)")
    p.add_argument("--date", default=None, help="대상 날짜 (MM-DD, 미지정 시 오늘 날짜)")
    p.add_argument("--person", default=None, help="특정 인물 강제 지정")
    p.add_argument("--upload", action="store_true", help="제작 완료 후 유튜브 자동 업로드 수행")
    p.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"], help="유튜브 공개 상태")
    p.add_argument("--publish-at", default=None, help="예약 공개 일시 (ISO 8601 포맷)")
    args = p.parse_args()

    if args.mode == "both":
        run_full_daily(date_str=args.date, upload=args.upload, privacy=args.privacy)
    else:
        run_pipeline(
            mode=args.mode,
            date_str=args.date,
            person=args.person,
            upload=args.upload,
            privacy=args.privacy,
            publish_at=args.publish_at
        )

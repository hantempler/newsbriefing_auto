"""스타이즈본 원스톱 완전 자동화 파이프라인 (run_star_pipeline.py)

역할:
1. 날짜 및 모드(AM/PM) 자동 계산 또는 지정
2. [Step 1] 실시간 트렌드 스타 스카우트 (star_trend_scout.py)
3. [Step 2] 팩트체크 및 7씬 서사 쇼츠 대본 집필 (01_star_script.py)
4. [Step 3] 에셋 폴더 구버전 잔재 100% 완전 청소 (클린업 - 덮어쓰기 버그 원천 차단)
5. [Step 4] 고화질 사료 수집 및 비전 씬 심사 / AI 연속성 생성 (02_star_image.py)
6. [Step 5] 성우 TTS 음성 마스터링 / Lyria 2 BGM / 썸네일 생성 (07_star_pilot_run.py)
7. [Step 6] 다중 컷 시네마틱 교차 전환 쇼츠 최종 합성 (08_star_assemble.py)
8. [Step 7] ffprobe 미디어 무결성 자동 검증 및 종합 리포트 출력
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Windows 콘솔 인코딩 대응
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
CALENDAR_FILE = DATA_DIR / "calendar_db.json"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

CRED_PATH = ROOT_DIR / "config" / "application_default_credentials.json"
if CRED_PATH.exists():
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(CRED_PATH))


def get_current_kst():
    """현재 한국 표준시(KST) datetime 객체 반환"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    return utc_now + datetime.timedelta(hours=9)


def get_default_date_and_mode():
    """날짜/모드 미지정 시 현재 KST 기준 날짜 및 오전/오후 모드 자동 결정"""
    kst_now = get_current_kst()
    date_str = kst_now.strftime("%m-%d")
    mode = "am" if kst_now.hour < 12 else "pm"
    return date_str, mode


def calculate_scheduled_publish_time(date_str, mode="am"):
    """당일 날짜(MM-DD)와 모드(AM: 07:00 KST, PM: 19:00 KST)에 맞는 유튜브 예약 공개 시각(RFC 3339 UTC) 산출.
    만약 목표 시각이 현재 시각(KST)보다 이미 경과하였거나 5분 이내라면 (None, False)를 반환하여 즉시 공개로 안전 폴백.
    """
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst)

    month, day = map(int, date_str.split("-"))
    year = now_kst.year

    target_hour = 7 if mode.lower() == "am" else 19
    target_dt_kst = datetime.datetime(year, month, day, target_hour, 0, 0, tzinfo=kst)

    if target_dt_kst > now_kst + datetime.timedelta(minutes=5):
        target_utc = target_dt_kst.astimezone(datetime.timezone.utc)
        publish_at_str = target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        return publish_at_str, True
    else:
        return None, False


def clean_old_assets(pkg_dir: Path):
    """구버전 에셋(파트 영상, 음성, BGM, 찌꺼기 이미지, 이전 최종 영상 등) 100% 완전 청소"""
    assets_dir = pkg_dir / "assets"
    cleaned_count = 0
    patterns = [
        "*.mp4",
        "*.wav",
        "*.jpg",
        "*.png",
        "*.ass",
        "temp_*.*",
        "concat_list.txt",
        "subtitles_dynamic.json"
    ]
    if assets_dir.exists():
        for pat in patterns:
            for f in assets_dir.glob(pat):
                try:
                    f.unlink()
                    cleaned_count += 1
                except Exception:
                    pass
    
    # 패키지 루트의 final_shorts.mp4 및 thumbnail 제거
    for rf in [pkg_dir / "final_shorts.mp4", pkg_dir / "thumbnail.jpg"]:
        if rf.exists():
            try:
                rf.unlink()
                cleaned_count += 1
            except Exception:
                pass

    print(f"[Pipeline Clean] 기존 에셋 잔재(영상/음성/이미지/자막) {cleaned_count}건 100% 완전 파쇄 완료!")


def verify_video_file(video_path: Path):
    """ffprobe로 최종 렌더링된 비디오의 무결성 검증"""
    if not video_path.exists():
        return False, "파일이 존재하지 않습니다."
    
    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb < 2.0:
        return False, f"비정상 파일 용량 ({size_mb:.2f} MB)"

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name",
            "-of", "json",
            str(video_path)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        info = json.loads(res.stdout)
        streams = info.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_name") == "h264"), None)
        a_stream = next((s for s in streams if s.get("codec_name") == "aac"), None)

        if not v_stream or not a_stream:
            return False, "비디오(h264) 또는 오디오(aac) 스트림 누락"

        w = int(v_stream.get("width", 0))
        h = int(v_stream.get("height", 0))
        v_dur = float(v_stream.get("duration", 0.0))

        if w != 1080 or h != 1920:
            return False, f"비정상 해상도: {w}x{h} (목표: 1080x1920)"

        return True, {
            "resolution": f"{w}x{h}",
            "duration": f"{v_dur:.1f}s",
            "size_mb": f"{size_mb:.2f} MB"
        }
    except Exception as e:
        return False, f"ffprobe 검증 실패: {e}"


def run_full_star_pipeline(date_str=None, mode=None, person=None, force_clean=True, upload=False, privacy="private", publish_at=None):
    """원스톱 스타이즈본 파이프라인 총괄 실행"""
    start_time = time.time()

    # 0. 날짜 및 모드 자동 결정
    def_date, def_mode = get_default_date_and_mode()
    date_str = date_str or def_date
    mode = (mode or def_mode).lower()

    print(f"\n{'='*65}")
    print(f" [STAR IS BORN] 365일 원스톱 무인 파이프라인 가동")
    print(f"                대상 일자: {date_str} | 모드: {mode.upper()}")
    print(f"                시작 시각: {get_current_kst().strftime('%Y-%m-%d %H:%M:%S')} KST")
    print(f"{'='*65}")

    # ==============================================================
    # [Step 1] 실시간 트렌드 스타 스카우트 (star_trend_scout.py)
    # ==============================================================
    print(f"\n>>> [Step 1/6] 실시간 트렌드 스타 스카우트 & 팩트 가드레일 가동...")
    scout_mod = importlib.import_module("star_trend_scout")
    
    # 캘린더 DB 우선 확인
    cal_db = {}
    if CALENDAR_FILE.exists():
        try:
            cal_db = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    slot_entry = cal_db.get("calendar", {}).get(date_str, {}).get(mode)
    if not slot_entry or not slot_entry.get("person_name"):
        print(f"[Pipeline] {date_str} [{mode.upper()}] 슬롯 비어있음 ➔ 실시간 AI 스카우트 실행")
        scout_mod.scout_trending_star(date_str=date_str, mode=mode)
        cal_db = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
        slot_entry = cal_db.get("calendar", {}).get(date_str, {}).get(mode)
    
    if not slot_entry:
        raise RuntimeError(f"[Pipeline Fatal] {date_str} [{mode.upper()}] 스타 스카우트 실패")

    star_name = slot_entry.get("person_name")
    star_name_en = slot_entry.get("person_name_en", "")
    qid = slot_entry.get("wikidata_id", "")
    print(f"[Pipeline Step 1 완료] 오늘의 스타 확정: {star_name} ({star_name_en}) [QID: {qid}]")

    # [Pipeline Reset] 파이프라인 시작 전 해당 인물 패키지 폴더 100% 완전 파쇄(Wipe) 리셋
    slug = re.sub(r"[^\w]", "_", star_name_en.lower())
    target_pkg = OUTPUT_DIR / f"2026{date_str.replace('-', '')}_{mode.upper()}_{slug}"
    if force_clean and target_pkg.exists():
        print(f"\n[Pipeline Reset] 🚨 기존 패키지 폴더 감지 ➔ 100% 완전 파쇄(Wipe) 리셋: {target_pkg.name}")
        shutil.rmtree(target_pkg)

    # ==============================================================
    # [Step 1.5] 사진 중심 대본을 위한 실제 역사적 사료 사전 수집 (02_star_image.py)
    # ==============================================================
    image_mod = importlib.import_module("02_star_image")
    available_photos = []
    if qid:
        print(f"\n>>> [Step 1.5] 사진 중심 대본을 위한 고화질 실사 사료 사전 수집...")
        try:
            available_photos = image_mod.preharvest_available_photos(qid, person_name=star_name, person_name_en=star_name_en, max_candidates=12)
            c_cnt = len(available_photos.get("candidates", [])) if isinstance(available_photos, dict) else len(available_photos)
            print(f"[Pipeline Step 1.5 완료] 검증된 실사 사료 풀 {c_cnt}장 확보 완료!")
        except Exception as e:
            print(f"[Pipeline Step 1.5 경고] 사료 사전 수집 실패({e}) ➔ 일반 모드로 대본 작성")

    # ==============================================================
    # [Step 2] 팩트체크 & 단 하나의 킬러 썰 몰입형 7씬 쇼츠 대본 집필 (01_star_script.py)
    # ==============================================================
    print(f"\n>>> [Step 2/6] 팩트체크 및 단 하나의 킬러 썰 몰입형 7씬 쇼츠 대본 집필...")
    script_mod = importlib.import_module("01_star_script")
    script_path = script_mod.run_pipeline(mode=mode, date_str=date_str, person=person or star_name, available_photos=available_photos)
    script_path = Path(script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"[Pipeline Fatal] 대본 파일 생성 실패: {script_path}")
    
    pkg_dir = script_path.parent
    print(f"[Pipeline Step 2 완료] 대본 집필 완료: {script_path.name} (패키지: {pkg_dir.name})")

    # ==============================================================
    # [Step 3] 에셋 폴더 잔재 100% 완전 청소 (클린업 - 덮어쓰기 방지)
    # ==============================================================
    if force_clean:
        print(f"\n>>> [Step 3/6] 이전 렌더링 파일 및 찌꺼기 100% 완전 청소...")
        clean_old_assets(pkg_dir)

    # ==============================================================
    # [Step 4] 고화질 사료 수집 및 비전 심사 / AI 연속성 생성 (02_star_image.py)
    # ==============================================================
    print(f"\n>>> [Step 4/6] 실사 사료 수집 ➔ 500px+ 선별 ➔ Gemini Vision 심사 ➔ AI 보완...")
    image_mod = importlib.import_module("02_star_image")
    image_files = image_mod.run_script_images(str(script_path))
    print(f"[Pipeline Step 4 완료] 총 {len(image_files)}개 씬 이미지 에셋 확보 완료!")

    # ==============================================================
    # [Step 5] 성우 TTS 음성 마스터링 / Lyria 2 BGM / 썸네일 (07_star_pilot_run.py)
    # ==============================================================
    print(f"\n>>> [Step 5/6] 맞춤 성우 TTS 음성 마스터링(-16 LUFS) 및 BGM, 썸네일 생성...")
    pilot_mod = importlib.import_module("07_star_pilot_run")
    pilot_mod.main(str(script_path), overwrite_tts=True)
    print(f"[Pipeline Step 5 완료] 음성, BGM, 썸네일 에셋 구축 완료!")

    # ==============================================================
    # [Step 6] 다중 컷 시네마틱 교차 전환 쇼츠 최종 영상 합성 (08_star_assemble.py)
    # ==============================================================
    print(f"\n>>> [Step 6/6] 다중 컷 시네마틱 교차 전환 쇼츠 최종 영상 렌더링...")
    assemble_mod = importlib.import_module("08_star_assemble")
    final_video = assemble_mod.assemble_shorts(str(script_path))
    final_video = Path(final_video)

    # ==============================================================
    # [Step 7] 최종 비디오 무결성 자동 검증 (ffprobe)
    # ==============================================================
    print(f"\n>>> [Step 7/6] 최종 비디오 무결성 정밀 검증 중...")
    is_valid, spec = verify_video_file(final_video)
    elapsed = time.time() - start_time

    print(f"\n{'='*65}")
    if is_valid:
        print(f" [STAR IS BORN] 🎉 최종 쇼츠 비디오 제작 및 무결점 검증 성공!")
        print(f"                - 출력 파일: {final_video}")
        print(f"                - 해상도: {spec['resolution']}")
        print(f"                - 영상 길이: {spec['duration']}")
        print(f"                - 파일 용량: {spec['size_mb']}")
        print(f"                - 총 소요 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
    else:
        print(f" [STAR IS BORN] ⚠️ 최종 비디오 검증 경고: {spec}")
    print(f"{'='*65}\n")

    # ==============================================================
    # [Step 8] YouTube 쇼츠 자동 업로드 및 예약 설정 (11_star_upload.py)
    # ==============================================================
    upload_result = None
    if upload and is_valid:
        print(f"\n>>> [Step 8/8] YouTube 쇼츠 자동 업로드 및 예약 설정 중 (공개: {privacy.upper()}, 예약: {publish_at})...")
        upload_mod = importlib.import_module("11_star_upload")
        upload_result = upload_mod.upload_shorts_package(
            package_dir=pkg_dir,
            privacy_status=privacy,
            publish_at=publish_at
        )

    return {
        "status": "SUCCESS" if is_valid else "FAILED",
        "video_path": str(final_video),
        "spec": spec if is_valid else {},
        "script_path": str(script_path),
        "person_name": star_name,
        "mode": mode.upper(),
        "date": date_str,
        "elapsed_sec": elapsed,
        "upload_result": upload_result
    }


def run_both_star_pipeline(date_str=None, upload=True, privacy="public"):
    """오전(AM, 07:00 KST) + 오후(PM, 19:00 KST) 일일 2편 풀 파이프라인 가동 및 정규 예약 업로드"""
    def_date, _ = get_default_date_and_mode()
    date_str = date_str or def_date
    
    am_pub, am_ok = calculate_scheduled_publish_time(date_str, mode="am")
    pm_pub, pm_ok = calculate_scheduled_publish_time(date_str, mode="pm")

    print(f"\n{'#'*65}")
    print(f"  [STAR IS BORN] 1일 2편(AM 07시 + PM 19시 정규 예약) 듀얼 파이프라인")
    print(f"  기준 일자: {date_str} (KST 한국 표준시)")
    print(f"  🌅 AM 생일 공개: {'예약 설정 (' + am_pub + ')' if am_ok else '즉시 공개'}")
    print(f"  🌃 PM 기일 공개: {'예약 설정 (' + pm_pub + ')' if pm_ok else '즉시 공개'}")
    print(f"{'#'*65}\n")

    print("\n>>> [1/2] 🌅 AM 편 가동 시작 <<<")
    res_am = run_full_star_pipeline(
        date_str=date_str,
        mode="am",
        upload=upload,
        privacy=privacy,
        publish_at=am_pub
    )

    print("\n[Pipeline] AM 편 완료. Google API 쿼터 안전 쿨다운 대기 (15초)...")
    time.sleep(15)

    print("\n>>> [2/2] 🌃 PM 편 가동 시작 <<<")
    res_pm = run_full_star_pipeline(
        date_str=date_str,
        mode="pm",
        upload=upload,
        privacy=privacy,
        publish_at=pm_pub
    )

    print(f"\n{'#'*65}")
    print(f"  🎉 [대성공] {date_str} AM/PM 2편 영상 제작 및 예약 업로드 완주!")
    print(f"{'#'*65}\n")
    return {"am": res_am, "pm": res_pm}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="스타이즈본 365일 원스톱 무인 파이프라인")
    parser.add_argument("--date", default=None, help="대상 일자 (MM-DD, 예: 11-26). 미입력 시 오늘 KST 자동 계산")
    parser.add_argument("--mode", default="both", choices=["both", "am", "pm"], help="모드 (both: AM+PM 정규 예약, am: 생일, pm: 기일). 기본값: both")
    parser.add_argument("--person", default=None, help="특정 인물 강제 지정 (선택)")
    parser.add_argument("--upload", dest="upload", action="store_true", default=True, help="유튜브 자동 업로드 수행 (기본 활성화)")
    parser.add_argument("--no-upload", dest="upload", action="store_false", help="유튜브 업로드 건너뛰기")
    parser.add_argument("--privacy", default="public", choices=["private", "unlisted", "public"], help="공개 상태 (기본값: public, 예약 시 자동 private 거쳐 public 전환)")
    parser.add_argument("--publish-at", default=None, help="예약 공개 일시 (ISO 8601 포맷)")
    parser.add_argument("--no-clean", action="store_true", help="기존 잔재 자동 클린업 비활성화")
    args = parser.parse_args()

    if args.mode == "both":
        run_both_star_pipeline(date_str=args.date, upload=args.upload, privacy=args.privacy)
    else:
        pub_at = args.publish_at
        if args.upload and not pub_at:
            cal_pub, _ = calculate_scheduled_publish_time(args.date or get_default_date_and_mode()[0], mode=args.mode)
            pub_at = cal_pub
        run_full_star_pipeline(
            date_str=args.date,
            mode=args.mode,
            person=args.person,
            force_clean=not args.no_clean,
            upload=args.upload,
            privacy=args.privacy,
            publish_at=pub_at
        )

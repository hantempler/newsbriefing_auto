"""롱폼 16:9 시네마틱 영상 합성 엔진 (Widescreen Cinematic Assembler)
각 씬별 16:9 와이드 아트워크 + 내레이션 음성(WAV) + 켄 번스 패럴랙스 무빙 +
넷플릭스 다큐멘터리 스타일의 16:9 자막(ASS) 및 배경 음악을 결합하여
최종 1080p 고화질 가로형 인물 다큐멘터리 영상을 완성합니다.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
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
ASSETS_DIR = ROOT_DIR / "assets"
FONT_DIR = ASSETS_DIR / "fonts"

# 16:9 다큐멘터리 규격
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 30


def get_audio_duration(wav_path: Path) -> float:
    """WAV 파일의 정확한 재생 길이(초) 반환."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())


def generate_scene_ass(script_data: dict, scene_durations: dict, out_ass_path: Path):
    """16:9 와이드 화면에 최적화된 다큐멘터리 자막 생성:
    - 상단 좌측: [CHAPTER 01] 챕터 타이틀 (깔끔한 50pt 화이트)
    - 하단 중앙: 영화 자막 스타일의 한국어 내레이션 (65pt 나눔명조/고딕, 블랙 반투명 박스)
    """
    header = f"""[Script Info]
Title: Star is Born Longform Documentary
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ChapterBadge,Pretendard,38,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,10,0,7,80,80,60,1
Style: DocNarration,Pretendard,54,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,3.5,2,2,120,120,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.0

    scenes = script_data.get("scenes", [])
    for s in scenes:
        s_num = s.get("scene_num", 1)
        dur = scene_durations.get(s_num, float(s.get("estimated_duration_sec", 60)))
        end_time = current_time + dur

        c_start = format_ass_time(current_time)
        c_end = format_ass_time(end_time)

        # 1. 상단 챕터 배지
        ch_title = s.get("chapter_title", f"Scene {s_num}")
        act_name = s.get("act", "")
        badge_text = f"{act_name.upper()} | {ch_title}"
        events.append(f"Dialogue: 1,{c_start},{c_end},ChapterBadge,,0,0,0,,{badge_text}")

        # 2. 하단 내레이션 (문장 단위 청킹 분할)
        narration = s.get("narration", "")
        sentences = re.split(r"(?<=[.!?])\s+", narration.strip())
        sentences = [sen.strip() for sen in sentences if sen.strip()]

        if sentences:
            sec_per_char = dur / max(1, len(narration))
            seg_start = current_time
            for sen in sentences:
                seg_dur = max(1.8, len(sen) * sec_per_char)
                seg_end = min(end_time, seg_start + seg_dur)
                s_t = format_ass_time(seg_start)
                e_t = format_ass_time(seg_end)
                events.append(f"Dialogue: 2,{s_t},{e_t},DocNarration,,0,0,0,,{sen}")
                seg_start = seg_end

        current_time = end_time

    out_ass_path.write_text(header + "\n".join(events), encoding="utf-8")
    print(f"✅ [16:9 Widescreen ASS 생성 완료] {out_ass_path.name}")


def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def assemble_scene_clip(img_path: Path, wav_path: Path, out_clip: Path, zoom_in: bool = True):
    """단일 씬 16:9 켄 번스 무빙 영상(MP4) 생성."""
    dur = get_audio_duration(wav_path)
    total_frames = int(dur * FPS)

    # 부드러운 켄 번스 줌인 / 줌아웃 효과
    if zoom_in:
        zoom_expr = f"min(pzoom+0.0006,1.15)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        zoom_expr = f"if(eq(on,1),1.15,max(1.0,pzoom-0.0006))"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={FPS}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-i", str(wav_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "256k",
        "-t", f"{dur:.2f}",
        str(out_clip)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def assemble_full_documentary(script_json_path: str, out_video_path: Path = None) -> Path:
    """대본, 씬 이미지들, 씬 오디오들을 취합하여 최종 1080p 16:9 다큐멘터리 MP4 영상 완성."""
    path = Path(script_json_path)
    if not path.exists():
        raise FileNotFoundError(f"대본을 찾을 수 없습니다: {path}")

    with open(path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    title_safe = re.sub(r"[^\w\-_]", "_", script_data.get("title", "documentary")[:20])
    scenes_dir = OUTPUT_DIR / f"{title_safe}_images"
    audio_dir = OUTPUT_DIR / f"{title_safe}_audio"
    temp_dir = OUTPUT_DIR / f"{title_safe}_temp_clips"
    temp_dir.mkdir(parents=True, exist_ok=True)

    if out_video_path is None:
        out_video_path = OUTPUT_DIR / f"{title_safe}_full_doc_1080p.mp4"

    scenes = script_data.get("scenes", [])
    scene_durations = {}
    clip_files = []

    print(f"\n🎬 [Full Assembly] 총 {len(scenes)}개 씬 클립 렌더링 시작...")
    for idx, s in enumerate(scenes):
        s_num = s.get("scene_num", idx + 1)
        img_file = scenes_dir / f"scene_{s_num:02d}.jpg"
        wav_file = audio_dir / f"scene_{s_num:02d}.wav"
        clip_file = temp_dir / f"clip_{s_num:02d}.mp4"

        # 이미지나 음성이 없으면 대체 (테스트 이미지 또는 침묵 오디오)
        if not img_file.exists():
            test_img = OUTPUT_DIR / "test_wide_16_9.jpg"
            if test_img.exists():
                img_file = test_img
        if not wav_file.exists():
            test_wav = OUTPUT_DIR / "test_doc_tts.wav"
            if test_wav.exists():
                wav_file = test_wav

        if not img_file.exists() or not wav_file.exists():
            print(f"[Assembly Warning] Scene {s_num} 필수 소스 부재, 건너뜁니다.")
            continue

        dur = get_audio_duration(wav_file)
        scene_durations[s_num] = dur

        if not clip_file.exists() or clip_file.stat().st_size < 1000:
            print(f"🎞️ Scene {s_num} 클립 렌더링 ({dur:.1f}초, 켄 번스 무빙 적용)...")
            zoom_in = (s_num % 2 == 1)
            assemble_scene_clip(img_file, wav_file, clip_file, zoom_in=zoom_in)

        clip_files.append(clip_file)

    if not clip_files:
        raise RuntimeError("렌더링할 수 있는 유효한 씬 클립이 없습니다.")

    # Concat 리스트 작성
    concat_list = temp_dir / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for c in clip_files:
            # Windows 경로 역슬래시 이스케이프
            c_str = str(c).replace("\\", "/")
            f.write(f"file '{c_str}'\n")

    # 16:9 ASS 자막 파일 생성
    ass_file = OUTPUT_DIR / f"{title_safe}_doc_subtitles.ass"
    generate_scene_ass(script_data, scene_durations, ass_file)

    # 1차 비디오 합본 생성
    merged_raw = temp_dir / "merged_raw.mp4"
    print(f"\n📦 [Concat] 전체 씬 합본 및 자막 버닝 시작...")
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(merged_raw)
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 자막 버닝 (ASS 필터 적용)
    ass_path_esc = str(ass_file).replace("\\", "/").replace(":", "\\:")
    burn_cmd = [
        "ffmpeg", "-y", "-i", str(merged_raw),
        "-vf", f"subtitles='{ass_path_esc}'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "19",
        "-c:a", "copy",
        str(out_video_path)
    ]
    subprocess.run(burn_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"🎉 [최종 완성] 16:9 풀HD 다큐멘터리 렌더링 완료: {out_video_path}")
    return out_video_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="롱폼 16:9 영상 합성 엔진")
    parser.add_argument("--script", type=str, required=True, help="대본 JSON 경로")
    args = parser.parse_args()
    assemble_full_documentary(args.script)

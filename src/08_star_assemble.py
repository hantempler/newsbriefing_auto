"""스타이즈본 세로형 쇼츠 최종 완성 엔진 (08_star_assemble.py v3).
잘나가는 유튜브 지식 쇼츠(1분만, 사물궁이, 지식인사이드) 벤치마킹 반영:
1. 1~2.5초 호흡별 다이내믹 자막(Dynamic Chunking) + 옐로우 키워드 하이라이트
2. 시네마틱 켄 번스(Ken Burns) 카메라 워크 (씬별 줌인/줌아웃 다이내믹 모션)
3. 숏폼 전용 굵은 고딕(Gmarket Sans TTF) 볼드 폰트 적용
4. 모바일 UI(제목/사운드/구독 버튼)를 완벽히 피하는 세이프존(MarginV=450)
5. 상단 챕터/토픽 태그 뱃지 + 하단 다이내믹 내레이션 듀얼 레이아웃
6. BGM 볼륨 0.38 밸런스 + 오프닝 0.5초 실사 썸네일 인서트
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
OUTPUT_DIR = ROOT_DIR / "output"
FONT_DIR = ROOT_DIR / "assets" / "fonts"
BGM_VOL = 0.38


def wrap_text_by_pixel(text, font, max_width, draw):
    """픽셀 너비 기준으로 단어 단위 완벽 줄바꿈 (줄 수 제한 없이 유연하게 분할하여 끊김 0% 보장)."""
    words = text.split(" ")
    lines = []
    current_line = ""
    for w in words:
        cand = (current_line + " " + w).strip()
        bbox = draw.textbbox((0, 0), cand, font=font)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_width:
            current_line = cand
        else:
            if current_line:
                lines.append(current_line)
            current_line = w
    if current_line:
        lines.append(current_line)
    return lines


def draw_ending_profile_card(base_img_path, out_img_path, cal_data, mode="AM"):
    """화면을 시원하게 크게 쓰는 풀 와이드 시네마틱 크레딧 시트 (1080x1920 규격 강제 피팅으로 글자 잘림 0%)."""
    from PIL import ImageOps
    raw_img = Image.open(base_img_path).convert("RGBA")
    # 원본 이미지가 1024x1024 등 다른 크기일 경우, 텍스트를 그리기 전에 반드시 1080x1920으로 스마트 피팅!
    if raw_img.size != (1080, 1920):
        img = ImageOps.fit(raw_img, (1080, 1920), method=Image.Resampling.LANCZOS, centering=(0.5, 0.4))
    else:
        img = raw_img
    w, h = 1080, 1920

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_bold_path = FONT_DIR / "GmarketSansTTFBold.ttf"
    win_bold = Path("C:/Windows/Fonts/malgunbd.ttf")
    win_reg = Path("C:/Windows/Fonts/malgun.ttf")

    font_bold = str(font_bold_path) if font_bold_path.exists() else str(win_bold)
    font_badge = ImageFont.truetype(font_bold, 28)
    font_name = ImageFont.truetype(font_bold, 54)
    font_sub = ImageFont.truetype(str(win_reg), 26)
    font_brief = ImageFont.truetype(str(win_bold), 27)
    font_tags = ImageFont.truetype(font_bold, 22)

    person_name = cal_data.get("person_name", "")
    person_en = cal_data.get("person_name_en", "")
    event_date = cal_data.get("event_date", "").replace("-", ".")
    keywords = cal_data.get("keywords", [])
    brief = cal_data.get("brief", "")
    category = cal_data.get("category", "STAR PROFILE")

    pad_x = 70
    max_w = w - (pad_x * 2)  # 940px 전폭 활용

    # 1. 픽셀 기준 자동 줄바꿈 (2줄에 억지로 가두지 않고 3~4줄로 넉넉하게 래핑)
    brief_lines = wrap_text_by_pixel(brief, font_brief, max_w, draw)

    # 2. 필요한 상단 높이 계산 및 시네마틱 그라데이션 페이드 적용
    line_h = 46
    content_bottom = 100 + 48 + 74 + 20 + (len(brief_lines) * line_h) + 20 + 36
    total_tint_h = max(580, content_bottom + 90)

    fade_start = content_bottom - 40
    fade_len = total_tint_h - fade_start
    for y in range(total_tint_h):
        if y < fade_start:
            alpha = 235
        else:
            ratio = (y - fade_start) / max(1, fade_len)
            alpha = int(235 * max(0.0, 1.0 - (ratio ** 1.4)))
        draw.line([(0, y), (w, y)], fill=(8, 12, 22, alpha))

    # 상단 앰비언트 골드 탑 바
    draw.rectangle([0, 0, w, 6], fill=(255, 215, 0, 255))

    cur_y = 110

    # 3. 인물 실명 (58pt 초대형 볼드 - 사족 영문 뱃지 배제)
    draw.text((pad_x, cur_y), person_name, fill=(255, 255, 255, 255), font=font_name)
    cur_y += 72

    # 4. 영문명 + 카테고리 + 날짜 (군더더기 없는 심플 서브타이틀)
    is_pm = str(mode).upper() == "PM" or "별세" in brief or "사망" in brief or "추모" in brief
    date_info = f"{event_date} 별세" if is_pm else f"{event_date} 출생"
    sub_text = f"{person_en}   |   {category}   |   {date_info}"
    draw.text((pad_x, cur_y), sub_text, fill=(200, 215, 245, 230), font=font_sub)
    cur_y += 44

    # 골드 디바이더 라인 (가로 940px)
    draw.line([pad_x, cur_y, w - pad_x, cur_y], fill=(255, 215, 0, 110), width=2)
    cur_y += 24

    # 5. brief 텍스트: 화이트 & 골드 투톤 컬러링으로 시원하게 출력
    colors = [(245, 248, 255, 255), (255, 230, 120, 255), (220, 235, 255, 255), (255, 240, 160, 255)]
    for idx, line in enumerate(brief_lines):
        col = colors[idx % len(colors)]
        draw.text((pad_x, cur_y), line, fill=col, font=font_brief)
        cur_y += line_h

    cur_y += 12

    # 6. 해시태그 태그 줄바꿈 안전 배치
    if keywords:
        tag_parts = [f"#{k.replace(' ', '')}" for k in keywords[:4]]
        tag_lines = wrap_text_by_pixel("   ".join(tag_parts), font_tags, max_w, draw)
        for t_line in tag_lines:
            draw.text((pad_x, cur_y), t_line, fill=(0, 235, 255, 240), font=font_tags)
            cur_y += 34

    final_img = Image.alpha_composite(img, overlay).convert("RGB")
    final_img.save(out_img_path, quality=95)
    print(f"[Assemble] 씬 7 엔딩 풀 와이드 시네마틱 크레딧 시트 완성: {Path(out_img_path).name} (brief {len(brief_lines)}행)")



def run_cmd(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg 에러:\n{r.stderr[-600:]}")
    return r


def get_audio_duration(path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1", str(path)
    ]
    r = run_cmd(cmd)
    return float(r.stdout.strip().split("=")[1])


def render_scene_clip_dynamic(img_file, wav_file, out_mp4, duration, scene_idx, camera_motion=None, sfx_file=None):
    """대본 감정 맞춤형 6대 시네마틱 카메라 모션(얼굴 줌, 패닝, 틸트, 비네팅 등)을 동적으로 렌더링."""
    total_frames = max(30, int(round(duration * 30)))
    step = 0.08 / total_frames
    vignette_prefix = ""

    # 기본 모션 폴백 (지정되지 않은 경우 씬별 자연스러운 교차 순환)
    if not camera_motion:
        default_motions = ["face_zoom", "push_in", "pan_lr", "vignette_zoom_out", "tilt_up", "slow_drift"]
        camera_motion = default_motions[(scene_idx - 1) % len(default_motions)]

    # 1. 모션별 FFmpeg zoompan 및 비주얼 필터 수식 생성 (씬별 시각적 차별화 명확화)
    if camera_motion == "face_zoom":
        # 인물 얼굴/표정 중심 부드럽고 뚜렷한 줌인 (1.00 -> 1.18)
        fast_step = 0.18 / total_frames
        zoom_expr = f"min(1.0+on*{fast_step:.6f}, 1.18)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih*0.35-(ih/zoom*0.35)"

    elif camera_motion == "push_in":
        # 긴장감 넘치는 임팩트 전진 줌 (1.05 -> 1.24)
        fast_step = 0.19 / total_frames
        zoom_expr = f"min(1.05+on*{fast_step:.6f}, 1.24)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih*0.42-(ih/zoom*0.42)"

    elif camera_motion == "pan_lr":
        # 콘서트/무대/넓은 배경: 1.20배 확대 후 좌에서 우로 뚜렷하게 훑는 패닝 (180px 이동)
        zoom_expr = "1.20"
        x_expr = f"(iw-iw/zoom)*(on/{max(1, total_frames - 1)})"
        y_expr = "ih*0.38-(ih/zoom*0.38)"

    elif camera_motion == "tilt_up":
        # 시련 극복/위상 카리스마: 1.20배 확대 후 아래에서 인물 얼굴로 상승 틸트 (180px 이동)
        zoom_expr = "1.20"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"(ih-ih/zoom)*(0.75-0.55*(on/{max(1, total_frames - 1)}))"

    elif camera_motion == "vignette_zoom_out":
        # 시련/고독/위기: 외곽 어두운 비네팅 + 1.20배에서 1.00배로 물러나는 줌아웃
        vignette_prefix = "vignette=PI/4.2,"
        step_out = 0.20 / total_frames
        zoom_expr = f"max(1.20-on*{step_out:.6f}, 1.00)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif camera_motion == "slow_drift":
        # 감동/추모/레거시: 1.15배에서 대각선으로 유려하게 유영하는 시네마틱 무빙
        zoom_expr = "1.15"
        x_expr = f"(iw-iw/zoom)*(0.15+0.7*(on/{max(1, total_frames - 1)}))"
        y_expr = f"(ih-ih/zoom)*(0.2+0.6*(on/{max(1, total_frames - 1)}))"

    if camera_motion == "stable_hold":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30"
    else:
        vf = (
            f"{vignette_prefix}"
            f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d=1:s=1080x1920:fps=30"
        )

    if sfx_file and Path(sfx_file).exists():
        sfx_vol = 0.35 if scene_idx == 1 else 0.20
        # normalize=0으로 내레이션 음성이 50%로 줄어들지 않고 100% 원본 크기 유지
        filter_complex = (
            f"[0:v]{vf}[v];"
            f"[1:a]volume=1.0[nar];"
            f"[2:a]volume={sfx_vol}[sfx];"
            f"[nar][sfx]amix=inputs=2:duration=first:normalize=0[a]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_file),
            "-i", str(wav_file),
            "-i", str(sfx_file),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-t", str(duration), "-pix_fmt", "yuv420p",
            str(out_mp4)
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_file),
            "-i", str(wav_file),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", "-pix_fmt", "yuv420p",
            str(out_mp4)
        ]
    run_cmd(cmd)


def assemble_shorts(script_path):
    p = Path(script_path)
    if not p.is_absolute():
        p = ROOT_DIR / script_path

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    script = data["script"]
    scenes = script["scenes"]
    n_scenes = len(scenes)

    pkg_dir = Path(meta.get("package_dir", p.parent))
    assets_dir = pkg_dir / "assets"
    person_name = meta.get("person_name", "오스카 와일드")

    print(f"============================================================")
    print(f"[Assemble v4] 유튜브 쇼츠 상위 1% 스타일 최종 영상 합성")
    print(f"              인물: {person_name}, 씬 수: {n_scenes}씬")
    print(f"              기능: 다이내믹 자막 + 켄번스 줌 + SFX + 오디오 덕킹 + 루프 엔딩")
    print(f"              패키지: {pkg_dir}")
    print(f"============================================================")

    # 0. 고정 댓글(pinned_comment) 및 유튜브 메타데이터 저장
    yt_meta = script.get("youtube_metadata", {})
    pinned_comment = script.get("pinned_comment", "") or yt_meta.get("pinned_comment", "")
    if pinned_comment:
        pinned_file = pkg_dir / "pinned_comment.txt"
        pinned_file.write_text(pinned_comment, encoding="utf-8")
        print(f"[Assemble] 0. 알고리즘 인게이지먼트용 고정 댓글 저장: {pinned_file.name}")
    if yt_meta:
        yt_meta_file = pkg_dir / "youtube_metadata.json"
        yt_meta_file.write_text(json.dumps(yt_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Assemble] 0. 유튜브 업로드 메타데이터(제목/태그/설명) 저장 완료")

    # 1. SFX 에셋 확보
    import importlib.util
    sfx_py = SRC_DIR / "10_star_sfx.py"
    sfx_assets = {}
    if sfx_py.exists():
        spec_s = importlib.util.spec_from_file_location("star_sfx", str(sfx_py))
        sfx_mod = importlib.util.module_from_spec(spec_s)
        spec_s.loader.exec_module(sfx_mod)
        sfx_assets = sfx_mod.ensure_sfx_assets()
        print(f"[Assemble] SFX 사운드 라이브러리 탑재 완료: {list(sfx_assets.keys())}")

    # 2. 다이내믹 자막 생성 (06_star_subtitle 모듈 호출)
    print(f"[Assemble] 1. 다이내믹 자막(호흡별 분할 + 키워드 옐로우 하이라이트) 생성 중...")
    sub_py = SRC_DIR / "06_star_subtitle.py"
    spec = importlib.util.spec_from_file_location("star_subtitle", str(sub_py))
    sub_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sub_mod)
    ass_path = assets_dir / "subtitles.ass"
    sub_mod.generate_subtitles(p, output_ass=ass_path)

    # 3. 각 씬 음성 길이 측정
    durations = []
    for i in range(1, n_scenes + 1):
        wav_file = assets_dir / f"scene_{i}.wav"
        dur = get_audio_duration(wav_file)
        durations.append(dur)
        print(f"[Assemble] Scene {i} 음성 길이: {dur:.2f}초")

    total_narr_dur = sum(durations)
    print(f"[Assemble] 총 내레이션 길이: {total_narr_dur:.2f}초")

    # 4. 실사 썸네일 동기화 및 오프닝 0.5초 클립 생성 (0초 서브 베이스 Impact SFX 포함)
    thumb_file = pkg_dir / "thumbnail.jpg"
    thumb_py = SRC_DIR / "09_star_thumbnail.py"
    if thumb_py.exists():
        try:
            spec_t = importlib.util.spec_from_file_location("star_thumbnail", str(thumb_py))
            thumb_mod = importlib.util.module_from_spec(spec_t)
            spec_t.loader.exec_module(thumb_mod)
            thumb_hook = script.get("title", script.get("hook_quote", "오늘의 스타"))
            thumb_mod.generate_shorts_thumbnail(
                person_name=person_name,
                person_name_en=meta.get("person_name_en", ""),
                hook_title=thumb_hook,
                out_path=str(thumb_file),
                target_date=meta.get("target_date", "10-16").replace("-", "."),
                mode=meta.get("mode", "AM"),
                years=meta.get("years", "")
            )
        except Exception as e:
            print(f"[Assemble] 썸네일 동기화 경고: {e}")

    part_clips = []
    thumb_clip = assets_dir / "part_0_thumb.mp4"
    if thumb_file.exists():
        print(f"[Assemble] 2. 오프닝 0.5초 실사 썸네일 + 서브 베이스 Impact 클립 생성 중...")
        impact_sfx = sfx_assets.get("impact")
        if impact_sfx and Path(impact_sfx).exists():
            cmd_thumb = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(thumb_file),
                "-i", str(impact_sfx),
                "-t", "0.5",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                "-af", "volume=0.85",
                "-pix_fmt", "yuv420p",
                str(thumb_clip)
            ]
        else:
            cmd_thumb = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(thumb_file),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", "0.5",
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
                str(thumb_clip)
            ]
        run_cmd(cmd_thumb)
        part_clips.append(thumb_clip)


    # 5. 씬별 세로형 비디오 파트 클립 렌더링 (대본 맞춤형 시네마틱 모션 + 전환 Whoosh SFX)
    print(f"[Assemble] 3. 씬별 대본 감정 맞춤형 시네마틱 모션 + 전환 Whoosh SFX 렌더링 중...")
    whoosh_sfx = sfx_assets.get("whoosh")
    for i in range(1, n_scenes + 1):
        part_mp4 = assets_dir / f"part_{i}.mp4"
        img_file = assets_dir / f"scene_{i}.jpg"
        wav_file = assets_dir / f"scene_{i}.wav"
        dur = durations[i - 1]
        sc = scenes[i - 1] if i - 1 < len(scenes) else {}

        # 씬 전환 효과음: 씬 2~7은 whoosh SFX 적용
        scene_sfx = whoosh_sfx if i > 1 else None

        # 카메라 모션 결정 (대본 지정 모션 또는 자동 순환)
        motion = sc.get("camera_motion")

        render_scene_clip_dynamic(img_file, wav_file, part_mp4, dur, scene_idx=i, camera_motion=motion, sfx_file=scene_sfx)
        print(f"[Assemble] Scene {i} 클립 완성 ({dur:.1f}s, Motion: {motion or 'auto'}, SFX: {'Whoosh' if scene_sfx else 'None'})")
        part_clips.append(part_mp4)

    # 6. 클립 Concat
    concat_list = assets_dir / "concat_list.txt"
    concat_list.write_text("".join(f"file '{c.name}'\n" for c in part_clips), encoding="utf-8")
    print(f"[Assemble] 4. 전체 씬 연결 중...")
    run_cmd(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", "concat.mp4"], cwd=assets_dir)

    # 7. ASS 자막 번인 + 오디오 덕킹(Audio Ducking) 적용 BGM 믹싱
    final_shorts = pkg_dir / "final_shorts.mp4"

    # 폰트 디렉토리 옵션 (assets/fonts)
    fonts_opt = ""
    if FONT_DIR.exists():
        fonts_dir_esc = str(FONT_DIR.resolve()).replace("\\", "/").replace(":", "\\:")
        fonts_opt = f":fontsdir='{fonts_dir_esc}'"

    sub_filter = f"ass='subtitles.ass'{fonts_opt}"

    # 오디오 덕킹: 성우 목소리 구간에서 BGM 볼륨 자동 축소 (-12dB), 일시 정지 시 즉각 복원
    ducking_filter_complex = (
        f"[0:v]{sub_filter}[v];"
        f"[0:a]asplit=2[nar][sc];"
        f"[1:a]volume=0.45[bgm];"
        f"[bgm][sc]sidechaincompress=threshold=0.035:ratio=3:attack=50:release=350[ducked_bgm];"
        f"[nar]volume=1.0[v_nar];"
        f"[ducked_bgm]volume=0.90[v_bgm];"
        f"[v_nar][v_bgm]amix=inputs=2:duration=first:normalize=0[aout]"
    )

    print(f"[Assemble] 5. 다이내믹 자막 번인 및 오디오 덕킹(sidechaincompress) 믹싱 중...")
    try:
        cmd_final = [
            "ffmpeg", "-y",
            "-i", "concat.mp4",
            "-stream_loop", "-1", "-i", "bgm.wav",
            "-filter_complex", ducking_filter_complex,
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(final_shorts)
        ]
        run_cmd(cmd_final, cwd=assets_dir)
        print(f"[Assemble] 오디오 덕킹(Sidechain Compression) 믹싱 성공!")
    except Exception as e:
        print(f"[Assemble] 오디오 덕킹 필터 예외 발생, 기본 믹싱으로 폴백: {e}")
        fallback_filter = (
            f"[0:v]{sub_filter}[v];"
            f"[1:a]volume=0.35[bgm];"
            f"[0:a]volume=1.0[nar];"
            f"[nar][bgm]amix=inputs=2:duration=first:normalize=0[aout]"
        )
        cmd_final = [
            "ffmpeg", "-y",
            "-i", "concat.mp4",
            "-stream_loop", "-1", "-i", "bgm.wav",
            "-filter_complex", fallback_filter,
            "-map", "[v]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(final_shorts)
        ]
        run_cmd(cmd_final, cwd=assets_dir)

    size_mb = final_shorts.stat().st_size / 1e6
    final_dur = get_audio_duration(final_shorts)

    print(f"============================================================")
    print(f"[Assemble v4] 대성공! 최종 영상 제작 완료!")
    print(f"              - 출력 파일: {final_shorts}")
    print(f"              - 영상 길이: {final_dur:.1f}초")
    print(f"              - 파일 크기: {size_mb:.2f} MB")
    print(f"============================================================")
    return final_shorts


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 9:16 쇼츠 합성기 v3")
    p.add_argument("--script", required=True, help="script.json 파일 경로")
    args = p.parse_args()
    assemble_shorts(args.script)

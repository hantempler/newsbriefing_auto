"""스타이즈본 다이내믹 쇼츠 자막 엔진 (06_star_subtitle.py).
잘나가는 유튜브 지식 쇼츠(1분만, 사물궁이, 지식인사이드) 자막 공식 완벽 적용:
1. 1~2.5초 단위(8~16글자) 호흡별 어절 분할 (Dynamic Chunking)
2. 시선 강탈 핵심 키워드 옐로우(&H0000E6FF&) 하이라이트
3. 숏폼 표준 굵은 고딕(Gmarket Sans TTF / Black Han Sans) 폰트 지원
4. 모바일 UI(제목/사운드/구독 버튼)를 완벽히 피하는 세이프존(MarginV=450) 배치
5. 상단 챕터/토픽 태그와 하단 다이내믹 자막의 듀얼 레이어 구조
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
CONFIG_DIR = ROOT_DIR / "config"
FONT_DIR = ROOT_DIR / "assets" / "fonts"

CRED_PATH = CONFIG_DIR / "application_default_credentials.json"
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
MODEL_NAME = "gemini-3.5-flash"


def get_audio_duration(path):
    """ffprobe로 오디오 실제 재생 시간 측정."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1", str(path)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return 10.0
    return float(r.stdout.strip().split("=")[1])


def format_ass_time(s):
    """초를 ASS 타임코드 포맷(h:mm:ss.cs)으로 변환."""
    cs = int(round((s % 1) * 100))
    if cs >= 100:
        s += 1
        cs = 0
    return f"{int(s // 3600):d}:{int((s % 3600) // 60):02d}:{int(s % 60):02d}.{cs:02d}"


def get_audio_voice_activity(wav_path, min_silence_dur=0.20, silence_thresh_db=-28):
    """FFmpeg silencedetect로 실제 음성 시작(lead_in) 및 종료 구간을 정밀 측정."""
    cmd = [
        "ffmpeg", "-i", str(wav_path),
        "-af", f"silencedetect=noise={silence_thresh_db}dB:d={min_silence_dur}",
        "-f", "null", "-"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    lead_in = 0.0
    lines = r.stderr.splitlines()
    for line in lines:
        if "silence_start: 0" in line or "silence_start: 0.0" in line:
            continue
        if "silence_end:" in line:
            m = re.search(r"silence_end:\s*([0-9.]+)", line)
            if m and lead_in == 0.0:
                lead_in = min(0.35, float(m.group(1)))
                break
    return lead_in


def rule_based_chunking(text):
    """한국어 구문 및 쉼표 기준 자연스러운 호흡 단위(12~24자) 분할 알고리즘."""
    # 문장 부호(쉼표, 마침표, 느낌표, 물음표) 기준 1차 분할
    raw_parts = re.split(r'([,?!.]\s*)', text)
    tokens = []
    for i in range(0, len(raw_parts), 2):
        chunk = raw_parts[i]
        if i + 1 < len(raw_parts):
            chunk += raw_parts[i + 1]
        chunk = chunk.strip()
        if chunk:
            tokens.append(chunk)

    chunks = []
    for tok in tokens:
        if len(tok) <= 22:
            chunks.append(tok)
        else:
            # 22자가 넘으면 띄어쓰기 중간에서 자연스럽게 분할
            words = tok.split(" ")
            mid = len(words) // 2
            chunks.append(" ".join(words[:mid]))
            chunks.append(" ".join(words[mid:]))

    results = []
    for c in chunks:
        words = [w.strip(".,?!'\"") for w in c.split(" ") if len(w.strip(".,?!'\"")) >= 2]
        longest = max(words, key=len) if words else ""
        results.append({
            "text": c,
            "highlight": longest
        })
    return results


def analyze_dynamic_chunks(scenes):
    """Gemini 2.5 Flash를 이용해 쇼츠 최적화 호흡 단위 청크 및 키워드 하이라이트 추출."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)

        scenes_input = []
        for sc in scenes:
            scenes_input.append({
                "scene_no": sc["scene_no"],
                "caption": sc.get("caption", ""),
                "narration": sc["narration"]
            })

        system_instruction = (
            "당신은 구독자 100만 유튜브 지식 쇼츠의 전문 자막 디렉터입니다.\n"
            "각 씬의 내레이션을 성우의 자연스러운 발화 호흡에 맞추어 2.0~3.5초(약 12~22자 내외)의 '의미 있는 구문 덩어리'로 분할하세요.\n"
            "절대 3~4글자 단위로 자잘하게 파편화하지 마세요! 시청자가 한눈에 읽기 편안한 한 줄 문맥 단위여야 합니다.\n"
            "각 청크마다 시청자의 시선을 순간적으로 사로잡을 수 있는 '핵심 키워드' 1개를 highlight 필드에 지정하세요.\n"
            "텍스트의 원본 글자나 의미를 절대 누락하지 마세요."
        )

        prompt = f"""
아래 씬 목록의 내레이션을 유튜브 쇼츠용 자연스러운 호흡 자막 청크로 분할해주세요.

[입력 씬 목록]
{json.dumps(scenes_input, ensure_ascii=False, indent=2)}

[출력 형식 - 반드시 JSON만 출력]
{{
  "scenes": [
    {{
      "scene_no": 1,
      "chunks": [
        {{
          "text": "노래방 가면 무조건 부르는 전설의 명곡 'Maria'!",
          "highlight": "전설의 명곡"
        }},
        {{
          "text": "그런데 이 노래의 주인공이 가수가 아니라면?",
          "highlight": "가수가 아니라면"
        }}
      ]
    }}
  ]
}}
"""
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        data = json.loads(resp.text.strip())
        print(f"[Subtitle] Gemini AI 기반 다이내믹 자막 청크 분할 완료 ({len(data.get('scenes', []))}씬)")
        return data.get("scenes", [])
    except Exception as e:
        print(f"[Subtitle] Gemini AI 분할 실패, 규칙 기반 폴백 적용: {e}")
        fallback_scenes = []
        for sc in scenes:
            fallback_scenes.append({
                "scene_no": sc["scene_no"],
                "chunks": rule_based_chunking(sc["narration"])
            })
        return fallback_scenes


def build_pro_ass_file(scenes, analyzed_scenes, durations, ass_path, offset=0.0, wav_paths=None):
    """유튜브 쇼츠 프로 스타일 ASS 자막 파일 생성 (Gmarket Sans TTF, 세이프존, 정밀 음성 싱크)."""
    header = """[Script Info]
Title: Star is Born Dynamic Shorts Subtitle
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopChapter, Gmarket Sans TTF, 70, &H00FFFFFF, &H00000000, &H00000000, &H00000000, 1, 0, 0, 0, 100, 100, 0, 0, 1, 7.5, 4.5, 8, 40, 40, 150, 1
Style: DynamicSub, Gmarket Sans TTF, 74, &H00FFFFFF, &H00000000, &H00000000, &H00000000, 1, 0, 0, 0, 100, 100, 0, 0, 1, 7.0, 4.0, 2, 50, 50, 480, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = offset

    analyzed_map = {s["scene_no"]: s["chunks"] for s in analyzed_scenes}

    for sc, duration in zip(scenes, durations):
        s_no = sc["scene_no"]
        scene_start = current_time
        scene_end = current_time + duration

        # 1. 상단 모던 챕터 태그 (번호와 제목 2단 분리, 굵직하고 또렷한 72pt 볼드)
        caption = sc.get("caption", "").strip()
        if caption:
            start_str = format_ass_time(scene_start)
            end_str = format_ass_time(scene_end)
            chapter_text = rf"{{\c&H0000E6FF&\fs54}}0{s_no}\N{{\c&H00FFFFFF&\fs72\b1}}{caption}"
            events.append(f"Dialogue: 1,{start_str},{end_str},TopChapter,,0,0,0,,{chapter_text}")

        # 2. 하단 다이내믹 내레이션 자막
        chunks = analyzed_map.get(s_no, [])
        if not chunks:
            chunks = rule_based_chunking(sc["narration"])

        # 음성 시작 지연(lead-in) 감지
        lead_in = 0.0
        if wav_paths and s_no in wav_paths and wav_paths[s_no].exists():
            lead_in = get_audio_voice_activity(wav_paths[s_no])

        # 문장 부호(쉼표, 마침표) 호흡 가중치를 반영한 시간 배분
        weights = []
        for c in chunks:
            txt = c["text"].strip()
            w = len(txt)
            if txt.endswith((',', '!', '?')):
                w += 3.5
            elif txt.endswith('.'):
                w += 4.5
            weights.append(max(1.0, w))

        total_weight = sum(weights) if sum(weights) > 0 else 1.0
        available_dur = max(1.0, duration - lead_in)

        t_cursor = scene_start + lead_in
        for i, c in enumerate(chunks):
            c_text = c["text"].strip()
            c_highlight = c.get("highlight", "").strip()

            c_dur = available_dur * (weights[i] / total_weight)
            c_end = t_cursor + c_dur
            if i == len(chunks) - 1:
                c_end = scene_end

            # 하이라이트 단어 스타일 태그 적용
            styled_text = c_text
            if c_highlight and c_highlight in styled_text:
                replacement = r"{\c&H0000E6FF&}" + c_highlight + r"{\c&H00FFFFFF&}"
                styled_text = styled_text.replace(c_highlight, replacement, 1)

            st_str = format_ass_time(t_cursor)
            et_str = format_ass_time(c_end)
            events.append(f"Dialogue: 0,{st_str},{et_str},DynamicSub,,0,0,0,,{styled_text}")

            t_cursor = c_end

        current_time = scene_end

    full_ass = header + "\n".join(events)
    ass_path.write_text(full_ass, encoding="utf-8")
    return ass_path


def generate_subtitles(script_path, output_ass=None, thumb_offset=3.0):
    """script.json을 읽고 다이내믹 ASS 자막 파일 생성."""
    p = Path(script_path)
    if not p.is_absolute():
        p = ROOT_DIR / script_path

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    scenes = data["script"]["scenes"]
    pkg_dir = Path(meta.get("package_dir", p.parent))
    assets_dir = pkg_dir / "assets"

    # 오디오 파일 및 길이 수집
    durations = []
    wav_paths = {}
    for sc in scenes:
        s_no = sc["scene_no"]
        wav = assets_dir / f"scene_{s_no}.wav"
        wav_paths[s_no] = wav
        if wav.exists():
            durations.append(get_audio_duration(wav))
        else:
            durations.append(10.0)

    # Gemini 기반 청킹 분석
    analyzed_scenes = analyze_dynamic_chunks(scenes)

    # ASS 파일 저장 경로
    if not output_ass:
        output_ass = assets_dir / "subtitles.ass"
    else:
        output_ass = Path(output_ass)

    # 오프닝 3.0초 썸네일 인서트 오프셋 반영
    offset = float(thumb_offset) if (pkg_dir / "thumbnail.jpg").exists() else 0.0
    build_pro_ass_file(scenes, analyzed_scenes, durations, output_ass, offset=offset, wav_paths=wav_paths)

    # 분석 JSON도 함께 보관
    sub_json = assets_dir / "subtitles_dynamic.json"
    sub_json.write_text(json.dumps(analyzed_scenes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[Subtitle] 정밀 음성 싱크 반영 다이내믹 ASS 자막 생성 완료: {output_ass}")
    return output_ass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="스타이즈본 다이내믹 쇼츠 자막 생성기")
    parser.add_argument("--script", required=True, help="script.json 파일 경로")
    parser.add_argument("--out", default=None, help="출력 subtitles.ass 경로")
    args = parser.parse_args()
    generate_subtitles(args.script, args.out)

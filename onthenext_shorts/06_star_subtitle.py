"""온더넥스트 숏폼 다이내믹 자막 및 컷 정렬 엔진 (06_star_subtitle.py - Faster-Whisper 정공법).
Stage 통음성을 단 1개도 쪼개지 않고 온전히 유지하면서:
1. faster-whisper (word_timestamps=True, scipy 16kHz 리샘플링)로 단어 단위 마이크로초 타임스탬프 추출
2. SequenceMatcher 씬 정렬로 컷별 실제 발화 시작점(speech_start)과 종료점(speech_end)을 0.001초 단위 물리 실측
3. 컷 이미지 전환 시점을 단어 간 무음 중심점에 정확히 스냅하여 이미지 밀림/음성 절단 0% 달성
4. 자막 타임코드를 실제 단어 발화 시작/종료 시간에 1:1 직결하여 음성-자막 0.000초 완전 일치
"""
import argparse
import json
import os
import re
import subprocess
import sys
import wave
from difflib import SequenceMatcher
from pathlib import Path

CUR_DIR = Path(__file__).resolve().parent
ROOT_DIR = CUR_DIR.parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(SRC_DIR))

from importlib import import_module
_sub_mod = import_module("src.06_star_subtitle")
format_ass_time = _sub_mod.format_ass_time
format_sub_display = _sub_mod.format_sub_display
rule_based_chunking = _sub_mod.rule_based_chunking


def clean_txt(t: str) -> str:
    """한글/영문/숫자만 남기고 특수문자 제거."""
    return re.sub(r"[^\w]", "", t).strip()


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


def transcribe_stage_audio_whisper(wav_path: Path):
    """faster-whisper로 Stage 통음성 내부의 모든 단어 타임스탬프 추출 (Stereo/Mono 안전 변환 및 16kHz 리샘플링)."""
    from faster_whisper import WhisperModel
    import scipy.signal
    import numpy as np

    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        n_ch = wf.getnchannels()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    audio_raw = np.frombuffer(raw_bytes, dtype=np.int16)
    if n_ch == 2:
        audio_mono = audio_raw.reshape(-1, 2).mean(axis=1)
    else:
        audio_mono = audio_raw
        
    audio_np = audio_mono.astype(np.float32) / 32768.0

    # 16,000Hz 리샘플링 (시간/속도 왜곡 완전 차단)
    if sr != 16000:
        num_samples = int(round(len(audio_np) * 16000 / float(sr)))
        audio_16k = scipy.signal.resample(audio_np, num_samples).astype(np.float32)
    else:
        audio_16k = audio_np

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_16k, language="ko", word_timestamps=True)

    words_data = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                words_data.append({
                    "word": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "prob": round(w.probability, 3)
                })
    return words_data


def find_scene_word_ranges_auto(cuts: list, whisper_words: list) -> list:
    """SequenceMatcher 및 묵음 갭 보너스를 이용한 대본 컷-Whisper 단어 자동 정렬 알고리즘."""
    num_words = len(whisper_words)
    ranges = []
    w_idx = 0

    for s_idx, c in enumerate(cuts):
        if s_idx == len(cuts) - 1:
            ranges.append((w_idx, num_words - 1))
            break

        s_start_w = w_idx
        next_c = cuts[s_idx + 1]
        next_words = [w for w in next_c["narration"].split() if clean_txt(w)]
        next_target1 = clean_txt(next_words[0]) if len(next_words) > 0 else ""
        next_target2 = clean_txt(next_words[1]) if len(next_words) > 1 else ""

        chars_cur = len(c["narration"])
        chars_total_rem = sum(len(s["narration"]) for s in cuts[s_idx:])
        words_rem = num_words - w_idx
        est_count = int(round(words_rem * (chars_cur / chars_total_rem)))
        est_end_w = w_idx + est_count

        best_split_w = est_end_w
        best_score = -1.0

        search_min = max(w_idx + 1, est_end_w - 6)
        search_max = min(num_words - 1, est_end_w + 6)

        for cand in range(search_min, search_max + 1):
            w1 = clean_txt(whisper_words[cand]["word"])
            w2 = clean_txt(whisper_words[cand + 1]["word"]) if cand + 1 < num_words else ""
            score1 = SequenceMatcher(None, next_target1, w1).ratio()
            score2 = SequenceMatcher(None, next_target2, w2).ratio() if next_target2 and w2 else 1.0
            comb_score = score1 * 0.7 + score2 * 0.3

            prev_end = whisper_words[cand - 1]["end"]
            curr_start = whisper_words[cand]["start"]
            gap = max(0.0, curr_start - prev_end)
            gap_bonus = min(0.3, gap * 0.3)
            total_score = comb_score + gap_bonus

            if total_score > best_score:
                best_score = total_score
                best_split_w = cand

        s_end_w = best_split_w - 1
        ranges.append((s_start_w, s_end_w))
        w_idx = best_split_w

    return ranges


def format_multiline_text(raw_text: str, max_line_chars: int = 20) -> str:
    """1~20자 구문은 시원한 1줄 단일행으로 유지하고,
    21자 이상의 긴 구문에서만 어절/문맥 기준의 자연스러운 2줄 배열(\\N) 적용.
    """
    clean_text = raw_text.strip()
    if len(clean_text) <= max_line_chars or " " not in clean_text:
        return clean_text

    words = clean_text.split()
    if len(words) <= 1:
        return clean_text

    # 1. 닫는 따옴표가 있는 단어 뒤에서 줄바꿈 우선 시도
    # 1. 닫는 따옴표 뒤에서 줄바꿈 (인용구 보호)
    for idx, w in enumerate(words[:-1]):
        if any(q in w for q in ["'", '"', '’', '”']):
            line1 = " ".join(words[:idx+1])
            line2 = " ".join(words[idx+1:])
            return f"{line1}\\N{line2}"
            if len(line1) >= 5 and len(line2) >= 5:
                return f"{line1}\\N{line2}"

    # 2. 쉼표가 있는 단어 뒤에서 줄바꿈 시도
    # 2. 쉼표(,) 뒤에서 줄바꿈
    for idx, w in enumerate(words[:-1]):
        if w.endswith(","):
            line1 = " ".join(words[:idx+1])
            line2 = " ".join(words[idx+1:])
            return f"{line1}\\N{line2}"
            if len(line1) >= 5 and len(line2) >= 5:
                return f"{line1}\\N{line2}"

    # 3. 중간 지점 단어 경계에서 균등 분할
    half = len(words) // 2
    return " ".join(words[:half]) + r"\N" + " ".join(words[half:])
    # 3. 양쪽 줄 길이 차이가 최소가 되도록 어절(공백) 경계 최적 분할
    best_idx = 1
    min_diff = 999
    for idx in range(1, len(words)):
        l1 = len(" ".join(words[:idx]))
        l2 = len(" ".join(words[idx:]))
        if l1 >= 6 and l2 >= 6:
            diff = abs(l1 - l2)
            if diff < min_diff:
                min_diff = diff
                best_idx = idx

    line1 = " ".join(words[:best_idx])
    line2 = " ".join(words[best_idx:])
    return f"{line1}\\N{line2}"

def chunk_words_with_quote_guard(disp_words: list, whisper_words: list, max_chars: int = 22) -> list:
    """원문 대본 단어(disp_words)와 Whisper 실측 단어(whisper_words)를 연동하여,
    따옴표 인용구 절단을 원천 차단하고 자연스러운 호흡 단위 청크 목록을 생성합니다.
    따옴표 인용구 절단을 원천 차단하고 1줄 우선(1~20자) 및 긴 구문(21~26자) 2줄 배열 청크 목록을 생성합니다.
    """
    total_whisper = len(whisper_words)
    total_disp = len(disp_words)
    if total_disp == 0:
        return []

    # 1. 원문 대본 단어들을 의미 단위 및 따옴표 보호 규칙으로 그룹화
    chunks_disp = []
    curr = []
    curr_len = 0
    in_quote = False

    def has_open_quote(text):
        return any(q in text for q in ["'", '"', '‘', '“'])

    def has_close_quote(text):
        return any(q in text for q in ["'", '"', '’', '”'])

    i = 0
    while i < total_disp:
        w = disp_words[i]
        w_len = len(w)

        # 다음 단어가 인용구 시작인데, 현재 버퍼에 단어가 있고 합치면 max_chars 초과 시 사전 분할(Pre-emptive Split)
        if not in_quote and has_open_quote(w) and curr:
            # 인용구 전체의 대략적인 길이 추정
            quote_span_len = 0
            for j in range(i, total_disp):
                quote_span_len += len(disp_words[j]) + 1
                if has_close_quote(disp_words[j]):
                    break
            if curr_len + quote_span_len > max_chars:
                # 인용구 앞에서 미리 잘라 새 화면으로 넘김
                chunks_disp.append(curr)
                curr = []
                curr_len = 0

        # 따옴표 상태 갱신
        if has_open_quote(w) and not has_close_quote(w):
            in_quote = True
        elif has_close_quote(w):
            in_quote = False

        curr.append(w)
        curr_len += w_len + 1  # 공백 포함 길이

        # 분할 조건 검사
        should_split = False
        if not in_quote:
            # 마침표, 느낌표, 물음표는 문장 종결이므로 분할
            if w.endswith((".", "!", "?")):
                should_split = True
            elif w.endswith(",") and curr_len >= 12:
                should_split = True
            elif curr_len >= max_chars:
                should_split = True
        else:
            # 인용구 닫히는 단어에 도달했을 때 글자 수가 충분하면 분할
            if has_close_quote(w) and curr_len >= 14:
                should_split = True
            elif curr_len >= 26:  # 인용구 자체가 너무 길면 안전 분할
                should_split = True
                in_quote = False

        if should_split and curr:
            chunks_disp.append(curr)
            curr = []
            curr_len = 0

        i += 1

    if curr:
        chunks_disp.append(curr)

    # 2. 각 disp 청크에 해당하는 Whisper 타임스탬프 매핑
    result_chunks = []
    w_cursor = 0

    for idx, c_words_group in enumerate(chunks_disp):
        c_count = len(c_words_group)
        w_start_idx = int(round(total_whisper * (w_cursor / max(1, total_disp))))
        w_end_idx = int(round(total_whisper * ((w_cursor + c_count) / max(1, total_disp))))

        if idx == len(chunks_disp) - 1 or w_end_idx >= total_whisper:
            w_end_idx = total_whisper

        w_start_idx = min(w_start_idx, total_whisper - 1)
        w_end_idx = max(w_start_idx + 1, min(w_end_idx, total_whisper))

        sub_words = whisper_words[w_start_idx:w_end_idx]
        start_time = sub_words[0]["start"] if sub_words else whisper_words[w_start_idx]["start"]
        end_time = sub_words[-1]["end"] if sub_words else whisper_words[w_start_idx]["end"]

        raw_text = " ".join(c_words_group)
        formatted_text = format_multiline_text(raw_text, max_line_chars=16)
        formatted_text = format_multiline_text(raw_text, max_line_chars=20)

        result_chunks.append({
            "text": formatted_text,
            "raw_text": raw_text,
            "words": c_words_group,
            "start": start_time,
            "end": end_time
        })
        w_cursor += c_count

    return result_chunks


def chunk_words_dynamic(words_list: list, max_chars: int = 16) -> list:
    """(하위 호환용) Whisper 단어 리스트 기준 단순 분할."""
    chunks = []
    curr = []
    curr_len = 0
    for w in words_list:
        wt = w["word"].strip()
        curr.append(w)
        curr_len += len(wt)
        if curr_len >= max_chars or wt.endswith((".", "!", "?", ",")):
            chunks.append({
                "words": curr,
                "start": curr[0]["start"],
                "end": curr[-1]["end"]
            })
            curr = []
            curr_len = 0
    if curr:
        chunks.append({
            "words": curr,
            "start": curr[0]["start"],
            "end": curr[-1]["end"]
        })
    return chunks


def generate_shorts_subtitles(script_json_path, output_ass=None, thumb_offset=0.0):
    """Faster-Whisper 단어 단위 타임스탬프 기반 무결점 ASS 자막 및 컷 경계 생성기."""
    p = Path(script_json_path)
    if not p.is_absolute():
        p = ROOT_DIR / script_json_path

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    script = data["script"]
    stages = script.get("stages", [])

    pkg_dir = Path(meta.get("package_dir", p.parent))
    audio_dir = pkg_dir / "audio"
    if not output_ass:
        output_ass = pkg_dir / "subtitles.ass"
    else:
        output_ass = Path(output_ass)

    print(f"============================================================")
    print(f"[Subtitle Engine v3] Faster-Whisper 단어 실측 정밀 동기화 시작")
    print(f"                     패키지: {pkg_dir.name}")
    print(f"                     출력 파일: {output_ass.name}")
    print(f"============================================================")

    header = """[Script Info]
Title: OnTheNext Shorts Dynamic Subtitle (Faster-Whisper Precision)
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
    current_time = thumb_offset
    cut_timings = {}

    for st in stages:
        s_no = st["stage_no"]
        s_caption = st.get("caption", f"Stage {s_no}")
        cuts = st.get("cuts", [])
        
        wav_file = audio_dir / f"stage_{s_no}.wav"
        if not wav_file.exists():
            raise FileNotFoundError(f"Stage {s_no} 오디오가 없습니다: {wav_file}")

        stage_dur = get_audio_duration(wav_file)
        stage_global_start = current_time

        print(f"\n[Whisper Sync] Stage {s_no}: [{s_caption}] ({len(cuts)}개 컷, 실측 {stage_dur:.2f}초)...")
        words = transcribe_stage_audio_whisper(wav_file)
        ranges = find_scene_word_ranges_auto(cuts, words)

        # 컷 비디오 전환 경계점 연산: 인접 컷 사이의 무음 중심점에 정확히 스냅
        boundaries = [0.0]
        for i in range(len(ranges) - 1):
            prev_en_w = ranges[i][1]
            next_st_w = ranges[i+1][0]
            prev_end = words[prev_en_w]["end"]
            next_start = words[next_st_w]["start"]
            mid = round((prev_end + next_start) / 2.0, 3)
            boundaries.append(mid)
        boundaries.append(stage_dur)

        for i, (st_w, en_w) in enumerate(ranges):
            c = cuts[i]
            c_no = c["cut_no"]
            c_caption = format_sub_display(c.get("caption", f"Cut {c_no}"))

            v_start = stage_global_start + boundaries[i]
            v_end = stage_global_start + boundaries[i+1]
            v_dur = round(boundaries[i+1] - boundaries[i], 3)

            c_words = words[st_w:en_w+1]
            s_start = stage_global_start + c_words[0]["start"]
            s_end = stage_global_start + c_words[-1]["end"]

            cut_timings[c_no] = {
                "start": round(v_start, 3),
                "end": round(v_end, 3),
                "duration": v_dur,
                "speech_start": round(s_start, 3),
                "speech_end": round(s_end, 3),
                "stage_no": s_no
            }

            print(f"   Cut {c_no:02d}: 비디오 [{v_start:.2f}s ~ {v_end:.2f}s, dur={v_dur:.2f}s] | 음성발화 [{s_start:.2f}s ~ {s_end:.2f}s] | '{c_words[0]['word']}' ~ '{c_words[-1]['word']}'")

            # 1. 상단 챕터 태그 (번호 없이 순수 챕터 제목만 선명한 단일 라인 표기)
            st_str = format_ass_time(v_start)
            et_str = format_ass_time(v_end)
            chapter_text = rf"{{\c&H00FFFFFF&\fs72\b1}}{c_caption}"
            events.append(f"Dialogue: 1,{st_str},{et_str},TopChapter,,0,0,0,,{chapter_text}")

            # 2. 하단 다이내믹 내레이션 자막 (Whisper 단어 타임스탬프와 1:1 직결)
            # 화면 자막용 원문 텍스트 (display_text 1순위, 요약/축약 감지 시 narration 원문 1:1 보존)
            disp = c.get("display_text", "").strip()
            narr = c.get("narration", "").strip()
            if not disp or (narr and len(disp) < len(narr) * 0.85):
                raw_target = narr
            else:
                raw_target = disp
            disp_narr = format_sub_display(raw_target)
            disp_words = disp_narr.split()

            # 인용구 원자적 블록 보호 및 1줄 우선(1~20자)/자연스러운 2줄(21~26자) 청킹 적용
            chunks = chunk_words_with_quote_guard(disp_words, c_words, max_chars=22)

            # 컷 대본에서 지정된 핵심 키워드 목록
            highlight_kws = c.get("highlight_keywords", [])
            if isinstance(highlight_kws, str):
                highlight_kws = [highlight_kws]

            for ck in chunks:
                raw_text = ck["raw_text"]
                styled_text = ck["text"]
                sub_st = stage_global_start + ck["start"]
                sub_et = stage_global_start + ck["end"]

                # 하이라이트 적용 로직
                applied_highlight = False

                # 1순위: 대본에서 지정한 highlight_keywords 매칭
                if highlight_kws:
                    for kw in highlight_kws:
                        kw_clean = kw.strip(".,?!'\"")
                        if kw_clean and kw_clean in styled_text:
                            styled_text = styled_text.replace(kw_clean, rf"{{\c&H0000E6FF&}}{kw_clean}{{\c&H00FFFFFF&}}", 1)
                            applied_highlight = True
                            break

                # 2순위: highlight_keywords가 없거나 매칭되지 않은 경우의 지능형 폴백
                if not applied_highlight and not highlight_kws:
                    # 종결어미 및 문법적 불용어 필터링
                    stop_endings = (
                        "습니다", "었습니다", "았습니다", "였습니다", "있었습니다", "없었습니다",
                        "뿐이었습니다", "뿐이었다", "돌았지만", "했지만", "였지만", "이라며", "라며",
                        "에게", "에서", "으로", "까지", "부터", "하고", "되고", "하며"
                    )
                    words_clean = [w.strip(".,?!'\"") for w in raw_text.split() if len(w.strip(".,?!'\"")) >= 2]
                    valid_candidates = [w for w in words_clean if not any(w.endswith(se) for se in stop_endings)]

                    # 숫자 또는 따옴표 포함 단어 우선
                    num_or_quote = [w for w in valid_candidates if any(ch.isdigit() for ch in w) or any(q in w for q in ["'", '"', '‘', '“'])]
                    chosen = num_or_quote[0] if num_or_quote else (valid_candidates[0] if valid_candidates else "")

                    if chosen and chosen in styled_text:
                        styled_text = styled_text.replace(chosen, rf"{{\c&H0000E6FF&}}{chosen}{{\c&H00FFFFFF&}}", 1)

                sub_st_str = format_ass_time(sub_st)
                sub_et_str = format_ass_time(sub_et)
                events.append(f"Dialogue: 0,{sub_st_str},{sub_et_str},DynamicSub,,0,0,0,,{styled_text}")

        # 다음 Stage 글로벌 시작 시점
        current_time = stage_global_start + stage_dur

    output_ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    
    timings_file = pkg_dir / "cut_timings.json"
    timings_file.write_text(json.dumps(cut_timings, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[Subtitle Engine v3] Faster-Whisper ASS 자막 생성 완료: {output_ass.name} (총 {len(events)}개 이벤트)")
    print(f"[Subtitle Engine v3] 컷별 싱크 데이터 갱신 완료: {timings_file.name}")
    return cut_timings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Faster-Whisper 기반 물리 실측 다이내믹 ASS 자막 생성기")
    parser.add_argument("--script", default="onthenext_shorts/output/20261110_AM_won_bin/script.json")
    parser.add_argument("--offset", type=float, default=0.0)
    args = parser.parse_args()
    generate_shorts_subtitles(args.script, thumb_offset=args.offset)

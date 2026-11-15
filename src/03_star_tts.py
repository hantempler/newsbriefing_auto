"""스타이즈본 내레이션 TTS 생성기.
PRJ_standard의 03_tts.py 계승 + 텍스트 정규화(자음 약어 치환) 필터 탑재.
"""
import argparse
import contextlib
import json
import os
import re
import sys
import time
import wave
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
MODEL_TTS = "gemini-2.5-flash-preview-tts"
VOICE = "Kore"

# 대본 및 인물 분위기별 가용 성우 풀 (Voice Roster)
VOICE_ROSTER = {
    "Charon": "묵직하고 깊은 명품 중저음 남성 (기일 추모, 역사 다큐멘터리)",
    "Fenrir": "파워풀하고 에너지 넘치는 남성 (액션, 스포츠, 투혼 서사)",
    "Puck": "위트 있고 트렌디한 젊은 남성 (힙합, 팝 컬처, 유쾌한 기행/썰)",
    "Orpheus": "지적이고 부드러운 감성 남성 (문학, 철학, 클래식 예술가)",
    "Kore": "밝고 또렷한 표준 안내 톤 여성 (생일 축하, 여배우/아이돌)",
    "Aoede": "깊은 울림과 감성적인 여성 (여성 레전드 추모, 비운의 역사)"
}


def get_recommended_voice(person_name="", mode="AM", category=""):
    """인물 특성, 모드(AM/PM), 장르에 맞춰 최적의 성우를 자동 추천."""
    mode_u = str(mode).upper()
    cat_l = str(category).lower()
    name_l = str(person_name).lower()

    # 1. 기일 추모(PM) 모드: 묵직하고 깊은 헌정 톤 우선
    if mode_u == "PM":
        # 여성 인물인 경우 감성적 여성 톤, 그 외는 명품 중저음 남성 Charon
        female_keywords = ["마리", "오드리", "마릴린", "휘트니", "다이애나", "여왕", "queen", "actress"]
        if any(k in name_l or k in cat_l for k in female_keywords):
            return "Aoede"
        return "Charon"

    # 2. 생일 축하(AM) 모드
    if any(k in cat_l for k in ["action", "sport", "football", "boxing", "hero"]):
        return "Fenrir"
    if any(k in cat_l for k in ["hiphop", "rap", "comedy", "pop"]):
        return "Puck"
    if any(k in cat_l for k in ["classic", "literature", "art", "writer", "poem"]):
        return "Orpheus"
    if any(k in cat_l for k in ["actor", "k-culture", "actress", "idol"]):
        return "Kore"

    return "Kore"


def int_to_korean(num: int) -> str:
    """정수를 자연스러운 한국어 한자 수사로 변환 (예: 1993 -> 천구백구십삼)."""
    if num == 0:
        return "영"
    digits = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
    units = ["", "십", "백", "천"]
    big_units = ["", "만", "억", "조"]

    num_str = str(num)
    chunks = []
    while num_str:
        chunks.append(num_str[-4:])
        num_str = num_str[:-4]

    result = []
    for chunk_idx, chunk in enumerate(chunks):
        chunk_val = int(chunk)
        if chunk_val == 0:
            continue
        chunk_str = ""
        c_len = len(chunk)
        for i, digit in enumerate(chunk):
            d = int(digit)
            pos = c_len - 1 - i
            if d > 0:
                if pos > 0 and d == 1:
                    chunk_str += units[pos]
                else:
                    chunk_str += digits[d] + units[pos]
        chunk_str += big_units[chunk_idx]
        result.append(chunk_str)

    return "".join(reversed(result))


def convert_numbers_to_spoken_korean(text: str) -> str:
    """아라비아 숫자 및 단위를 AI 성우가 자연스럽게 낭독할 수 있는 한국어 구어체로 자동 변환."""
    if not text:
        return ""
    t = text

    # 고유명사 예외 선반영
    t = re.sub(r'블링크\s*182', '블링크 일팔이', t, flags=re.IGNORECASE)

    # 1. 연도: 1800~2099년
    def repl_year(m):
        return f"{int_to_korean(int(m.group(1)))}년"
    t = re.sub(r'(\d{4})년', repl_year, t)

    # 2. 월: 6월(유월), 10월(시월) 등 발음 예외 처리
    month_special = {'6': '유', '06': '유', '10': '시'}
    def repl_month(m):
        val = m.group(1)
        if val in month_special:
            return f"{month_special[val]}월"
        return f"{int_to_korean(int(val))}월"
    t = re.sub(r'(?<!\d)(\d{1,2})월', repl_month, t)

    # 3. 일: 1~31일
    def repl_day(m):
        val = int(m.group(1))
        if 1 <= val <= 31:
            return f"{int_to_korean(val)}일"
        return m.group(0)
    t = re.sub(r'(?<!\d)(\d{1,2})일', repl_day, t)

    # 4. 백분율: % -> 퍼센트
    def repl_percent(m):
        val = m.group(1)
        if "." in val:
            parts = val.split(".")
            return f"{int_to_korean(int(parts[0]))} 점 {int_to_korean(int(parts[1]))} 퍼센트"
        return f"{int_to_korean(int(val))} 퍼센트"
    t = re.sub(r'(\d+(?:\.\d+)?)%', repl_percent, t)

    # 5. 시간 단위: 분, 초
    def repl_time(m):
        return f"{int_to_korean(int(m.group(1)))} {m.group(2)}"
    t = re.sub(r'(\d+)\s*(분|초)', repl_time, t)

    # 6. 도(화상/각도/온도), 위(순위), 세(나이), 대(연령대)
    def repl_unit(m):
        return f"{int_to_korean(int(m.group(1)))}{m.group(2)}"
    t = re.sub(r'(\d+)\s*(도|위|세|대|선)', repl_unit, t)

    # 7. 수량/인원 단위: 명, 개, 번, 회, 곡, 편, 만, 억
    def repl_count(m):
        return f"{int_to_korean(int(m.group(1)))} {m.group(2)}"
    t = re.sub(r'(\d+)\s*(명|개|번|회|곡|편|만|억)', repl_count, t)

    # 8. 잔여 단독 숫자 변환
    def repl_standalone(m):
        return int_to_korean(int(m.group(1)))
    t = re.sub(r'(?<![A-Za-z0-9])(\d+)(?![A-Za-z0-9])', repl_standalone, t)

    return t


def normalize_tts_text(text: str) -> str:
    """TTS 낭독 시 어색한 자음 약어, 슬랭, 아라비아 숫자를 자연스러운 한국어 발음으로 자동 치환."""
    replacements = [
        (r"ㄱㄱ", "고고"),
        (r"ㄷㄷ", "덜덜"),
        (r"ㅋㅋ+", "하하"),
        (r"ㅎㅎ+", "하하"),
        (r"ㅠㅠ+", "흑흑"),
        (r"ㅜㅜ+", "흑흑"),
        (r"ㄹㅇ", "진짜"),
        # (r"쌉(\w+)", r"완전 \1"),
        # (r"개(\w+)", r"완전 \1"),
        # (r"존(\w+)", r"완전 \1"),
        (r"@태그", "태그"),
        (r"#shorts", ""),
    ]
    cleaned = text
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)

    # 아라비아 숫자 ➔ 한국어 낭독 발음 변환
    cleaned = convert_numbers_to_spoken_korean(cleaned)
    return cleaned.strip()


def run_tts_test(text, voice=VOICE, out_path="star_tts.wav"):
    from google import genai
    from google.genai import types

    out = Path(out_path)
    if not out.is_absolute():
        out = OUTPUT_DIR / out_path
    out.parent.mkdir(parents=True, exist_ok=True)

    clean_text = normalize_tts_text(text)
    client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)
    print(f"[TTS] 요청: voice={voice}, {len(clean_text)}자 ('{clean_text[:25]}...')")

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
                print(f"[TTS] 429 쿼터 한도 감지, {wait_sec}초 대기 후 재시도 ({attempt}/4)...")
                time.sleep(wait_sec)
                continue
            raise e

    audio = None
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("audio"):
            audio = part.inline_data.data
            break

    if not audio:
        raise RuntimeError("오디오 데이터 없음")

    # 1. 1차 원시 오디오(Raw 24kHz Mono) 임시 저장
    raw_temp = out.with_suffix(".raw.wav")
    with wave.open(str(raw_temp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio)

    # 2. 방송 표준 2-Pass 리니어 오디오 마스터링 체인 (초반 볼륨 꺼짐 0% 원천 차단)
    import subprocess
    import json
    pre_filter = "highpass=f=80,apad=pad_dur=0.35"

    # Pass 1: 오디오 음량 통계 사전 측정 (print_format=json)
    pass1_cmd = [
        "ffmpeg", "-i", str(raw_temp),
        "-af", f"{pre_filter},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    p1 = subprocess.run(pass1_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    
    m = re.search(r'\{[\s\S]*"input_i"[\s\S]*\}', p1.stderr)
    if m:
        try:
            st = json.loads(m.group(0))
            # Pass 2: linear=true로 0.00초 첫 음절부터 끝까지 균일한 고정 게인 적용 (3초 버퍼 지연 버그 완전 제거)
            master_filter = (
                f"{pre_filter},"
                f"loudnorm=I=-16:TP=-1.5:LRA=11:"
                f"measured_I={st['input_i']}:"
                f"measured_TP={st['input_tp']}:"
                f"measured_LRA={st['input_lra']}:"
                f"measured_thresh={st['input_thresh']}:"
                f"offset={st['target_offset']}:"
                f"linear=true"
            )
        except Exception:
            master_filter = f"{pre_filter},loudnorm=I=-16:TP=-1.5:LRA=11"
    else:
        master_filter = f"{pre_filter},loudnorm=I=-16:TP=-1.5:LRA=11"

    cmd = [
        "ffmpeg", "-y", "-i", str(raw_temp),
        "-af", master_filter,
        "-ar", "44100", "-ac", "2",
        "-c:a", "pcm_s16le",
        str(out)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0:
        print(f"[Warn] 마스터링 실패, 원본 유지: {res.stderr[-200:]}")
        raw_temp.replace(out)
    else:
        if raw_temp.exists():
            raw_temp.unlink()

    with contextlib.closing(wave.open(str(out), "rb")) as wf:
        dur = wf.getnframes() / wf.getframerate()

    print(f"[TTS] 마스터링 완료: {out.name} ({out.stat().st_size / 1e3:.0f} KB, {dur:.1f}초, -16 LUFS 평준화)")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 TTS 생성기")
    p.add_argument("--text", default="내 천재성 외에는 신고할 것이 없다!")
    p.add_argument("--voice", default=VOICE)
    p.add_argument("--out", default="test_tts.wav")
    a = p.parse_args()
    run_tts_test(a.text, a.voice, a.out)

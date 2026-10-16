"""스타이즈본 사운드 이펙트(SFX) 관리 및 합성 모듈 (10_star_sfx.py).
유튜브 쇼츠 1% 연출: 씬 전환(Whoosh), 0초 임팩트(Impact), 자막 하이라이트(Pop).
"""
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT_DIR / "assets" / "sfx"
SFX_DIR.mkdir(parents=True, exist_ok=True)


def ensure_sfx_assets():
    """로열티 프리 합성 SFX(Whoosh, Impact, Pop) 자동 생성 및 보장."""
    whoosh_file = SFX_DIR / "whoosh.wav"
    impact_file = SFX_DIR / "impact.wav"
    pop_file = SFX_DIR / "pop.wav"

    if not whoosh_file.exists():
        # 화이트 노이즈 밴드패스 스윕 기반의 시네마틱 Whoosh
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "anoisesrc=d=0.4:c=white:r=44100,bandpass=f=900:width_type=q:w=2.2,volume=1.2",
            "-af", "afade=t=in:ss=0:d=0.15,afade=t=out:st=0.2:d=0.2",
            str(whoosh_file)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    if not impact_file.exists():
        # 서브 드롭 임팩트 (65Hz 딥 베이스 펀치)
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=f=65:d=0.6:r=44100",
            "-af", "volume=1.4,afade=t=in:ss=0:d=0.03,afade=t=out:st=0.1:d=0.5",
            str(impact_file)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    if not pop_file.exists():
        # 경쾌한 키워드 팝 톤 (1200Hz)
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=f=1200:d=0.12:r=44100",
            "-af", "volume=0.7,afade=t=in:ss=0:d=0.01,afade=t=out:st=0.04:d=0.08",
            str(pop_file)
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    return {
        "whoosh": whoosh_file,
        "impact": impact_file,
        "pop": pop_file
    }


if __name__ == "__main__":
    sfxs = ensure_sfx_assets()
    print("[SFX] 효과음 에셋 확인 완료:", sfxs)

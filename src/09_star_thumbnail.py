"""스타이즈본 시네마틱 숏폼 썸네일 엔진 (09_star_thumbnail.py v2).
2026 유튜브 쇼츠 상위 1% 인물/지식 채널(1분만, 지식인사이드, 너진똑, Magnates Media) 벤치마킹:
1. 1080x1920 Full Bleed 세로 풀 프레임 실사 포트레이트 배치
2. 시네마틱 다크 비네팅 & 그라데이션 섀도우로 인물 표정 강조 및 텍스트 가독성 극대화
3. 초대형 볼드 펀치 헤드라인 (화이트 + 네온 옐로우 투톤 대비, 90pt 대형 폰트)
4. 세련된 미니멀 브랜드 태그 (STAR IS BORN | 10.16)
5. 촌스러운 원색 액자/배너/별표(★) 전면 퇴출
"""
import argparse
import os
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Windows cp949 콘솔 인코딩 대응 (유럽 인물 악센트 문자 등 출력 방어)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DATA_DIR = ROOT_DIR / "data"
PORTRAITS_DIR = DATA_DIR / "portraits"
PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR = ROOT_DIR / "assets" / "fonts"
FONT_BLACK = FONTS_DIR / "BlackHanSans-Regular.ttf"
FONT_GMARKET = FONTS_DIR / "GmarketSansTTFBold.ttf"


def download_portrait(person_name, person_name_en=None):
    """위키피디아 REST API를 통해 실사 초상화/사진 고화질 다운로드."""
    names_to_try = [person_name_en, person_name] if person_name_en else [person_name]
    headers = {"User-Agent": "StarIsBornBot/1.0 (contact@starisborn.com)"}

    slug = re.sub(r"[^\w]", "_", (person_name_en or person_name).lower())
    saved_file = PORTRAITS_DIR / f"{slug}.jpg"
    if saved_file.exists() and saved_file.stat().st_size > 5000:
        return saved_file

    for name in names_to_try:
        if not name:
            continue
        try:
            api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(name.replace(' ', '_'))}"
            r = requests.get(api_url, headers=headers, timeout=15)
            if r.status_code == 200:
                d = r.json()
                thumb_url = d.get("thumbnail", {}).get("source")
                if thumb_url:
                    # 더 큰 고해상도(800px) 요청
                    high_url = re.sub(r"/\d+px-", "/800px-", thumb_url)
                    r_img = requests.get(high_url, headers=headers, timeout=20)
                    if r_img.status_code != 200:
                        r_img = requests.get(thumb_url, headers=headers, timeout=20)
                    if r_img.status_code == 200 and len(r_img.content) > 3000:
                        saved_file.write_bytes(r_img.content)
                        print(f"[Thumbnail] 고화질 실사 사진 수집 성공: {saved_file.name}")
                        return saved_file
        except Exception as e:
            print(f"[Thumbnail] 수집 실패({name}): {e}")

    return None


def generate_shorts_thumbnail(person_name, person_name_en, hook_title, out_path="thumbnail.jpg", target_date="10.16", mode="AM", years="", base_image_path=None):
    """초상권 리스크가 없는 AI 생성 일러스트 이미지를 기반으로 시네마틱 쇼츠 썸네일 제작."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 초상권 100% 안전: 실사 사진 대신 생성된 고품질 AI 일러스트(scene_1.jpg 등) 자동 탐색
    art_file = None
    if base_image_path and Path(base_image_path).exists():
        art_file = Path(base_image_path)
    else:
        pkg_dir = out.parent
        cands = [
            pkg_dir / "assets" / "scene_1.jpg",
            pkg_dir / "assets" / "scene_7.jpg",
            pkg_dir / "assets" / "scene_2.jpg",
            pkg_dir / "scene_1.jpg",
        ]
        for c in cands:
            if c.exists() and c.stat().st_size > 5000:
                art_file = c
                break

    W, H = 1080, 1920
    # 1. 베이스 캔버스 생성 (다크 시네마틱 배경)
    base = Image.new("RGB", (W, H), color=(15, 15, 20))

    # 2. 생성된 AI 아트워크를 1080x1920 세로 풀 블리드(Full Bleed)로 배치
    if art_file and art_file.exists():
        try:
            raw_p = Image.open(art_file).convert("RGB")
            p_ratio = raw_p.width / raw_p.height
            t_ratio = W / H

            if p_ratio > t_ratio:
                new_h = H
                new_w = int(H * p_ratio)
            else:
                new_w = W
                new_h = int(W / p_ratio)

            raw_p = raw_p.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - W) // 2
            top = max(0, int((new_h - H) * 0.20))
            cropped = raw_p.crop((left, top, left + W, top + H))
            base.paste(cropped, (0, 0))
            print(f"[Thumbnail] 초상권 0% AI 생성 일러스트 기반 썸네일 합성: {art_file.name}")
        except Exception as e:
            print(f"[Thumbnail] AI 아트워크 배치 오류: {e}")

    # 3. 시네마틱 다크 비네팅 & 상하단 그라데이션 오버레이 생성
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)

    # 상단 다크 그라데이션 (0 ~ 550px: 텍스트 영역 가독성 확보)
    for y in range(550):
        alpha = int(220 * (1.0 - (y / 550) ** 1.3))
        d_overlay.line([(0, y), (W, y)], fill=(10, 10, 14, alpha))

    # 하단 다크 그라데이션 (1350 ~ 1920px: 인물명 & 브랜딩 영역)
    for y in range(1350, H):
        alpha = int(235 * (((y - 1350) / (H - 1350)) ** 1.2))
        d_overlay.line([(0, y), (W, y)], fill=(10, 10, 14, alpha))

    # 캔버스 합성
    final_img = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(final_img)

    # 4. 폰트 로드
    font_path_hero = FONT_BLACK if FONT_BLACK.exists() else FONT_GMARKET
    font_path_main = FONT_GMARKET if FONT_GMARKET.exists() else FONT_BLACK

    try:
        font_brand = ImageFont.truetype(str(font_path_main), 36)
        font_name = ImageFont.truetype(str(font_path_main), 56)
        font_sub = ImageFont.truetype(str(font_path_main), 34)
    except Exception:
        font_brand = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # 5. 상단 모던 미니멀 브랜드 라벨 (AM: STAR IS BORN vs PM: THE LEGEND FALLS)
    brand_y = 120
    is_pm = str(mode).upper() == "PM"
    brand_label = "THE LEGEND FALLS" if is_pm else "STAR IS BORN"
    dot_color = (255, 204, 0) if is_pm else (255, 45, 85)  # PM: 기일/추모 골드, AM: 탄생 레드

    draw.ellipse([70, brand_y - 10, 88, brand_y + 8], fill=dot_color)
    draw.text((105, brand_y), f"{brand_label}   |   {target_date}", fill=(240, 240, 250), font=font_brand, anchor="lm")

    # 6. 메인 헤드라인 정제 및 분할 (콜론/부제 및 중복 인물명 제거 후 2행 밸런스 유지)
    clean_hook = hook_title.strip()
    if ":" in clean_hook:
        clean_hook = clean_hook.split(":", 1)[0].strip()
    elif " - " in clean_hook:
        clean_hook = clean_hook.split(" - ", 1)[0].strip()

    if person_name:
        clean_hook = re.sub(rf"\s*[-–:]?\s*{re.escape(person_name)}\s*$", "", clean_hook).strip()
    if person_name_en:
        clean_hook = re.sub(rf"\s*[-–:]?\s*{re.escape(person_name_en)}\s*$", "", clean_hook, flags=re.IGNORECASE).strip()

    if "\n" in clean_hook:
        parts = clean_hook.split("\n", 1)
        line1, line2 = parts[0].strip(), parts[1].strip()
    elif "? " in clean_hook:
        parts = clean_hook.split("? ", 1)
        line1 = parts[0].strip() + "?"
        line2 = parts[1].strip()
    elif "! " in clean_hook:
        parts = clean_hook.split("! ", 1)
        line1 = parts[0].strip() + "!"
        line2 = parts[1].strip()
    else:
        words = clean_hook.split()
        if len(words) <= 2:
            line1 = words[0] if words else ""
            line2 = words[1] if len(words) > 1 else ""
        else:
            total_chars = len(clean_hook)
            best_idx = 1
            min_diff = 999
            cur_len = 0
            for i in range(len(words) - 1):
                cur_len += len(words[i]) + 1
                diff = abs(cur_len - (total_chars / 2))
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i + 1
            line1 = " ".join(words[:best_idx])
            line2 = " ".join(words[best_idx:])

    # 텍스트 너비 자동 조절 (Auto-Fit: 캔버스 폭 1080 중 최대 880px 이내로 축소하여 좌우 100px 안전 마진 확보)
    def get_autofit_font(text, max_w=880, initial_size=90, min_size=42):
        size = initial_size
        while size >= min_size:
            try:
                f = ImageFont.truetype(str(font_path_hero), size)
            except Exception:
                return ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=f)
            w = bbox[2] - bbox[0]
            if w <= max_w:
                return f
            size -= 2
        try:
            return ImageFont.truetype(str(font_path_hero), min_size)
        except Exception:
            return ImageFont.load_default()

    font_hero_1 = get_autofit_font(line1, max_w=880, initial_size=90, min_size=42)
    font_hero_2 = get_autofit_font(line2, max_w=880, initial_size=92, min_size=42)

    # 드롭 섀도우 함수
    def draw_shadow_text(xy, text, font, fill_color, shadow_color=(0, 0, 0), stroke_w=6):
        x, y = xy
        for dx, dy in [(3, 4), (4, 5), (2, 3)]:
            draw.text((x + dx, y + dy), text, fill=shadow_color, font=font, anchor="mm", stroke_width=stroke_w, stroke_fill=shadow_color)
        draw.text((x, y), text, fill=fill_color, font=font, anchor="mm", stroke_width=stroke_w, stroke_fill=shadow_color)

    # 1행: 화이트 (#FFFFFF) - 265px
    draw_shadow_text((W // 2, 265), line1, font_hero_1, fill_color=(255, 255, 255), stroke_w=7)
    # 2행: 네온 옐로우 (#FFE600) - 385px
    draw_shadow_text((W // 2, 385), line2, font_hero_2, fill_color=(255, 230, 0), stroke_w=7)

    # 7. 하단 정갈한 인물 시그니처 바
    draw.text((W // 2, 1680), person_name, fill=(255, 255, 255), font=font_name, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    clean_en = unicodedata.normalize('NFKD', person_name_en).encode('ASCII', 'ignore').decode('utf-8') if person_name_en else ""
    if years:
        en_display = f"{clean_en} ({years})" if clean_en else f"({years})"
    else:
        en_display = clean_en if clean_en else "Star is Born Original"
    draw.text((W // 2, 1755), en_display, fill=(200, 205, 225), font=font_sub, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))

    final_rgb = final_img.convert("RGB")
    final_rgb.save(str(out), quality=95)
    print(f"[Thumbnail v2] 최신 시네마틱 숏폼 썸네일 합성 완료: {out}")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="시네마틱 실사 썸네일 생성기 v2")
    p.add_argument("--person", default="오스카 와일드")
    p.add_argument("--person-en", default="Oscar Wilde")
    p.add_argument("--hook", default="고소했다가 감옥 간 천재 작가")
    p.add_argument("--out", default="thumbnail.jpg")
    p.add_argument("--date", default="10.16")
    p.add_argument("--mode", default="AM", choices=["AM", "PM", "am", "pm"])
    p.add_argument("--years", default="")
    a = p.parse_args()
    generate_shorts_thumbnail(a.person, a.person_en, a.hook, a.out, a.date, a.mode, a.years)

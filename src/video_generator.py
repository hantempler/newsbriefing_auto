import os
import sys
import re
import unicodedata
from xml.sax.saxutils import escape
from google.cloud import texttospeech_v1beta1 as texttospeech
import requests
import subprocess
import concurrent.futures
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageOps
from moviepy.editor import AudioFileClip, CompositeAudioClip, AudioClip, concatenate_audioclips
from moviepy.audio.fx.all import audio_fadeout, audio_loop

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

class YouTubeShortsGenerator:
    def __init__(self, script_data: dict, topic: str, work_dir: str, bgm_path: str = None):
        self.script_data = script_data
        self.topic = topic
        self.work_dir = work_dir
        self.bgm_path = bgm_path
        self.temp_dir = os.path.join(work_dir, "temp_render")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.tts_client = texttospeech.TextToSpeechClient()
        self.font_path = os.path.join(config.CONFIG_DIR, "GmarketSansTTFBold.ttf")
        
        temp_font_path = os.path.join(self.temp_dir, "GmarketSansTTFBold.ttf")
        if not os.path.exists(temp_font_path) and os.path.exists(self.font_path):
            shutil.copy(self.font_path, temp_font_path)
            
        import datetime
        now = datetime.datetime.now()
        weekdays = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        today_str = now.strftime("%Y년 %m월 %d일")
        self.header_str = f"{today_str}({weekdays[now.weekday()]}) | 1분 뉴스 정리"
        
        topic_str = script_data.get("topic") or topic or script_data.get("cover_title", "오늘의 1분 뉴스")
        if "?" in topic_str:
            topic_str = script_data.get("cover_title", "오늘의 1분 뉴스")
        self.topic_str = topic_str

    def clean_text(self, text: str) -> str:
        text = re.sub(r"\([^()]*\)", "", text or "")
        text = re.sub(r"[‘’'`\"]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def get_font(self, size):
        try: return ImageFont.truetype(self.font_path, size)
        except: return ImageFont.load_default()

    def get_fallback_font(self, size):
        try: return ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", size)
        except: return self.get_font(size)

    def draw_text_fallback(self, draw, x, y, text, primary_font, fallback_font, fill, stroke_width=0, stroke_fill='black'):
        current_x = x
        for char in text:
            font = fallback_font if ('\u4e00' <= char <= '\u9fff' or char == '☒') else primary_font
            draw.text((current_x, y), char, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
            current_x += draw.textlength(char, font=font)
        return current_x

    def draw_multiline_text_fallback(self, draw, center_x, start_y, text, primary_font, fallback_font, fill, spacing, stroke_width=0, stroke_fill='black'):
        lines = text.split('\n')
        y = start_y
        for line in lines:
            line_width = sum(draw.textlength(c, fallback_font if ('\u4e00' <= c <= '\u9fff' or c == '☒') else primary_font) for c in line)
            x = center_x - (line_width / 2)
            for char in line:
                font = fallback_font if ('\u4e00' <= char <= '\u9fff' or char == '☒') else primary_font
                draw.text((x, y), char, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
                x += draw.textlength(char, font=font)
            bbox = draw.textbbox((0,0), "A", font=primary_font)
            y += (bbox[3] - bbox[1]) + spacing

    def chunk_text(self, text, max_length=15):
        lines = text.replace('\n', ' ').split()
        chunks = []
        current_line = []
        current_chunk_lines = []
        
        for word in lines:
            if sum(len(w) for w in current_line) + len(current_line) + len(word) > 24:
                if current_line:
                    current_chunk_lines.append(" ".join(current_line))
                current_line = [word]
                if len(current_chunk_lines) == 2:
                    chunks.append("\n".join(current_chunk_lines))
                    current_chunk_lines = []
            else:
                current_line.append(word)
                
        if current_line:
            current_chunk_lines.append(" ".join(current_line))
        if current_chunk_lines:
            chunks.append("\n".join(current_chunk_lines))
            
        return chunks

    def generate_section_tts(self, text: str, index: int) -> dict:
        if not text.strip():
            return None
        
        # 문장 분리 후 청크 단위 분할 & SSML mark 삽입 (소수점 분리 방지)
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        ssml_parts = ["<speak>"]
        chunk_list = []
        mark_idx = 0
        
        for sentence in sentences:
            if not sentence.strip(): continue
            chunks = self.chunk_text(sentence)
            for chunk in chunks:
                chunk_list.append(chunk)
                clean = escape(chunk.replace("\n", " "))
                ssml_parts.append(f'<mark name="chunk_{mark_idx}"/>{clean}')
                mark_idx += 1
            ssml_parts.append('<break time="180ms"/>')
            
        ssml_parts.append('<break time="500ms"/>')
        ssml_parts.append("</speak>")
        ssml = "".join(ssml_parts)
        
        audio_path = os.path.join(self.temp_dir, f"audio_sec_{index}.mp3")
        
        request = texttospeech.SynthesizeSpeechRequest(
            input=texttospeech.SynthesisInput(ssml=ssml),
            voice=texttospeech.VoiceSelectionParams(language_code="ko-KR", name="ko-KR-Neural2-C"),
            audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.0),
            enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK]
        )
        response = self.tts_client.synthesize_speech(request=request)
        
        with open(audio_path, "wb") as out:
            out.write(response.audio_content)
            
        timepoints = {tp.mark_name: tp.time_seconds for tp in response.timepoints}
        
        return {
            "audio_path": audio_path,
            "chunks": chunk_list,
            "timepoints": timepoints
        }

    def get_pexels_video(self, keyword: str) -> str:
        if not config.PEXELS_API_KEY:
            return None
        temp_path = os.path.join(self.work_dir, f"bg_{keyword.replace(' ', '_')}.mp4")
        if os.path.exists(temp_path):
            return temp_path
            
        url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&size=medium&per_page=1"
        headers = {"Authorization": config.PEXELS_API_KEY}
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            if data.get("videos"):
                link = data["videos"][0]["video_files"][0]["link"]
                with requests.get(link, stream=True) as r:
                    r.raise_for_status()
                    with open(temp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                return temp_path
        except Exception as e:
            print(f"Pexels 영상 오류 ({keyword}): {e}")
        return None

    def get_pexels_photo(self, keyword: str, photo_index: int = 0) -> str:
        if not config.PEXELS_API_KEY:
            return None
        url = "https://api.pexels.com/v1/search"
        params = {"query": keyword, "orientation": "portrait", "size": "large", "per_page": 2}
        headers = {"Authorization": config.PEXELS_API_KEY}
        try:
            res = requests.get(url, params=params, headers=headers, timeout=15)
            res.raise_for_status()
            photos = res.json().get("photos", [])
            if len(photos) > photo_index:
                image_url = photos[photo_index].get("src", {}).get("portrait") or photos[photo_index].get("src", {}).get("large")
                if image_url:
                    photo_path = os.path.join(self.temp_dir, f"summary_bg_{photo_index}.jpg")
                    with requests.get(image_url, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        with open(photo_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                    return photo_path
        except Exception as e:
            print(f"Pexels 사진 오류: {e}")
        return None

    def create_summary_image(self, summary_lines: list):
        canvas_w, canvas_h = 1080, 1920
        # 투명 배경으로 생성하여 비디오 위에 오버레이 가능하게 함
        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            body_font = ImageFont.truetype(self.font_path, 43)
        except:
            body_font = ImageFont.load_default()
            
        row_x = 70
        row_width = canvas_w - (row_x * 2)
        row_height = 160
        row_gap = 20
        first_row_y = 350

        for index, summary_line in enumerate(summary_lines[:5], start=1):
            summary_line = summary_line.lstrip('0123456789. ') 
            
            cat_match = re.match(r'\[(.*?)\]', summary_line)
            if cat_match:
                cat_text = cat_match.group(1)
                summary_line = summary_line[cat_match.end():].strip()
            else:
                cat_text = str(index)
            
            wrapped_lines = []
            current_line = ""
            max_text_width = row_width - 220
            for word in summary_line.split():
                candidate = f"{current_line} {word}".strip()
                candidate_width = draw.textbbox((0, 0), candidate, font=body_font)[2]
                if current_line and candidate_width > max_text_width:
                    wrapped_lines.append(current_line)
                    current_line = word
                else:
                    current_line = candidate
            if current_line:
                wrapped_lines.append(current_line)

            row_y = first_row_y + (index - 1) * (row_height + row_gap)
            draw.rounded_rectangle((row_x, row_y, row_x + row_width, row_y + row_height), radius=18, fill=(28, 31, 52, 235), outline=(255, 215, 0, 180), width=2)
            
            badge_font = ImageFont.truetype(self.font_path, 40)
            badge_bbox = draw.textbbox((0, 0), cat_text, font=badge_font)
            bw = 130 # 고정 너비 적용
            bh = 70
            bx = row_x + 24
            by = row_y + 45
            draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=15, fill='#FFD700')
            
            # 텍스트 중앙 정렬
            text_w = badge_bbox[2] - badge_bbox[0]
            text_h = badge_bbox[3] - badge_bbox[1]
            draw.text((bx + (bw - text_w) / 2, by + (bh - text_h) / 2 - 8), cat_text, font=badge_font, fill='#111323')

            body_text = "\n".join(wrapped_lines[:2])
            text_x = bx + bw + 30
            body_bbox = draw.multiline_textbbox((0, 0), body_text, font=body_font, spacing=10)
            body_y = row_y + (row_height - (body_bbox[3] - body_bbox[1])) / 2 - 4
            draw.multiline_text((text_x, body_y), body_text, font=body_font, fill='white', spacing=10, stroke_width=1, stroke_fill='black')
        
        out_path = os.path.join(self.temp_dir, "summary_final.png")
        img.save(out_path)
        return out_path

    def download_weather_icon(self, status):
        # 트위터 이모지(Twemoji)의 고화질 PNG를 사용하여 가독성과 디자인 극대화
        if "비" in status: icon_code = "1f327" # 비구름
        elif "눈" in status: icon_code = "2744" # 눈송이
        elif "흐림" in status or "구름" in status: icon_code = "2601" # 구름
        else: icon_code = "2600" # 맑음 (해)
        
        icon_path = os.path.join(self.temp_dir, f"weather_twemoji_{icon_code}.png")
        if not os.path.exists(icon_path):
            url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{icon_code}.png"
            try:
                res = requests.get(url, stream=True, timeout=5)
                if res.status_code == 200:
                    with open(icon_path, "wb") as f:
                        for chunk in res.iter_content(1024): f.write(chunk)
            except: pass
        if os.path.exists(icon_path):
            return Image.open(icon_path).convert("RGBA")
        return None

    def create_weather_image(self, weather_list: list, bg_path: str):
        canvas_w, canvas_h = 1080, 1920
        # 투명 배경으로 생성하여 비디오 위에 오버레이 가능하게 함
        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 가독성을 위한 전체 다크 오버레이
        draw.rectangle([0,0,canvas_w,canvas_h], fill=(0,0,0, 120))
        
        try:
            title_font = ImageFont.truetype(self.font_path, 60)
            city_font = ImageFont.truetype(self.font_path, 45)
            temp_font_big = ImageFont.truetype(self.font_path, 80)
            status_font = ImageFont.truetype(self.font_path, 35)
        except:
            title_font = city_font = temp_font_big = status_font = ImageFont.load_default()
            
        import datetime
        now = datetime.datetime.now()
        tomorrow = now + datetime.timedelta(days=1)
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        title = f"{tomorrow.year}년 {tomorrow.month}월 {tomorrow.day}일({weekdays[tomorrow.weekday()]})\n내일의 날씨"
        
        title_bbox = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=15)
        title_x = (canvas_w - (title_bbox[2] - title_bbox[0])) / 2
        draw.multiline_text((title_x, 140), title, font=title_font, fill='#FFD700', align='center', spacing=15, stroke_width=3, stroke_fill='black')
        
        # Grid layout
        cols = 2
        col_width = 400
        row_height = 200
        start_x = 120
        start_y = 400
        
        for i, w in enumerate(weather_list[:10]):
            col = i % cols
            row = i // cols
            x = start_x + (col * (col_width + 40))
            y = start_y + (row * (row_height + 40))
            
            # Glassmorphism Box: 반투명 화이트 + 얇은 화이트 테두리
            draw.rounded_rectangle((x, y, x + col_width, y + row_height), radius=25, fill=(255, 255, 255, 30), outline=(255, 255, 255, 80), width=2)
            
            city = w.get("city", "")
            temp = w.get("temp", "")
            status = w.get("status", "")
            
            # 도시와 온도
            draw.text((x + 40, y + 30), city, font=city_font, fill='white')
            draw.text((x + 40, y + 90), temp, font=temp_font_big, fill='white')
            
            # 날씨 상태 이미지 합성 및 텍스트 명시
            icon = self.download_weather_icon(status)
            if icon:
                icon = icon.resize((90, 90), Image.Resampling.LANCZOS)
                img.paste(icon, (x + 240, y + 25), icon)
            
            s_bbox = draw.textbbox((0,0), status, font=status_font)
            s_w = s_bbox[2] - s_bbox[0]
            draw.text((x + 240 + (90 - s_w)/2, y + 125), status, font=status_font, fill='white')
            
        out_path = os.path.join(self.temp_dir, "weather_final.png")
        img.save(out_path)
        return out_path

    def format_ass_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def get_wrapped_topic_ass(self):
        try:
            topic_font = ImageFont.truetype(self.font_path, 58)
        except:
            topic_font = ImageFont.load_default()
            
        max_width = 900
        topic_lines = []
        current_line = ""
        for word in self.topic_str.replace('\n', ' ').split(" "):
            candidate = f"{current_line} {word}".strip()
            if ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0, 0), candidate, font=topic_font)[2] > max_width:
                if current_line: topic_lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line: topic_lines.append(current_line)
        return "\\N".join(topic_lines)

    def generate_video(self):
        sections = self.script_data.get("script_sections", [])
        has_summary = bool(self.script_data.get("news_summary_list"))
        has_weather = bool(self.script_data.get("weather_list"))
        
        # 1. 병렬 처리로 각 섹션별 TTS와 뉴스 원문 이미지 다운로드
        print("  -> (멀티 쓰레딩) 섹션별 에셋 준비 중...")
        
        def download_news_image(url, idx):
            if not url: return None
            try:
                import requests
                path = os.path.join(self.temp_dir, f"news_bg_{idx}.jpg")
                res = requests.get(url, stream=True, timeout=10)
                res.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in res.iter_content(8192): f.write(chunk)
                return path
            except:
                return None
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            tts_futures = []
            bg_futures = []
            for i, sec in enumerate(sections):
                text = self.clean_text(sec.get("narration", sec.get("text", "")))
                image_url = sec.get("image_url", "")
                bg_keyword = sec.get("bg_keyword", "news studio")
                
                tts_futures.append(executor.submit(self.generate_section_tts, text, i))
                
                def get_bg(url, kw, idx):
                    img_path = download_news_image(url, idx)
                    if img_path: return img_path
                    return self.get_pexels_video(kw)
                    
                bg_futures.append(executor.submit(get_bg, image_url, bg_keyword, i))
            
            section_data = []
            for i in range(len(sections)):
                tts_info = tts_futures[i].result()
                bg_path = bg_futures[i].result()
                caption = sections[i].get("caption", self.topic_str)
                section_data.append({"tts_info": tts_info, "bg_path": bg_path, "caption": caption})

        print("  -> 오디오 합성 및 ASS 자막 시간표 구성 중...")
        audio_clips = []
        def make_silence(t): return [0, 0]
        audio_clips.append(AudioClip(make_frame=make_silence, duration=3.0, fps=44100))
        current_time = 3.0
        
        ass_events = []
        
        for sec_idx, sdata in enumerate(section_data):
            tts = sdata["tts_info"]
            if not tts: continue
            
            aclip = AudioFileClip(tts["audio_path"])
            duration = aclip.duration
            audio_clips.append(aclip)
            
            # 기록된 Timepoint를 바탕으로 정확한 자막 시간 설정
            timepoints = tts["timepoints"]
            chunks = tts["chunks"]
            for i, chunk_text in enumerate(chunks):
                mark_name = f"chunk_{i}"
                if mark_name in timepoints:
                    start_sec = current_time + timepoints[mark_name]
                    # 다음 청크가 있으면 그 시작시간을 끝시간으로, 아니면 오디오 끝시간으로
                    next_mark = f"chunk_{i+1}"
                    if next_mark in timepoints:
                        end_sec = current_time + timepoints[next_mark]
                    else:
                        end_sec = current_time + duration - 0.2
                        
                    ass_events.append({
                        "start": self.format_ass_time(start_sec),
                        "end": self.format_ass_time(end_sec),
                        "text": chunk_text.replace("\n", "\\N")
                    })
            
            sdata["duration"] = duration
            current_time += duration
            
        if has_summary:
            audio_clips.append(AudioClip(make_frame=make_silence, duration=4.0, fps=44100))
            current_time += 4.0
            
        if has_weather:
            audio_clips.append(AudioClip(make_frame=make_silence, duration=4.0, fps=44100))
            current_time += 4.0
            
        final_audio = concatenate_audioclips(audio_clips)
        total_duration = current_time
        
        if self.bgm_path and os.path.exists(self.bgm_path):
            bgm_clip = AudioFileClip(self.bgm_path)
            bgm_clip = audio_loop(bgm_clip, duration=total_duration)
            bgm_clip = bgm_clip.volumex(0.08)
            bgm_clip = audio_fadeout(bgm_clip, min(2.0, total_duration))
            final_audio = CompositeAudioClip([final_audio, bgm_clip])
            
        raw_audio_path = os.path.join(self.temp_dir, "raw_audio.wav")
        final_audio.write_audiofile(raw_audio_path, fps=44100, logger=None)
        
        print("  -> 이미지 오버레이 생성 및 FFmpeg 비디오 렌더링 중...")
        
        try:
            h_font = ImageFont.truetype(self.font_path, 40)
            t_font = ImageFont.truetype(self.font_path, 58)
            s_font = ImageFont.truetype(self.font_path, 70)
            c_font = ImageFont.truetype(self.font_path, 90)
        except:
            h_font = t_font = s_font = c_font = ImageFont.load_default()
            
        # 토픽 텍스트 래핑
        max_width = 900
        topic_lines = []
        current_line = ""
        for word in self.topic_str.replace('\n', ' ').split(" "):
            candidate = f"{current_line} {word}".strip()
            if ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0, 0), candidate, font=t_font)[2] > max_width:
                if current_line: topic_lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        if current_line: topic_lines.append(current_line)
        wrapped_topic_str = "\n".join(topic_lines)
        
        # 3초 인트로(커버) 컷 생성 (보고서 스타일)
        cover_png = os.path.join(self.temp_dir, "cover.png")
        c_img = Image.new('RGBA', (1080, 1920), (255, 255, 255, 0))
        c_draw = ImageDraw.Draw(c_img)
        
        # 상단 리포트 헤더
        report_str = "DAILY NEWS REPORT"
        r_bbox = c_draw.textbbox((0, 0), report_str, font=h_font)
        c_draw.text(((1080 - (r_bbox[2] - r_bbox[0])) / 2, 500), report_str, font=h_font, fill='white', stroke_width=2, stroke_fill='black')
        
        # 선 그리기
        c_draw.line([(340, 570), (740, 570)], fill='white', width=4)
        
        # 메인 타이틀 (주제)
        import datetime
        now = datetime.datetime.now()
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        cover_title = f"{now.year}년 {now.month:02d}월 {now.day:02d}일({weekdays[now.weekday()]})\n종합 뉴스"
        
        c_bbox = c_draw.multiline_textbbox((0, 0), cover_title, font=c_font, spacing=20)
        c_draw.multiline_text(((1080 - (c_bbox[2] - c_bbox[0])) / 2, 630), cover_title, font=c_font, fill='#FFD700', align='center', spacing=20, stroke_width=4, stroke_fill='black')
        
        # 하단 텍스트
        sub_str = "AI 뉴스 브리핑 데스크"
        s_bbox = c_draw.textbbox((0, 0), sub_str, font=h_font)
        c_draw.text(((1080 - (s_bbox[2] - s_bbox[0])) / 2, 1100), sub_str, font=h_font, fill='white', stroke_width=2, stroke_fill='black')
        
        c_img.save(cover_png)
        
        intro_ts = os.path.join(self.temp_dir, "chunk_intro.ts")
        
        cover_keyword = "breaking news"
        if self.script_data.get("script_sections") and len(self.script_data["script_sections"]) > 0:
            cover_keyword = self.script_data["script_sections"][0].get("bg_keyword", "breaking news")
            
        cover_photo = self.get_pexels_photo(cover_keyword, 0)
        if cover_photo and os.path.exists(cover_photo):
            # Crop photo to 1080x1920 and loop it for 3 seconds, then overlay text
            subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", cover_photo, "-i", cover_png, "-t", "3.0", "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24[bg];[bg][1:v]overlay=0:0", "-c:v", "libx264", "-preset", "ultrafast", intro_ts], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=#141432:s=1080x1920:d=3.0:r=24", "-i", cover_png, "-filter_complex", "[0:v][1:v]overlay=0:0", "-c:v", "libx264", "-preset", "ultrafast", intro_ts], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        concat_list = [f"file 'chunk_intro.ts'"]
        
        summary_img = None
        if has_summary:
            summary_img_path = self.create_summary_image(self.script_data["news_summary_list"])
            summary_img = Image.open(summary_img_path).convert("RGBA")
        
        chunk_idx = 0
        for sdata in section_data:
            tts = sdata.get("tts_info")
            if not tts: continue
            bg_path = sdata["bg_path"]
            timepoints = tts["timepoints"]
            chunks = tts["chunks"]
            duration = sdata["duration"]
            caption = sdata.get("caption", self.topic_str)
            
            # 캡션(타이틀) 래핑
            caption_lines = []
            current_cline = ""
            for word in caption.split():
                candidate = f"{current_cline} {word}".strip()
                if ImageDraw.Draw(Image.new('RGB', (1,1))).textbbox((0, 0), candidate, font=t_font)[2] > 950:
                    if current_cline: caption_lines.append(current_cline)
                    current_cline = word
                else:
                    current_cline = candidate
            if current_cline: caption_lines.append(current_cline)
            wrapped_caption = "\n".join(caption_lines)
            
            # 섹션별 단일 영상 생성 (오버레이 활용)
            filter_chains = []
            png_inputs = []
            
            if bg_path and os.path.exists(bg_path):
                if bg_path.lower().endswith(".mp4"):
                    filter_chains.append(f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24[bg0]")
                else:
                    filter_chains.append(f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,boxblur=20:5,format=yuv420p[bg_blur];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg_blur][fg]overlay=(W-w)/2:(H-h)/2[bg0]")
            else:
                filter_chains.append(f"[0:v]scale=1080:1920,fps=24[bg0]")

            current_sec = 0.0
            for i, chunk_text in enumerate(chunks):
                next_mark = f"chunk_{i+1}"
                if next_mark in timepoints:
                    end_sec = timepoints[next_mark]
                else:
                    end_sec = duration
                
                # PNG 생성 (폰트 폴백 적용)
                img = Image.new('RGBA', (1080, 1920), (255, 255, 255, 0))
                draw = ImageDraw.Draw(img)
                fb_font = self.get_fallback_font(40)
                
                # Header
                h_bbox = draw.textbbox((0, 0), self.header_str, font=h_font)
                draw.text(((1080 - (h_bbox[2] - h_bbox[0])) / 2, 100), self.header_str, font=h_font, fill=(255, 255, 255, 220), stroke_width=2, stroke_fill='black')
                # Title (Caption)
                self.draw_multiline_text_fallback(draw, 540, 160, wrapped_caption, t_font, self.get_fallback_font(58), '#FFD700', 10, 3)
                # Subtitle (Auto-scale)
                s_fontsize = 70
                while True:
                    s_font = self.get_font(s_fontsize)
                    s_bbox = draw.multiline_textbbox((0, 0), chunk_text, font=s_font, spacing=10)
                    if (s_bbox[2] - s_bbox[0]) <= 980 or s_fontsize <= 30:
                        break
                    s_fontsize -= 2
                
                s_y = 1350 + (200 - (s_bbox[3] - s_bbox[1])) / 2
                self.draw_multiline_text_fallback(draw, 540, s_y, chunk_text, s_font, self.get_fallback_font(s_fontsize), 'white', 10, 3)
                
                # 마지막 섹션(총평)일 경우 요약 이미지 합성
                if has_summary and chunk_idx == len(section_data) - 1 and summary_img:
                    img.paste(summary_img, (0,0), summary_img)
                
                png_path = os.path.join(self.temp_dir, f"sec_{chunk_idx}_sub_{i}.png")
                img.save(png_path)
                
                png_inputs.extend(["-i", png_path])
                in_bg = f"[bg{i}]"
                out_bg = f"[bg{i+1}]"
                filter_chains.append(f"{in_bg}[{i+1}:v]overlay=0:0:enable='between(t,{current_sec:.3f},{end_sec:.3f})'{out_bg}")
                
                current_sec = end_sec
                
            filter_complex = ";".join(filter_chains)
            last_out = f"[bg{len(chunks)}]"
            ts_path = os.path.join(self.temp_dir, f"vchunk_{chunk_idx}.ts")
            
            cmd = ["ffmpeg", "-y"]
            if bg_path and os.path.exists(bg_path) and bg_path.lower().endswith(".mp4"):
                cmd.extend(["-stream_loop", "-1", "-i", bg_path])
            elif bg_path and os.path.exists(bg_path):
                cmd.extend(["-loop", "1", "-i", bg_path])
            else:
                cmd.extend(["-f", "lavfi", "-i", f"color=c=#323232:s=1080x1920"])
                
            cmd.extend(png_inputs)
            cmd.extend(["-filter_complex", filter_complex, "-map", last_out, "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast", ts_path])
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            concat_list.append(f"file 'vchunk_{chunk_idx}.ts'")
            chunk_idx += 1

        # 별도의 요약 청크 생성 로직 삭제 (마지막 섹션에 오버레이로 대체됨)
            
        if has_weather:
            # 전반적인 날씨 파악하여 비디오 다운로드
            weather_list = self.script_data["weather_list"]
            conditions = [w.get("status", "") for w in weather_list]
            if not conditions: dominant_weather = "맑음"
            else:
                from collections import Counter
                dominant_weather = Counter(conditions).most_common(1)[0][0]
                
            weather_kw = "clear blue sky"
            if "비" in dominant_weather: weather_kw = "rainy window"
            elif "눈" in dominant_weather: weather_kw = "snowing"
            elif "흐림" in dominant_weather or "구름" in dominant_weather: weather_kw = "cloudy sky"
            
            weather_bg_path = self.get_pexels_video(weather_kw)
            if not weather_bg_path:
                weather_bg_path = self.get_pexels_photo(weather_kw, 0)
                
            weather_img_path = self.create_weather_image(weather_list, weather_bg_path)
            weather_ts = os.path.join(self.temp_dir, "chunk_weather.ts")
            
            cmd = ["ffmpeg", "-y"]
            if weather_bg_path and os.path.exists(weather_bg_path) and weather_bg_path.lower().endswith(".mp4"):
                cmd.extend(["-stream_loop", "-1", "-i", weather_bg_path])
                filter_complex = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24[bg];[bg][1:v]overlay=0:0"
            elif weather_bg_path and os.path.exists(weather_bg_path):
                cmd.extend(["-loop", "1", "-i", weather_bg_path])
                filter_complex = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=24,boxblur=20:5,format=yuv420p[bg_blur];[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg_blur][fg]overlay=(W-w)/2:(H-h)/2[bg];[bg][1:v]overlay=0:0"
            else:
                cmd.extend(["-f", "lavfi", "-i", "color=c=#323232:s=1080x1920:r=24"])
                filter_complex = "[0:v][1:v]overlay=0:0"
                
            cmd.extend(["-i", weather_img_path, "-t", "4.0", "-filter_complex", filter_complex, "-c:v", "libx264", "-preset", "ultrafast", weather_ts])
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            concat_list.append(f"file 'chunk_weather.ts'")
            
        concat_txt_path = os.path.join(self.temp_dir, "concat.txt")
        with open(concat_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(concat_list))
            
        raw_video_ts = os.path.join(self.temp_dir, "raw_video.ts")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt_path, "-c", "copy", raw_video_ts], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        output_path = os.path.join(self.work_dir, "final_shorts.mp4")
        print("  -> 최종 믹싱 중...")
        mix_cmd = ["ffmpeg", "-y", "-i", "raw_video.ts", "-i", "raw_audio.wav", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", output_path]
        result = subprocess.run(mix_cmd, cwd=self.temp_dir)
        
        if result.returncode == 0:
            print(f"영상 렌더링 완료: {output_path}")
            return output_path
        else:
            print("FFmpeg 렌더링 중 오류가 발생했습니다.")
            return None

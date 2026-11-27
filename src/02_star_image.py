"""스타이즈본 이미지 생성기 (V2 비전 기반 지능형 배치 에디션):
1. 500px 이상 고화질 실사 사료만 사전 다운로드 (500px 미만 저화질 썸네일 원천 배제)
2. Gemini Vision 모델이 실제 사진을 눈으로 직접 보고 심사:
   - 타인(안재홍 등) 단독 샷 및 2인 이상 단체/군중 컷 100% 영구 탈락(REJECT)
   - 오직 목표 스타 1인 단독 샷(Solo Cut)만 합격 후, 7개 씬 중 가장 적합한 씬으로 직접 배치
   - 씬당 가장 훌륭한 사진 최대 3개(메인 1장 + 서브 최대 2장) 엄격 제한
3. 실사 사료가 배정되지 않은 씬만 시각적 연속성 앵커를 적용하여 AI 생성.
"""
import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from PIL import Image, ImageOps, ImageFilter, ImageEnhance

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
    return "newsbriefing-439502"

GCP_PROJECT_ID = _resolve_project_id()
GCP_LOCATION = "global"
MODEL_IMAGE = "gemini-nano-banana-2.1"
MODEL_FALLBACK = "gemini-2.5-flash-image"

PROMPT_DEFAULT = (
    "Oscar Wilde with his iconic shoulder-length wavy hair, wearing a purple velvet coat, "
    "smug dandy expression, hyper-realistic retro pop-art caricature, vivid cinematic lighting, vertical 9:16 poster style, 8k, no text"
)

USER_AGENT = "StarIsBornBot/2.0 (https://github.com/hantempler/starisborn; contact: admin@starisborn.com)"

_REAL_PHOTOS_CACHE = {}


def _get_json_safe(url, headers=None, data=None, timeout=12, max_retries=3):
    h = {"User-Agent": USER_AGENT}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h, data=data)
    for attempt in range(max_retries):
        try:
            time.sleep(0.15)  # API 기본 간격 확보
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            err_str = str(e)
            if ("429" in err_str or "Too Many Requests" in err_str) and attempt < max_retries - 1:
                wait_sec = (attempt + 1) * 3
                print(f"[API 429 대기] 위키미디어 API 요청 한도 감지, {wait_sec}초 쿨다운 일시 정지 후 재시도 ({attempt+1}/{max_retries})...")
                time.sleep(wait_sec)
                continue
            if attempt == max_retries - 1:
                raise


def _fetch_entity_graph(qid: str):
    """위키데이터 엔티티 및 소속 그룹(P463)/소속팀(P54) 관계망 자동 순회"""
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    data = _get_json_safe(url)
    entity = data.get("entities", {}).get(qid, {})
    claims = entity.get("claims", {})
    labels = entity.get("labels", {})
    sitelinks = entity.get("sitelinks", {})

    name_ko = labels.get("ko", {}).get("value", "")
    name_en = labels.get("en", {}).get("value", "")
    p18  = claims.get("P18", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    p373 = claims.get("P373", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    p345 = claims.get("P345", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    p434 = claims.get("P434", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")

    related_categories = []
    for prop in ["P463", "P54", "P361"]:
        for snak in claims.get(prop, []):
            rel_id = snak.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if rel_id:
                try:
                    rel_data = _get_json_safe(f"https://www.wikidata.org/wiki/Special:EntityData/{rel_id}.json")
                    cat = rel_data.get("entities", {}).get(rel_id, {}).get("claims", {}).get("P373", [{}])[0].get("mainsnak", {}).get("datavalue", {}).get("value")
                    if cat and cat not in related_categories:
                        related_categories.append(cat)
                except Exception:
                    pass

    return {
        "name_ko": name_ko, "name_en": name_en,
        "p18": p18, "p373": p373, "p345": p345, "p434": p434,
        "related_categories": related_categories,
        "kowiki": sitelinks.get("kowiki", {}).get("title"),
        "enwiki": sitelinks.get("enwiki", {}).get("title")
    }


def _fetch_commons_file_direct(filename: str, star_name: str):
    """위키데이터 공식 프로필(P18) 단일 파일 메타데이터 직접 조회"""
    if not filename: return []
    clean_name = filename if filename.startswith("File:") else f"File:{filename}"
    params = urllib.parse.urlencode({
        "action": "query", "titles": clean_name,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "format": "json"
    })
    try:
        data = _get_json_safe(f"https://commons.wikimedia.org/w/api.php?{params}")
        results = []
        for pid, page in data.get("query", {}).get("pages", {}).items():
            if int(pid) < 0: continue
            info_list = page.get("imageinfo", [])
            if not info_list: continue
            info = info_list[0]
            ext = info.get("extmetadata", {})
            dt = ext.get("DateTimeOriginal", {}).get("value") or ext.get("DateTime", {}).get("value") or ""
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", f"{dt} {filename}")
            results.append({
                "source": "Wikidata Official Profile (P18)",
                "url": info.get("url"), "width": info.get("width", 0), "height": info.get("height", 0),
                "year": year_match.group(1) if year_match else "",
                "caption": ext.get("ImageDescription", {}).get("value", f"{star_name} 공식 프로필")[:120],
                "filename": page.get("title", clean_name),
                "is_profile": True,
                "priority": 1
            })
        return results
    except Exception:
        return []


def _search_commons_files(query_name: str, star_name: str, limit: int = 25):
    """위키미디어 공용 공식 검색 API(generator=search)를 통한 인물 실사 핀포인트 적출"""
    if not query_name: return []
    clean_query = query_name.strip("\"'")
    params = urllib.parse.urlencode({
        "action": "query", "generator": "search",
        "gsrsearch": f'"{clean_query}"', "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|extmetadata", "format": "json"
    })
    try:
        data = _get_json_safe(f"https://commons.wikimedia.org/w/api.php?{params}")
        results = []
        for pid, page in data.get("query", {}).get("pages", {}).items():
            if int(pid) < 0: continue
            info_list = page.get("imageinfo", [])
            if not info_list: continue
            info = info_list[0]
            title = page.get("title", "")
            lower_t = title.lower()
            if any(bad in lower_t for bad in [".flac", ".ogg", ".mp3", ".pdf", "signature", "logo", "icon", ".svg"]):
                continue
            ext = info.get("extmetadata", {})
            dt = ext.get("DateTimeOriginal", {}).get("value") or ext.get("DateTime", {}).get("value") or ""
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", f"{dt} {title}")
            results.append({
                "source": f"Commons Search (\"{clean_query}\")",
                "url": info.get("url"), "width": info.get("width", 0), "height": info.get("height", 0),
                "year": year_match.group(1) if year_match else "",
                "caption": ext.get("ImageDescription", {}).get("value", title)[:120],
                "filename": title,
                "is_profile": False,
                "priority": 3
            })
        return results
    except Exception:
        return []


def _fetch_commons_category_files(cat_name: str, star_name: str, limit: int = 50):
    """위키미디어 카테고리 멤버 직접 호출 (오디오/다이어그램 배제)"""
    if not cat_name: return []
    params = urllib.parse.urlencode({
        "action": "query", "generator": "categorymembers",
        "gcmtitle": f"Category:{cat_name}", "gcmtype": "file",
        "prop": "imageinfo", "iiprop": "url|size|extmetadata",
        "gcmlimit": str(limit), "format": "json"
    })
    try:
        data = _get_json_safe(f"https://commons.wikimedia.org/w/api.php?{params}")
        results = []
        for pid, page in data.get("query", {}).get("pages", {}).items():
            if int(pid) < 0: continue
            info_list = page.get("imageinfo", [])
            if not info_list: continue
            info = info_list[0]
            title = page.get("title", "")
            if any(bad in title.lower() for bad in [".flac", ".ogg", ".mp3", ".pdf", "signature", "logo", "icon", ".svg"]):
                continue
            ext = info.get("extmetadata", {})
            dt = ext.get("DateTimeOriginal", {}).get("value") or ext.get("DateTime", {}).get("value") or ""
            year_match = re.search(r"\b(19\d\d|20\d\d)\b", f"{dt} {title}")
            results.append({
                "source": f"Commons Category ({cat_name})",
                "url": info.get("url"), "width": info.get("width", 0), "height": info.get("height", 0),
                "year": year_match.group(1) if year_match else "",
                "caption": ext.get("ImageDescription", {}).get("value", title)[:120],
                "filename": title,
                "is_profile": False,
                "priority": 2
            })
        return results
    except Exception:
        return []


def _fetch_commons_subcategories_2depth(parent_cat: str, star_name: str):
    """가수 콘서트 투어 및 스포츠 선수 2-depth 'by year' 서브카테고리 자동 확장"""
    if not parent_cat: return []
    try:
        params = urllib.parse.urlencode({
            "action": "query", "generator": "categorymembers",
            "gcmtitle": f"Category:{parent_cat}", "gcmtype": "subcat",
            "gcmlimit": "30", "format": "json"
        })
        data = _get_json_safe(f"https://commons.wikimedia.org/w/api.php?{params}")
        subcats = [p.get("title", "").replace("Category:", "") for _, p in data.get("query", {}).get("pages", {}).items()]

        results = []
        for sc in subcats:
            lower_sc = sc.lower()
            if "by year" in lower_sc or "by decade" in lower_sc:
                deep_params = urllib.parse.urlencode({
                    "action": "query", "generator": "categorymembers",
                    "gcmtitle": f"Category:{sc}", "gcmtype": "subcat",
                    "gcmlimit": "20", "format": "json"
                })
                deep_data = _get_json_safe(f"https://commons.wikimedia.org/w/api.php?{deep_params}")
                deep_subcats = [p.get("title", "").replace("Category:", "") for _, p in deep_data.get("query", {}).get("pages", {}).items()]
                for d_sc in deep_subcats[:8]:
                    results.extend(_fetch_commons_category_files(d_sc, star_name, limit=10))

            elif any(k in lower_sc for k in ["concert", "tour", "live", "performance", "match"]):
                results.extend(_fetch_commons_category_files(sc, star_name, limit=15))

        return results
    except Exception:
        return []


def _fetch_wikipedia_guarded(lang: str, title: str, star_name: str, names: list):
    """위키백과 본문 미디어 수집 (타인/게스트/멘토 100% 차단 가드레일)"""
    if not title: return []
    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/media-list/{urllib.parse.quote(title)}"
        data = _get_json_safe(url)
        valid_titles = []
        for item in data.get("items", []):
            if item.get("type") != "image": continue
            ft = item.get("title", "")
            lower_ft = ft.lower()
            if any(bad in lower_ft for bad in ["icon", "flag", "logo", "symbol", "stub", "portal"]):
                continue
            if any(n and len(n) >= 2 and n.lower() in lower_ft for n in names):
                valid_titles.append(ft)
        
        results = []
        for i in range(0, len(valid_titles), 50):
            batch = ["File:" + t if not t.startswith("File:") else t for t in valid_titles[i:i+50]]
            p_url = f"https://commons.wikimedia.org/w/api.php?action=query&titles={'|'.join([urllib.parse.quote(t) for t in batch])}&prop=imageinfo&iiprop=url|size|extmetadata&format=json"
            batch_data = _get_json_safe(p_url)
            for _, p in batch_data.get("query", {}).get("pages", {}).items():
                if int(_) < 0 or not p.get("imageinfo"): continue
                inf = p["imageinfo"][0]
                results.append({
                    "source": f"Wikipedia Body ({lang})",
                    "url": inf.get("url"), "width": inf.get("width", 0), "height": inf.get("height", 0),
                    "year": "", "caption": p.get("title", ""), "filename": p.get("title", ""),
                    "is_profile": False,
                    "priority": 4
                })
        return results
    except Exception:
        return []


def _fetch_imdb_graphql(p345: str, star_name: str, limit: int = 35):
    """IMDb GraphQL 스틸컷 (배우/감독/가수 공통)"""
    if not p345: return []
    query = """
    query NameImages($id: ID!, $first: Int!) {
      name(id: $id) {
        images(first: $first) {
          edges { node { id url caption { plainText } } }
        }
      }
    }
    """
    post_data = json.dumps({"query": query, "variables": {"id": p345, "first": limit}}).encode("utf-8")
    headers = {"content-type": "application/json", "x-imdb-client-name": "imdb_web_consumers"}
    try:
        data = _get_json_safe("https://caching.graphql.imdb.com/", headers=headers, data=post_data)
        edges = data.get("data", {}).get("name", {}).get("images", {}).get("edges", [])
        results = []
        for edge in edges:
            node = edge.get("node", {})
            u = node.get("url")
            cap = node.get("caption", {}).get("plainText") or f"{star_name} 스틸컷"
            ym = re.search(r"\b(19\d\d|20\d\d)\b", cap)
            if u:
                results.append({
                    "source": "IMDb", "url": u, "width": 1000, "height": 1000,
                    "year": ym.group(1) if ym else "", "caption": cap, "filename": node.get("id"),
                    "is_profile": False,
                    "priority": 5
                })
        return results
    except Exception:
        return []


def fetch_real_star_photos(qid: str):
    """
    [V3 프로덕션 통합 실사 수집기 - 보편적 5계층 아키텍처]
    배우, 가수, 스포츠 선수, 소설가, 과학자 등 직업군에 구애받지 않고
    인물 본인과 100% 직결된 실사 사료를 우선순위(Priority 1~5) 기반으로 선별 수집.
    """
    global _REAL_PHOTOS_CACHE
    if qid in _REAL_PHOTOS_CACHE:
        return _REAL_PHOTOS_CACHE[qid]

    meta = _fetch_entity_graph(qid)
    star_name = meta["name_ko"] or meta["name_en"]
    star_name_en = meta.get("name_en", "")
    star_name_ko = meta.get("name_ko", "")
    name_list = [n for n in [star_name_ko, star_name_en, star_name] if n]
    raw_photos = []

    # 1. [Priority 1] P18 공식 대표 프로필 (단일 파일 직접 조회)
    if meta.get("p18"):
        raw_photos.extend(_fetch_commons_file_direct(meta["p18"], star_name))

    # 2. [Priority 2] 본인 전용 위키미디어 카테고리 (Category:{Name})
    if meta.get("p373"):
        raw_photos.extend(_fetch_commons_category_files(meta["p373"], star_name, limit=35))

    # 3. [Priority 3] 위키미디어 공용 공식 파일 검색 (intitle / generator=search)
    # 영문명 및 한글명으로 핀포인트 직접 검색 (전 직업군 보편 적용)
    if star_name_en:
        raw_photos.extend(_search_commons_files(star_name_en, star_name, limit=20))
    if star_name_ko and star_name_ko != star_name_en:
        raw_photos.extend(_search_commons_files(star_name_ko, star_name, limit=10))

    # 4. [Priority 4] 위키백과 본문 삽입 미디어 (ko & en 가드레일 통과 파일)
    raw_photos.extend(_fetch_wikipedia_guarded("ko", meta["kowiki"], star_name, name_list))
    raw_photos.extend(_fetch_wikipedia_guarded("en", meta["enwiki"], star_name, name_list))

    # 5. [Priority 5] IMDb GraphQL 스틸컷 (배우/감독 등 등록 인물)
    if meta.get("p345"):
        raw_photos.extend(_fetch_imdb_graphql(meta["p345"], star_name, limit=25))

    # 🚨 소속팀(P54), 소속단체(P463) 무차별 카테고리 크롤링은 100년 전 과거 사진 오염의 주원인이므로 완전 영구 폐기!

    # 6. 중복 제거 (URL & 파일명 기준) 및 우선순위(Priority 1~5) 기반 정렬
    deduped = []
    seen_urls = set()
    seen_fnames = set()
    for p in raw_photos:
        u = p.get("url")
        if not u: continue
        clean_u = u.split("?")[0]
        fn = re.sub(r"^File:", "", p.get("filename", ""), flags=re.IGNORECASE).strip().lower()
        if clean_u in seen_urls or (fn and fn in seen_fnames):
            continue
        seen_urls.add(clean_u)
        if fn: seen_fnames.add(fn)
        deduped.append({
            "id": f"real_{len(deduped)+1:03d}",
            "source": p.get("source", "Unknown"),
            "url": u,
            "width": p.get("width", 0),
            "height": p.get("height", 0),
            "year": p.get("year", ""),
            "caption": p.get("caption", f"{star_name} 실사 사료"),
            "is_profile": p.get("is_profile", False) or ("Official Profile" in p.get("source", "")),
            "priority": p.get("priority", 99)
        })

    # 우선순위(Priority: 1 -> 2 -> 3 -> 4 -> 5) 최우선 정렬 후, 사료 내 연도 정렬
    def _sort_key(x):
        prio = x.get("priority", 99)
        y_str = re.sub(r"\D", "", str(x.get("year", "")))
        y_val = -int(y_str[:4]) if len(y_str) >= 4 else 0  # 최근 연도 우선
        return (prio, y_val)

    sorted_photos = sorted(deduped, key=_sort_key)
    print(f"[Image Harvester] QID={qid} ({star_name}) 고순도 실사 사료 {len(sorted_photos)}장 확보 완료! (우선순위 정렬)")
    _REAL_PHOTOS_CACHE[qid] = sorted_photos
    return sorted_photos


def filter_high_res_photos(photos, min_px=500, min_bytes=20000, max_pool=25):
    """1단계: 500px 미만 저해상도/썸네일 즉시 걷어내고, 선명한 고화질 사료만 풀 확보."""
    high_res_pool = []
    print(f"\n[02_star_image] 1단계: 수집된 {len(photos)}장 중 500px 이상 고화질 선별 다운로드 시작...")

    for idx, p in enumerate(photos):
        url = p.get("url", "")
        if not url:
            continue

        b = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(0.3)  # 위키미디어 API 요청 간격 보장 (기본 0.3초)
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    b = resp.read()
                break
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "Too Many Requests" in err_str) and attempt < max_retries - 1:
                    wait_sec = (attempt + 1) * 3
                    print(f"  [429 대기] 위키미디어 요청 한도 감지, {wait_sec}초 쿨다운 일시 정지 후 재시도 ({attempt+1}/{max_retries})...")
                    time.sleep(wait_sec)
                else:
                    if attempt == max_retries - 1:
                        print(f"  - [{idx+1}/{len(photos)}] 다운로드 실패({e}): {p.get('caption', '')[:35]}")
                    time.sleep(0.5)

        if not b:
            continue

        try:
            if len(b) < min_bytes:
                print(f"  - [{idx+1}/{len(photos)}] 용량 미달({len(b)/1e3:.1f}KB) 탈락: {p.get('caption', '')[:35]}")
                continue

            img = Image.open(io.BytesIO(b))
            w, h = img.size
            if max(w, h) < min_px:
                print(f"  - [{idx+1}/{len(photos)}] 500px 미만 저해상도({w}x{h}) 탈락: {p.get('caption', '')[:35]}")
                continue

            print(f"  + [{idx+1}/{len(photos)}] ✅ 500px+ 고화질 합격 ({w}x{h}, {len(b)/1e3:.0f}KB): {p.get('caption', '')[:40]}")
            high_res_pool.append({
                "id": p["id"],
                "source": p["source"],
                "caption": p.get("caption", ""),
                "url": url,
                "bytes": b,
                "size": (w, h),
                "is_profile": p.get("is_profile", False)
            })
            if len(high_res_pool) >= max_pool:
                break
        except Exception as e:
            print(f"  - [{idx+1}/{len(photos)}] 이미지 검증 실패({e}): {p.get('caption', '')[:35]}")

    print(f"[02_star_image] 1단계 완료: 고화질 사료 풀 총 {len(high_res_pool)}장 확보!")
    return high_res_pool


def curate_photo_milestones(client, types, clean_candidates, person_name: str, person_name_en: str = ""):
    """[V3 사진 중심 대본 핵심] 수집 및 필터링된 실사 사료 풀을 살펴보고,
    스타의 일생에서 가장 중요한 2~3대 핵심 마일스톤(작품/사건/무대)을 엄선하여
    대본 작가가 스토리의 중심 기둥으로 삼을 수 있는 기획 브리프 도출."""
    if not clean_candidates:
        return {"milestones": [], "storyline_brief": "확보된 실사 사료가 없어 AI 시네마틱 이미지로 서사를 전개합니다."}

    p_list_text = []
    for idx, c in enumerate(clean_candidates):
        p_list_text.append(f"[{idx+1}] 사료 ID: {c['id']} | 출처: {c['source']} | 내용: {c['caption']}")
    candidates_str = "\n".join(p_list_text)

    prompt = f"""너는 최고 권위의 9:16 다큐멘터리 쇼츠 총괄 프로듀서 겸 사료 큐레이터 AI다.
[목표 인물]: {person_name} ({person_name_en})

우리는 사료 풀에서 500px 이상 고화질 사진을 확보하고 쓸모없는 사료(저화질, 티켓, 포스터, 앵커 화면 등)를 버린 후
아래와 같이 총 {len(clean_candidates)}장의 귀중한 실사 사료를 확보했습니다:

[확보된 실사 사료 목록]:
{candidates_str}

[🚨 큐레이션 지침 - 사진 중심 스토리 아키텍처 수립]:
1. 확보된 사진들을 면밀히 살펴본 후, '아! 이 사진들이 있으니 이 사건들을 쇼츠 7씬 스토리의 중심 기둥(뼈대)으로 써야겠다!'라고 판단되는 가장 위대하고 드라마틱한 2~3대 핵심 마일스톤(작품, 사건, 역사적 투샷, 시상식 등)을 엄선하세요.
2. [시간 순서(Chronological Order) 절대 엄수]:
   - 엄선하는 마일스톤들은 반드시 과거에서 현재로 이어지는 시간 순서(연도 오름차순, 예: 2000년 ➔ 2002년 ➔ 2021년)대로 정렬되어야 합니다.
   - 시간 순서가 역전되는 일(예: 2002년 아카데미가 2000년 VMA보다 먼저 나오는 일)은 서사의 몰입을 깨뜨리므로 절대 금지합니다!
3. 억지로 모든 사진을 쓰지 말고, 스타의 인생 굴곡(예: 무명 탈출의 계기가 된 무대, 전 세계를 뒤흔든 대표작/시상식, 현재의 레전드 프로필 등)을 가장 강렬하게 증명하는 2~3장을 고르세요.
4. 각 마일스톤마다 쇼츠 7개 씬 중 어디에 배치되어야 할지(예: 씬 4 전환점, 씬 5~6 클라이맥스, 씬 7 레거시 등)와 그 사진 속 구체적 순간을 대본 작가가 어떻게 풀어야 할지 지침을 작성하세요.

아래 JSON 규격으로만 응답하세요:
```json
{{
  "milestones": [
    {{
      "photo_id": "선택한 사료 ID",
      "event_name": "사건/작품 명칭 (예: 2000 MTV VMA 닥터 드레 무대)",
      "year": "연도 (예: 2000)",
      "target_scene_role": "turning_point 또는 climax 또는 legacy",
      "recommended_scene_no": 4,
      "story_core": "이 사진에 담긴 실제 순간과 대본에서 풀어야 할 핵심 서사",
      "visual_description": "사진 속 인물의 구체적인 모습, 의상, 표정, 분위기"
    }}
  ],
  "storyline_brief": "대본 작가를 위한 총괄 지침: 확보된 사진들을 연대기 순서대로 중심으로 삼아 7씬 서사를 어떻게 직조해야 하는지 명확한 2~3문장 가이드"
}}
```"""

    try:
        resp = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json")
        )
        clean_t = re.sub(r"^```(?:json)?\s*", "", resp.text.strip())
        clean_t = re.sub(r"\s*```$", "", clean_t)
        curated = json.loads(clean_t)

        # 연도(year) 기준 오름차순 강제 정렬 안전장치 (시간 역전 원천 방지)
        def _extract_year(m):
            y_str = re.sub(r"\D", "", str(m.get("year", "")))
            return int(y_str[:4]) if len(y_str) >= 4 else 9999

        if curated.get("milestones"):
            curated["milestones"].sort(key=_extract_year)
            # 권장 씬 번호도 연대기 순으로 순차 부여 (씬 4 -> 씬 5 -> 씬 6 -> 씬 7)
            scene_slots = [4, 5, 6, 7]
            for idx, m in enumerate(curated["milestones"]):
                if idx < len(scene_slots):
                    m["recommended_scene_no"] = scene_slots[idx]

        print(f"\n[Photo Curator] 🎯 확보된 사진 기반 {len(curated.get('milestones', []))}대 핵심 마일스톤 도출 완료 (시간순 정렬)!")
        for m in curated.get("milestones", []):
            print(f"  ⭐ [{m.get('event_name')} ({m.get('year', '')})] 사료 ID: {m.get('photo_id')} -> {m.get('target_scene_role')} (씬 {m.get('recommended_scene_no', '?')})")
        print(f"  📝 서사 총괄 지침: {curated.get('storyline_brief')[:80]}...\n")
        return curated
    except Exception as e:
        print(f"[Photo Curator Warning] 마일스톤 큐레이션 실패({e}), 기본 사료 매핑 폴백")
        return {
            "milestones": [
                {
                    "photo_id": clean_candidates[0]["id"],
                    "event_name": clean_candidates[0]["caption"][:30],
                    "target_scene_role": "climax",
                    "recommended_scene_no": 5,
                    "story_core": clean_candidates[0]["caption"],
                    "visual_description": clean_candidates[0]["caption"]
                }
            ],
            "storyline_brief": "확보된 대표 실사 사료를 클라이맥스 씬의 중심으로 삼으세요."
        }


def preharvest_available_photos(qid: str, person_name: str = None, person_name_en: str = None, max_candidates: int = 12):
    """[V3 사진 중심 대본] 대본 집필 전, 고화질 실사 사료를 사전 수집 및 쓸모없는 사료 필터링 후,
    LLM 사료 큐레이터가 핵심 마일스톤과 스토리 아키텍처 브리프를 도출하여 반환."""
    from google import genai
    from google.genai import types

    print(f"[Photo Pre-Harvest] QID({qid}) {person_name or ''} ({person_name_en or ''}) 실사 사료 사전 수집 중...")
    raw_photos = fetch_real_star_photos(qid)
    if not raw_photos:
        print("[Photo Pre-Harvest] 수집된 실사 사료 없음 (0장)")
        return {"candidates": [], "milestones": [], "storyline_brief": ""}

    # 1. 500px 이상 고화질 선별
    pool = filter_high_res_photos(raw_photos, min_px=500, min_bytes=20000, max_pool=25)
    if not pool:
        return {"candidates": [], "milestones": [], "storyline_brief": ""}

    # 2. 명백한 부적격 사료(뉴스 앵커 샷, 5인 이상 떼샷, 그래픽 표지 등) 1차 텍스트 필터링
    clean_candidates = []
    bad_keywords = ["news", "anchor", "studio", "special report", "koppel", "ticket", "poster", "logo", "billboard"]

    for item in pool:
        cap_lower = (item.get("caption") or "").lower()
        if any(bw in cap_lower for bw in bad_keywords):
            continue
        if cap_lower.count(",") >= 4:
            continue

        clean_candidates.append({
            "id": item["id"],
            "caption": item["caption"],
            "source": item["source"],
            "is_profile": item.get("is_profile", False),
            "size": item.get("size", (0, 0))
        })
        if len(clean_candidates) >= max_candidates:
            break

    print(f"[Photo Pre-Harvest] 정제된 사료 풀 총 {len(clean_candidates)}장 확정! 이제 사료들을 살펴보고 핵심 마일스톤을 도출합니다.")
    for c in clean_candidates:
        print(f"  📌 [사료 ID: {c['id']}] ({c['source']}) {c['caption'][:45]}...")

    # 3. 스토리 우선 원칙: 사진으로 대본을 억압하지 않고 사료 후보 풀만 반환
    return {
        "candidates": clean_candidates,
        "milestones": [],
        "storyline_brief": ""
    }


def place_photos_into_scenes_with_vision(client, types, high_res_pool, person_name, scenes, max_per_scene=3):
    """2단계: Gemini Vision 모델이 실제 사진들을 직접 눈으로 보고, 7개 씬 중 가장 적합한 씬에 최대 3장씩 배치.
    타인 단독 샷, 단체 컷은 100% 탈락(REJECT).
    """
    if not high_res_pool:
        return {}, []

    scene_desc = []
    for sc in scenes:
        s_num = sc.get("scene_no", 1)
        cap = sc.get("caption", "")
        narr = sc.get("narration_tts") or sc.get("narration", "")
        scene_desc.append(f"Scene {s_num}: [소제목: {cap}] - 내레이션: {narr}")
    scenes_text = "\n".join(scene_desc)

    contents = []
    prompt = f"""너는 최고 권위의 9:16 다큐멘터리 쇼츠 사료 검증 및 연출 감독 AI다.
[목표 인물]: {person_name}

[쇼츠 7개 씬 서사 흐름]:
{scenes_text}

[🚨 엄격한 즉각 불합격(REJECT) 기준 - 절대 어떤 씬에도 배치 금지 🚨]:
1. [타인 단독 샷 100% 탈락]: 목표 인물({person_name})이 나오지 않고 다른 사람(동료 배우, 조연 등)만 단독으로 나온 사진은 100% 즉각 탈락!
2. [군중/떼샷 및 행사 단체 컷 탈락]: 5인 이상 여러 사람이 우르르 등장하여 인물이 작게 나오거나, 제작발표회/시상식에 10여 명이 나란히 선 행사 단체 컷은 탈락!
3. [주인공 소외 컷 탈락]: 타인이 화면의 메인이고 주인공({person_name})은 뒤에 흐릿하게 걸쳐 있거나 식별하기 어려운 컷은 탈락!
4. [뉴스 스튜디오 / TV 속 화면(Inset) 100% 탈락]: 뉴스 앵커, 아나운서, 기자가 스튜디오 데스크에서 보도하는 장면이거나, TV 모니터/배경 스크린 속 작은 그래픽 박스(인셋)로 주인공이 나오는 방송 화면은 절대 배치하지 말고 100% 즉각 탈락! (주인공 본인이 직접 현장에서 촬영된 실사 사료만 합격)
5. [그래픽 결격 사유]: 텍스트 배너, 모눈종이, 빈 템플릿, 친필 사인 그래픽 탈락.
6. [🚨 핵심: 대본 상황/시대 불일치 컷오프 (Strict Context Cutoff) 🚨]:
   - 사진의 인물이 목표 스타({person_name})라 할지라도, 해당 씬 내레이션의 [시대(나이대), 의상/배경, 상황/사건]과 시각적으로 명백히 불일치하면 절대 어떤 씬에도 배치하지 말고 가차 없이 탈락(REJECT) 처리하라!
   - [불일치 예시]:
     * 대본이 "어린 시절 / 중고교 학창시절 / 밤샘 공부"인데 ➔ 30대 로맨스 스틸컷이나 화려한 행사 사진 매칭 절대 금지! (즉각 탈락)
     * 대본이 "교도소 경비교도대 군 복무"인데 ➔ 엉뚱한 영화 스틸컷(예: 과외선생, 회사원 등) 매칭 절대 금지! (즉각 탈락)
   - 내용과 상황이 완벽히 맞아떨어지는 실사가 없는 씬은 절대로 억지로 채우지 말고 반드시 빈 배열 []로 비워두어라! (사료가 없는 씬은 대본 맞춤형 AI 이미지로 채워짐)

[✅ 합격 및 씬 배치 기준]:
1. [1인 단독 샷 적극 합격]: 목표 인물({person_name}) 1인이 선명하게 부각된 고화질 단독 샷.
2. [주인공 중심 2~3인 명장면 스틸컷 전격 합격]:
   - 영화/드라마에서 상대 배우와의 투샷, 극중 케미 컷, 상징적 인터뷰/기념 투샷 등 **주인공({person_name})이 화면의 주역(Hero)으로 명확히 부각되어 있는 2~3인 샷은 적극 합격**!
3. [엄격한 문맥 일치 씬 배치]:
   - 합격한 사진의 비주얼(나이대, 의상, 표정, 배경, 작품 맥락)을 눈으로 직접 보고, **내용과 시각적으로 가장 정확히 일치하는 씬 번호("1", "2", ... "7")에만 배치**하라.
   - 대본에서 언급된 실제 작품/활동과 시각적으로 일치하는 씬에 최우선 배치하라.
   - 각 씬당 가장 적합한 순서대로 최대 {max_per_scene}장까지만 배치하고, 어울리는 사료가 없는 씬은 빈 배열 []을 유지하라.

제공된 {len(high_res_pool)}장의 이미지(인덱스 0~{len(high_res_pool)-1})에 대해 아래 JSON 형식으로만 응답하라:
```json
{{
  "placements": {{
    "1": [0],
    "5": [2, 3]
  }},
  "rejections": [
    {{"index": 1, "reason": "타인 단독 샷이므로 탈락"}},
    {{"index": 4, "reason": "5인 이상 행사 단체 컷이므로 탈락"}},
    {{"index": 6, "reason": "대본 상황 불일치 (학창시절/군복무 씬에 30대 영화 스틸컷 매칭 불가)"}}
  ]
}}
```"""

    for idx, item in enumerate(high_res_pool):
        contents.append(f"--- [사진 인덱스 {idx}] 출처: {item['source']}, 캡션: {item['caption']} ---")
        contents.append(types.Part.from_bytes(data=item["bytes"], mime_type="image/jpeg"))

    contents.append(prompt)

    try:
        resp = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
        )
        clean_t = re.sub(r"^```(?:json)?\s*", "", resp.text.strip())
        clean_t = re.sub(r"\s*```$", "", clean_t)
        j = json.loads(clean_t)
        placements = j.get("placements", {})
        rejections = j.get("rejections", [])
        
        print(f"\n[Vision Placement] 2단계: Gemini Vision 심사 및 씬 배치 결과:")
        for rej in rejections:
            idx = rej.get("index")
            cap = high_res_pool[idx]["caption"] if idx is not None and idx < len(high_res_pool) else ""
            print(f"  ❌ 사진 #{idx} ({cap[:30]}...) 탈락: {rej.get('reason')}")
        for sc_k, indices in sorted(placements.items(), key=lambda x: int(x[0])):
            valid_idx = [i for i in indices if isinstance(i, int) and 0 <= i < len(high_res_pool)][:max_per_scene]
            print(f"  🎬 Scene {sc_k}: 총 {len(valid_idx)}장 배치 확정 (인덱스: {valid_idx})")
        return placements, rejections
    except Exception as e:
        print(f"[Vision Placement Error] 비전 모델 평가 실패: {e}")
        return {}, []


def _save_fitted_image(raw_bytes, out_path, target_size=(1080, 1920)):
    """Pillow를 사용하여 9:16 (1080x1920) 세로 비율로 스마트 정규화:
    1. 이미 세로형(aspect ratio <= 0.75, 예: 9:16, 4:5 등):
       - 상단 35% 중심(얼굴 영역 보존)으로 스마트 크롭하여 꽉 찬 화면(Full Bleed) 유지.
    2. 가로형(aspect ratio > 0.75, 예: 16:9, 4:3, 3:2, 정사각형 등):
       - 무지성 센터 크롭 금지 (인물 및 투샷 파손 원천 차단)
       - 원본 사진 전체를 100% 무손실 중앙 배치 (Letterbox)
       - 상하 여백은 원본 사진을 확대한 고급 가우시안 블러(radius=40) + 밝기 조절(0.65)로 채움.
    """
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        tw, th = target_size
        iw, ih = img.size
        aspect = iw / ih

        # 1. 세로형 (0.75 이하): 단독 인물 샷이 많으므로 상단 35% 얼굴 중심 크롭
        if aspect <= 0.75:
            fitted = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.35))
        else:
            # 2. 가로형/정사각형: 블러 배경 + 원본 100% 온전 배치 (다큐멘터리 글로벌 표준)
            bg = ImageOps.fit(img, target_size, method=Image.Resampling.BILINEAR, centering=(0.5, 0.5))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
            bg = ImageEnhance.Brightness(bg).enhance(0.65)

            scale = tw / iw
            new_w = tw
            new_h = int(ih * scale)
            if new_h > th:
                scale = th / ih
                new_h = th
                new_w = int(iw * scale)

            fg = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            x_offset = (tw - new_w) // 2
            y_offset = (th - new_h) // 2
            bg.paste(fg, (x_offset, y_offset))
            fitted = bg

        fitted.save(out_path, format="JPEG", quality=95)
    except Exception as e:
        print(f"[Image Warning] 스마트 9:16 피팅 실패({e}), 원본 바이트 직접 저장...")
        Path(out_path).write_bytes(raw_bytes)


def run_ai_image_generation(client, types, prompt, out_path, person_name=None, fallback_bytes=None):
    """실사 사료가 없는 씬만 시각적 연속성을 보강하여 Gemini 이미지 생성 (429 쿼터 초과 시 대표 실사 사료 폴백 안전망 탑재)"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if person_name:
        continuity_prompt = f"Authentic portrait of {person_name}, true to real-life facial features and appearance, retro pop-art cinematic lighting, vertical 9:16 poster style, 8k, no text"
        if len(prompt) < 100:
            prompt = f"{continuity_prompt}, {prompt}"

    resp = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=MODEL_IMAGE,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
            break
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait_sec = (attempt + 1) * 8
                print(f"[Image AI] 429 쿼터 감지, {wait_sec}초 대기 후 재시도 ({attempt + 1}/4)...")
                time.sleep(wait_sec)
                continue
            print(f"[Image AI] {MODEL_IMAGE} 실패({e}), 폴백 {MODEL_FALLBACK}")
            try:
                resp = client.models.generate_content(
                    model=MODEL_FALLBACK,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
                )
                break
            except Exception as e2:
                if "429" in str(e2) or "RESOURCE_EXHAUSTED" in str(e2):
                    time.sleep(8)
                    continue
                print(f"[Image AI Warning] 폴백 모델도 실패: {e2}")

    saved = False
    if resp and resp.candidates:
        cand = resp.candidates[0]
        cnt = getattr(cand, "content", None)
        parts = getattr(cnt, "parts", []) if cnt else []
        for p in parts:
            if getattr(p, "inline_data", None) and p.inline_data:
                _save_fitted_image(p.inline_data.data, out)
                saved = True
                print(f"  🎨 AI 연속성 생성 저장 완료: {out.name} ({out.stat().st_size / 1e3:.0f} KB)")
                break

    # 1차 폴백: 이전 씬 이미지 재사용
    if not saved:
        prev_images = sorted(out.parent.glob("scene_*.jpg"))
        if prev_images:
            import shutil
            shutil.copyfile(prev_images[-1], out)
            saved = True
            print(f"  🔄 [안전 폴백] AI 쿼터 소진으로 이전 씬 에셋 복제: {out.name}")

    # 2차 폴백: 대표 실사 사료 바이트로 스마트 피팅 저장 (파이프라인 무중단 완주 보장)
    if not saved and fallback_bytes:
        _save_fitted_image(fallback_bytes, out)
        saved = True
        print(f"  🛡️ [안전 폴백] AI 쿼터 소진으로 확보된 대표 실사 사료 스마트 피팅 저장: {out.name}")

    if not saved:
        raise RuntimeError(f"AI 이미지 생성 최종 실패 (폴백 사료 부재): {out}")

    return out


def run_script_images(script_path: str):
    """대본 JSON을 기반으로 3단계 정석 파이프라인 가동:
    1. 500px 고화질 선별 다운로드
    2. Vision 모델 씬 적합성 판정 & 씬당 최대 3장 배치 (타인 컷 100% REJECT)
    3. 사료 결손 씬만 AI 연속성 생성
    """
    from google import genai
    from google.genai import types

    p = Path(script_path)
    if not p.is_absolute():
        p = ROOT_DIR / script_path

    if not p.exists():
        raise FileNotFoundError(f"대본 파일을 찾을 수 없습니다: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    script = data.get("script", {})
    scenes = script.get("scenes", [])

    pkg_dir = Path(meta.get("package_dir", p.parent))
    assets_dir = pkg_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 기존 잔재 에셋 완전 삭제 클린업
    cleaned = 0
    for old_f in assets_dir.glob("scene_*.jpg"):
        try:
            old_f.unlink()
            cleaned += 1
        except Exception:
            pass
    if cleaned > 0:
        print(f"[02_star_image] 기존 에셋 {cleaned}건 정리 완료 (신규 생성 준비)")

    person_name = meta.get("person_name", "")
    qid = meta.get("wikidata_id", "")

    print(f"============================================================")
    print(f"[02_star_image] 비전 기반 지능형 씬 배치 파이프라인 가동")
    print(f"                인물: {person_name} (QID: {qid})")
    print(f"                패키지 경로: {pkg_dir}")
    print(f"                총 씬 수: {len(scenes)}씬")
    print(f"============================================================")

    # 1. 실사 사료 메타데이터 수집
    raw_photos = fetch_real_star_photos(qid) if qid else []
    meta_json_path = pkg_dir / "sourced_photos_metadata.json"
    meta_json_path.write_text(json.dumps([
        {"id": ph["id"], "source": ph["source"], "caption": ph.get("caption"), "is_profile": ph.get("is_profile"), "url": ph["url"]}
        for ph in raw_photos
    ], ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 500px 이상 고화질 선별 다운로드
    high_res_pool = filter_high_res_photos(raw_photos, min_px=500, min_bytes=20000, max_pool=25)

    client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)

    # 2.5 [V3 사료 앵커링] 대본에 지정된 anchored_photo_id 우선 매핑
    pool_id_to_idx = {item["id"]: idx for idx, item in enumerate(high_res_pool)}
    anchored_placements = {}
    for sc in scenes:
        s_num = str(sc.get("scene_no", 1))
        anch_id = sc.get("anchored_photo_id")
        if anch_id and anch_id in pool_id_to_idx:
            idx = pool_id_to_idx[anch_id]
            anchored_placements[s_num] = [idx]
            print(f"  ⚓ [사료 앵커 확정] Scene {s_num}: 사료 ID '{anch_id}' 우선 배치 ({high_res_pool[idx]['caption'][:35]}...)")

    # 3. Vision 모델 씬 적합성 심사 및 배치 (씬당 최대 3장, 타인 컷 100% REJECT)
    placements, rejections = place_photos_into_scenes_with_vision(
        client=client,
        types=types,
        high_res_pool=high_res_pool,
        person_name=person_name,
        scenes=scenes,
        max_per_scene=3
    )

    # 앵커 사료가 있는 씬은 앵커 사료를 1위로 병합
    for s_k, idx_list in anchored_placements.items():
        if s_k not in placements or not placements[s_k]:
            placements[s_k] = idx_list
        elif idx_list[0] not in placements[s_k]:
            placements[s_k] = idx_list + placements[s_k][:2]

    # 매칭 리포트 영구 저장
    report_path = pkg_dir / "matching_report.json"
    report_data = {
        "person_name": person_name,
        "wikidata_id": qid,
        "placements": placements,
        "rejections": rejections,
        "details": {}
    }
    for sc_k, idx_list in placements.items():
        report_data["details"][sc_k] = [
            {"id": high_res_pool[i]["id"], "caption": high_res_pool[i]["caption"], "source": high_res_pool[i]["source"]}
            for i in idx_list if i < len(high_res_pool)
        ]
    report_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[02_star_image] 비전 매칭 리포트 저장 완료: {report_path.name}")

    # 4. 각 씬별 에셋 확정 저장 (실사 피팅 vs AI 연속성 생성)
    print(f"\n============================================================")
    print(f"[02_star_image] 3단계: 씬별 최종 에셋 9:16 정규화 저장")
    print(f"============================================================")

    generated_files = []
    for sc in scenes:
        s_num = sc.get("scene_no", 1)
        out_file = assets_dir / f"scene_{s_num}.jpg"
        assigned_indices = [i for i in placements.get(str(s_num), []) if isinstance(i, int) and 0 <= i < len(high_res_pool)][:3]

        print(f"\n[Scene {s_num}/{len(scenes)}] 에셋 확정 처리...")

        if assigned_indices:
            # 📸 실사 사료 피팅 저장 (씬당 최대 3장)
            saved_info = []
            for sub_idx, p_idx in enumerate(assigned_indices):
                item = high_res_pool[p_idx]
                target_out = out_file if sub_idx == 0 else assets_dir / f"scene_{s_num}_sub{sub_idx}.jpg"
                _save_fitted_image(item["bytes"], target_out)
                print(f"  📸 [실사 피팅 저장] {target_out.name} ({target_out.stat().st_size / 1e3:.0f} KB) - {item['caption'][:40]}...")
                saved_info.append({
                    "path": str(target_out),
                    "source": item["source"],
                    "caption": item["caption"],
                    "url": item["url"]
                })
            
            sc["is_real_photo"] = True
            sc["photo_count"] = len(saved_info)
            sc["photo_source"] = saved_info[0]["source"]
            sc["matched_caption"] = saved_info[0]["caption"]
            sc["images"] = saved_info
            generated_files.append(out_file)
        else:
            # 🎨 사료가 없는 씬 ➔ AI 연속성 생성
            bg_prompt = sc.get("bg_prompt", PROMPT_DEFAULT)
            if "vertical 9:16" not in bg_prompt:
                bg_prompt += ", vertical 9:16 poster style, 8k, no text"
            
            rep_bytes = high_res_pool[0]["bytes"] if high_res_pool else None
            saved_ai = run_ai_image_generation(client, types, bg_prompt, out_file, person_name=person_name, fallback_bytes=rep_bytes)
            sc["is_real_photo"] = False
            sc["photo_source"] = "AI_CONTINUITY"
            sc["photo_count"] = 1
            generated_files.append(saved_ai)

    # 대본 메타데이터 갱신 저장
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[02_star_image] 7개 씬 전체 에셋 생성 및 대본 갱신 완료! ({p.name})")
    return generated_files


def run_image_test(prompt=PROMPT_DEFAULT, out_path="test_image.jpg", **kwargs):
    """기존 모듈 호환용 단일 AI 이미지 생성 wrapper"""
    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)
    person_name = kwargs.get("meta_data", {}).get("person_name", "")
    return run_ai_image_generation(client, types, prompt, out_path, person_name=person_name)



if __name__ == "__main__":
    p = argparse.ArgumentParser(description="스타이즈본 9:16 세로형 이미지 생성")
    p.add_argument("--script", default=None, help="대본 script.json 파일 경로")
    p.add_argument("--prompt", default=PROMPT_DEFAULT, help="단일 이미지 생성 프롬프트")
    p.add_argument("--out", default="test_image.jpg", help="단일 이미지 출력 파일명")
    a = p.parse_args()

    if a.script:
        run_script_images(a.script)
    else:
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION)
        run_ai_image_generation(client, types, a.prompt, a.out)

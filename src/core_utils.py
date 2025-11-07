# core_utils.py
import re
from html import unescape
try:
    import kss  # 선택: 설치되어 있으면 사용
    _HAS_KSS = True
except Exception:
    _HAS_KSS = False
import difflib
import os
import time
import psutil
import urllib.parse
import logging
import requests
import pandas as pd

from bs4 import BeautifulSoup
from konlpy.tag import Okt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from difflib import SequenceMatcher

# 날짜
today = datetime.now().strftime("%y%m%d")

# 드라이버 경로 (본인 PC에 맞게 수정)
driver_path = r"C:\chromedriver-win64\chromedriver.exe"

okt = Okt()

# 제외 도메인 로드
excluded_domains = pd.read_excel("../../excel/수집 제외 도메인 주소.xlsx")["제외 도메인 주소"].dropna().tolist()

# 로그 설정
os.makedirs("../../log", exist_ok=True)
logging.basicConfig(
    filename=f"../../log/로그_{today}.txt",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def log(msg, index=None):
    prefix = f"[{index+1:03d}] " if index is not None else ""
    full_msg = f"{prefix}{msg}"
    print(full_msg)
    logging.info(full_msg)

def create_driver(index=None):
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.media_stream": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.media_stream_mic": 2,
            "profile.default_content_setting_values.media_stream_camera": 2,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = webdriver.Chrome(service=Service(driver_path), options=options)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        })

        return driver
    except Exception as e:
        log(f"❌ 드라이버 생성 실패: {e}", index)
        return None



def kill_driver(driver, index=None):
    if driver:
        try:
            driver.quit()
        except Exception as e:
            log(f"⚠️ driver.quit() 실패: {e}", index)

        try:
            pid = getattr(driver.service.process, 'pid', None)
            if pid and psutil.pid_exists(pid):
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.kill()
                parent.kill()
                log(f"💀 ChromeDriver PID {pid} 강제 종료 완료 (자식 {len(children)}개)", index)
        except Exception as e:
            log(f"⚠️ 강제 프로세스 종료 실패: {e}", index)


def clean_text(text):
    if not isinstance(text, str):
        text = str(text)

    # "nan" 문자열 제거
    if text.strip().lower() == 'nan':
        return ""

    #  비디오 플레이어 관련 시스템 문구 제거
    patterns_to_remove = [
        r"Video Player",  # "Video Player" 라인
        r"Video 태그를 지원하지 않는 브라우저입니다\.",  # 안내 문구
        r"\d{2}:\d{2}",  # 00:00 형식 시간
        r"[01]\.\d{2}x",  # 재생속도 (예: 1.00x)
        r"출처:\s?[^\n]+",  # 출처: KBS News 등
        r"/\s?\d+\.?\d*",   # / 2 또는 / 2.00 형태까지 모두 제거
        r"Your browser does not support the video tag."
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text)

    #  특수 문자 및 이스케이프 정리
    text = text.replace("\\\"", "\"").replace("\\'", "'").replace("\\\\", "\\")
    text = re.sub(r"[ㅋㅎㅠㅜ]+", "", text)
    text = re.sub(r"[!?~\.\,\-#]{2,}", "", text)

    #  HTML 엔티티 및 특수 문자 제거
    text = re.sub(r"&[a-z]+;|&#\d+;", "", text)

    #  공백 및 제어 문자 정리
    text = re.sub(r"[\\\xa0\u200b\u3000\u200c_x000D_]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()

#키워드 추출
def extract_keywords(text, num_keywords=5):
    nouns = okt.nouns(text)
    return " ".join(nouns[:num_keywords])

#문장 추출
def extract_first_sentences(text):
    paras = re.split(r'\n{2,}', text.strip())
    get_first = lambda p: re.split(r'(?<=[.!?])(?=\s|[가-힣])', p.strip())[0] if p else ""
    get_last = lambda p: re.split(r'(?<=[.!?])(?=\s|[가-힣])', p.strip())[-1].strip() if p else ""
    first = get_first(paras[0]) if len(paras) > 0 else ""
    second = get_first(paras[1]) if len(paras) > 1 else ""
    last = get_last(paras[-1]) if len(paras) > 0 else ""

    return first, second, last

#문장 유사도 확인함수
def calculate_copy_ratio(article, post):
    def clean(t): return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()
    article, post = clean(article), clean(post)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article) if s.strip()]
    if not sentences: return 0.0
    scores = []
    for s in sentences:
        try:
            v = TfidfVectorizer().fit([s, post])
            tfidf = v.transform([s, post])
            scores.append(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except:
            continue
    return round(sum(scores)/len(scores), 3) if scores else 0.0

#같은 문장 유무 확인함수
def similar_sentence(article, post, threshold=0.3):

    article_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article) if s.strip()]
    post_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', post) if s.strip()]

    for art_s in article_sentences:
        for post_s in post_sentences:
            try:
                vectorizer = TfidfVectorizer().fit([art_s, post_s])
                tfidf = vectorizer.transform([art_s, post_s])
                sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
                if sim >= threshold:
                    return True
            except:
                continue
    return False


def safe_get(driver, url, timeout=90, index=None):
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        return True
    except Exception as e:
        log(f"⏰ safe_get 페이지 로딩 실패: {url} ({e})", index)

        if "connection refused" in str(e).lower() or "connection aborted" in str(e).lower():
            log("💥 드라이버 세션이 죽었습니다. 새로 생성합니다.", index)
            kill_driver(driver, index)
            return False

        kill_driver(driver, index)
        return False

def load_trusted_oids():
    def load_oid_from_excel(filename):
        try:
            # 핵심: int → str → zfill(3)
            return set(
                pd.read_excel(filename)["oid"]
                .dropna()
                .astype(int)
                .astype(str)
                .apply(lambda x: x.zfill(3))
            )
        except Exception as e:
            log(f"⚠️ {filename} 로딩 실패: {e}")
            return set()

    base_path = "../../oid 리스트"  # 폴더 경로에 맞게 수정A
    news_oids = load_oid_from_excel(os.path.join(base_path, "네이버뉴스 신탁언론 oid.xlsx"))

    sports_oids = load_oid_from_excel(os.path.join(base_path, "네이버스포츠 신탁언론 oid.xlsx"))
    entertain_oids = load_oid_from_excel(os.path.join(base_path, "네이버엔터 신탁언론 oid.xlsx"))

    return news_oids, sports_oids, entertain_oids

trusted_news_oids, trusted_sports_oids, trusted_entertain_oids = load_trusted_oids()

def load_trusted_domains(xlsx_path: str) -> list[str]:
    try:
        df = pd.read_excel(xlsx_path)
        # '도메인' 컬럼에서 공백/대소문자 정리
        doms = (
            df["도메인"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )
        return doms
    except Exception as e:
        log(f"⚠️ 도메인 화이트리스트 로딩 실패: {e}")
        return []

# 절대경로: 질문에서 주신 경로 그대로 사용
TRUSTED_DOMAINS = load_trusted_domains(
    r"D:\jupyter\community_site_crawling-main\원문기사\oid 리스트\매체사_도메인_정보.xlsx"
)
log(f"📦 도메인 화이트리스트 크기: {len(TRUSTED_DOMAINS)}")

def fallback_with_requests(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")
        content_div = soup.select_one("#dic_area, article")
        if content_div:
            return content_div.get_text(strip=True)
        paragraphs = soup.find_all("p")
        return "\n".join(p.get_text(strip=True) for p in paragraphs)
    except:
        return ""

def get_news_article_body(url, driver, max_retries=2, index=None):
    for attempt in range(max_retries):
        try:
            if not safe_get(driver, url, timeout=90, index=index):
                log(f"⏰ get_news_article_body 로딩 실패 (시도 {attempt+1}) → 드라이버 재생성", index)
                kill_driver(driver, index)
                driver = create_driver(index)
                if driver is None:
                    log("❌ 드라이버 재생성 실패", index)
                    return "", None
                continue

            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            domain = urllib.parse.urlparse(url).netloc

            selector_map = {
                    "n.news.naver.com": "article#dic_area",
                    "m.sports.naver.com": "div._article_content",
                    "m.entertain.naver.com": "article#comp_news_article div._article_content",

                    "edaily.co.kr": "div.news_body", # 1 이데일리
                    "mt.co.kr": "div#textBody", # 2 머니투데이
                    "fnnews.com": "div#article_content",  # 3 파이낸셜뉴스
                    "khan.co.kr": "div#articleBody", # 4 경향신문
                    "sedaily.com": "div.article_view", # 5 서울경제
                    "dailian.co.kr": "div.article", # 6 데일리안
                    "news.bizwatch.co.kr": "div.news_body.new_editor", # 7 비즈워치
                    "asiae.co.kr": "div#txt_area",  # 8 아시아경제
                    "kmib.co.kr": "div#articleBody", # 9 국민일보
                    "biz.heraldcorp.com": "article#articleText", #10 헤럴드경제
                    "newspim.com": "div#news-contents", #11 뉴스핌
                    "hani.co.kr": "div.article-text", #12 한겨레
                    "nocutnews.co.kr": "div#pnlContent", #13 노컷뉴스
                    "ytn.co.kr": "div#CmAdContent",  #14 YTN
                    "segye.com": "div#article_txt", #15 세계일보
                    #"hankookilbo.com": "div.col-main", #16 한국일보
                    "seoul.co.kr": "div.viewContent.body18.color700", #17 서울신문
                    "imbc.com": "div.news_txt", #18 MBC
                    "cctimes.kr": "div#article-view-content-div", #19 충청타임즈
                    "busan.com": "div.article_content", #20 부산일보
                    "sbs.co.kr": "div.text_area", #21 SBS
                    "kbs.co.kr": "div#cont_newstext", #22 KBS
                    "etoday.co.kr": "div.articleView", #23 이투데이
                    "breaknews.com": "div#CLtag", #24 BreakNews
                    "koreaherald.com": "article#articleText", #25 코리아헤럴드
                    "incheonilbo.com": "article#article-view-content-div", #26 인천일보
                    "etnews.com": "div#articleBody", #27 전자신문
                    "kookje.co.kr": "div.news_article", #28 국제신문
                    "ajunews.com": "div#articleBody", #29 아주경제
                    "imaeil.com": "div#articlebody", #30 매일신문
                    "kyeonggi.com": "div.article_cont_wrap", #31 경기일보
                    "ggilbo.com": "article.article-veiw-body", #32 금강일보
                    "domin.co.kr": "div#article-view-content-div",#33 전북도민일보
                    "asiatoday.co.kr": "div#font", #34 아시아투데이
                    "kado.net": "article.article-veiw-body", #35 강원도민일보
                    "mbn.co.kr": "div#newsViewArea", #36 MBN
                    "ksilbo.co.kr": "article.article-veiw-body", #37 경상일보
                    "joongboo.com": "article.article-veiw-body", #38 중부일보
                    "jbnews.com": "article.article-veiw-body", #39 중부매일
                    "kwangju.co.kr": "div#joinskmbox", #40 광주일보
                    "kwnews.co.kr": "div#articlebody", #41 강원일보
                    "economist.co.kr": "div#article_body", #42 이코노미스트
                    "sports.khan.co.kr": "div#articleBody",#43 스포츠경향
                    "kgnews.co.kr": "div#news_body_area", #44 경기신문
                    "nongmin.com": "div.news_txt.ck-content", #45 농민신문
                    "yeongnam.com": "article.article-news-box", #46 영남일보
                    "sisain.co.kr": "article.article-veiw-body", #47 시사IN
                    "isplus.com": "div#article_body", #48 일간스포츠
                    "inews365.com": "div.article", #49 충북일보
                    "daejonilbo.com": "article.article-veiw-body", #50 대전일보
                    "kihoilbo.co.kr": "article.article-veiw-body", #51 기호일보
                    "newspenguin.com": "article.article-veiw-body", #52 뉴스펭귄
                    "mediatoday.co.kr": "article.article-veiw-body", #53 미디어오늘
                    "mdilbo.com": "div.article_view", #54 무등일보
                    "kyeongin.com": "div#article-body", #55 경인일보
                    "gnnews.co.kr": "div.news_text", #56 경남일보
                    "sportsseoul.com": "div#article-body", #57 스포츠서울
                    "idaegu.co.kr": "div.news_text", #58 대구신문
                    "idaegu.com": "article.article-veiw-body", #59 대구일보
                    "idomin.com": "article.article-veiw-body", #60 경남도민일보
                    "namdonews.com": "article.article-veiw-body", #61 남도일보
                    "obsnews.co.kr": "article.article-veiw-body", #62 OBS
                    "kyongbuk.co.kr": "article.article-veiw-body", #63 경북일보
                    "knnews.co.kr": "div.cont_cont", #64 경남신문
                    "sports.hankooki.com": "article.article-veiw-body", #65 스포츠한국
                    "jjan.kr": "div.article_txt_container", #66 전북일보
                    "joongdo.co.kr": "div#font", #67 중도일보
                    "hidomin.com": "div#article-view-content-div", #68 경북도민일보
                    "naeil.com": "div.article-view", #69 내일신문
                    "kjdaily.com": "div#content", #70 광주매일신문
                    "cctoday.co.kr": "article.article-veiw-body", #71 충청투데이
                    "jnilbo.com": "div#content", #72 전남일보
                    "viva100.com": "div.news_content", #73 브릿지경제
                    "sportsworldi.com": "article.viewBox2", #74 스포츠월드
                    "sjbnews.com": "span.news_text.cl6.p-b-25", #75 새전북신문
                    "dynews.co.kr": "article.article-veiw-body", #76 동양일보
                    "iusm.co.kr": "article.article-veiw-body", #77 울산매일
                    "dnews.co.kr": "div.text", #78 e대한경제
                    "hellodd.com": "article.article-veiw-body", #79 헬로디디
                    "ilyo.co.kr": "div.contentView.ctl-font-ty2.editorType2", #80 일요신문
                    "ccdailynews.com": "article.article-veiw-body", #81 충청일보
                    "djtimes.co.kr": "article.article-veiw-body", #82 당진시대
                    "hkbs.co.kr": "article.article-veiw-body", #83 환경일보
                    "h21.hani.co.kr": "div.arti-txt.0", #84 한겨레21
                    "ihalla.com": "div.article_txt", #85 한라일보
                    "ulsanpress.net": "article.article-veiw-body", #86 울산신문
                    "jejunews.com": "div#article-view-content-div", #87 제주일보
                    "wonjutoday.co.kr": "article.article-veiw-body", #88 원주투데이
                    "kbmaeil.com": "div.news_content", #89 경북매일신문
                    "weekly.hankooki.com": "article.article-veiw-body", #90 주간한국
                    "yjinews.com": "article.article-veiw-body", #91 영주시민신문
                    "ebn.co.kr": "article.article-veiw-body", #92 EBN산업뉴스
                    "kidshankook.kr": "article.article-veiw-body", #93 소년한국일보
                    "journalist.or.kr": "div#news_body_area", #94 기자협회보
                    "jeollailbo.com": "article.article-veiw-body", #95 전라일보
                    "jemin.com": "article.article-veiw-body", #96 제민일보
                    "kukinews.com": "div#articleContent", #97 쿠키뉴스
                    "ekn.kr": "div#news_body_area_contents", #98 에너지경제
                    "pttimes.com": "article.article-veiw-body", #99 평택시민신문
                    "mediapen.com": "div#articleBody", #100미디어펜
                    "koreatimes.com": "div#print_arti", #101코리아타임스
                    "okinews.com": "div#article-view-content-div", #102옥천신문
                    "igimpo.com": "article.article-veiw-body", #103김포신문
                    #"gwangnam.co.kr": "div#content", #104광남일보
                    "pdjournal.com": "article.article-veiw-body", #105PD저널
                    "pennmike.com": "article.article-veiw-body", #106펜앤드마이크
                    "hsnews.co.kr": "article.article-veiw-body", #107홍성신문
                    "metroseoul.co.kr": "div.col-12", #108메트로경제
                    "pressian.com": "div.article_body", #109프레시안
                    "womaneconomy.co.kr": "article.article-veiw-body", #110여성경제신문
                    #"wooriy.com": "", #111영암우리신문
                    "gynet.co.kr": "div#article-view-content-div", #112광양신문
                    "newssc.co.kr": "div#article-view-content-div", #113뉴스서천
                    "kidkangwon.co.kr": "div#article-view-content-div", #114어린이강원
                    "mygoyang.com": "article.article-veiw-body", #115주간고양신문
                    "soraknews.co.kr": "td#ct", #116주간설악신문
                    "seoulwire.com": "article.article-veiw-body", #117서울와이어
            }

            selector = next((v for k, v in selector_map.items() if k in domain), None)
            if selector:
                div = soup.select_one(selector)
                if div:
                    body = div.get_text(separator="\n", strip=True)
                    if len(body) > 300:
                        return body, driver

            fallback = fallback_with_requests(url)
            return fallback, driver

        except Exception as e:
            log(f"❌ get_news_article_body 예외 발생 (시도 {attempt+1}): {e}", index)
            kill_driver(driver, index)
            driver = create_driver(index)
            if driver is None:
                log("❌ 드라이버 재생성 실패", index)
                return "", None
            time.sleep(1)

    kill_driver(driver, index)
    fallback = fallback_with_requests(url)
    return fallback, None


def is_excluded(url):
    return any(domain in url for domain in excluded_domains)

MAX_QUERY_LENGTH = 100

def generate_search_queries(title, first, second, last):
    def truncate(text):
        return text[:MAX_QUERY_LENGTH] if text else ""
    # 입력 텍스트들 정제
    title_clean = truncate(clean_text(title))
    first_clean = truncate(clean_text(first))
    second_clean = truncate(clean_text(second))
    last_clean = truncate(clean_text(last))

    keywords = truncate(extract_keywords(title_clean))

    queries = list(set(filter(None, [
        title_clean,
        # keywords + " " + press,
        first_clean,
        second_clean,
        last_clean
    ])))
    return queries

def extract_oid_from_naver_url(link):
    parsed = urlparse(link)
    path = parsed.path

    # 패턴: /article/<oid>/<aid>
    match = re.search(r"/article/(\d{3})/\d+", path)
    if match:
        return match.group(1)

    # 예외적: n.news.naver.com/mnews/article/<oid>/<aid>
    match = re.search(r"/mnews/article/(\d{3})/\d+", path)
    if match:
        return match.group(1)

    return None

def search_news_with_api(queries, driver, client_id, client_secret, max_results=15, index=None):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    results = []
    seen_links = set()

    for q in queries:
        url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display={max_results}&sort=sim"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                log(f"⚠️ API 검색 실패 ({res.status_code}) - {q}", index)
                continue

            items = res.json().get("items", [])
            for item in items:
                link = item.get("link")
                title = BeautifulSoup(item.get("title", ""), "html.parser").get_text()

                if not link or link in seen_links or is_excluded(link):
                    continue

                if "naver.com" in link:
                    oid = extract_oid_from_naver_url(link)
                    if not oid:
                        log(f"⚠️ OID 추출 실패 → 스킵: {link}", index)
                        continue

                    if "n.news.naver.com" in link:
                        if oid not in trusted_news_oids:
                            # log(f"🚫 비신탁 뉴스 언론 (oid={oid}) → {link}", index)
                            continue
                    elif "sports.naver.com" in link:
                        if oid not in trusted_sports_oids:
                            # log(f"🚫 비신탁 스포츠 언론 (oid={oid}) → {link}", index)
                            continue
                    elif "entertain.naver.com" in link:
                        if oid not in trusted_entertain_oids:
                            # log(f"🚫 비신탁 엔터 언론 (oid={oid}) → {link}", index)
                            continue

                else:
                    netloc = urlparse(link).netloc.lower()  # ex) www.ajunews.com
                    # www/m 등 서브도메인까지 허용하려면 endswith 사용
                    if TRUSTED_DOMAINS:  # 리스트가 비어있을 땐 필터 생략(디버그 편의)
                        ok = any(
                            netloc == d or netloc.endswith("." + d) or netloc.endswith(d)
                            for d in TRUSTED_DOMAINS
                        )
                        if not ok:
                            # log(f"🚫 비화이트리스트 도메인 제외: {netloc} → {link}", index)
                            continue

                body, new_driver = get_news_article_body(link, driver, index=index)
                if new_driver != driver:
                    log("🔁 드라이버가 새로 갱신되었습니다", index)
                    driver = new_driver

                seen_links.add(link)
                body, _ = get_news_article_body(link, driver, index=index)
                if body and len(body) > 300:
                    cleaned_body = clean_text(body)
                    results.append({"title": title, "link": link, "body": cleaned_body})

        except Exception as e:
            log(f"❌ API 검색 오류: {e}", index)
            continue

    return results

def _normalize_for_exact(s: str) -> str:
    s = unescape(s)
    s = re.sub(r'<[^>]+>', ' ', s)              # HTML 태그 제거
    s = s.replace('“','"').replace('”','"').replace('’',"'").replace('‘',"'")
    s = s.replace('–', '-').replace('—', '-')   # 대시 통일
    # 괄호류 간단 통일
    s = s.replace('（','(').replace('）',')').replace('[','(').replace(']',')')
    # 숫자 콤마 제거(8,060 -> 8060)
    s = re.sub(r'(?<=\d),(?=\d)', '', s)
    # 공백 정리
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _split_sentences(text: str):
    text = text.strip()
    if not text:
        return []
    if _HAS_KSS:
        return [s.strip() for s in kss.split_sentences(text) if s and s.strip()]
    # fallback: 마침표/물음표/느낌표 + 줄바꿈
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [p.strip() for p in parts if p and p.strip()]

def _is_valid_sentence(s: str, min_chars=20, min_tokens=5):
    if len(s) < min_chars:
        return False
    if len(re.findall(r'\w+', s)) < min_tokens:
        return False
    return True

def _almost_equal(a: str, b: str, tol: float = 0.98) -> bool:
    """구두점/공백 등 미세차이를 허용하는 '거의 완전일치'."""
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio() >= tol

"""
def calculate_sequence_matcher_ratio(article: str, post: str) -> float:
    
    SequenceMatcher 기반 단방향 복사율:
      - article(원문)의 글자 중 post(게시글)에 포함되는 비율 계산
      - 글자 단위 비교이므로 띄어쓰기/순서 일치에 민감
    
    def _clean(t):
        t = "" if t is None else str(t)
        t = re.sub(r"[^\w\s]", "", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    article_clean = _clean(article)
    post_clean = _clean(post)

    if not article_clean or not post_clean:
        return 0.0

    # post_clean이 article_clean과 얼마나 겹치는지 확인
    matcher = SequenceMatcher(None, post_clean, article_clean)
    matched_len = sum(block.size for block in matcher.get_matching_blocks() if block.size > 0)
    ratio = matched_len / len(article_clean)
    return round(ratio, 3)
"""

def exact_copy_rate(article_text: str,
                    post_text: str,
                    mode: str = "sentence",      # "sentence" | "substr" | "hybrid"
                    min_chars: int = 20,
                    min_tokens: int = 5,
                    almost_tol: float = 0.98) -> float:
    """
    복제율 = (일치(또는 거의-일치) 문장 수) / (원문 유효 문장 수)
    반환값은 소수점 둘째자리까지 반올림 (0.00 ~ 1.00)
    - mode="sentence": 문장→문장 집합 매칭 + 거의-일치 보강
    - mode="substr": 원문 문장 ∈ 게시글 본문 서브스트링
    - mode="hybrid": sentence 우선, 실패분만 substr로 재확인
    """
    # 1) 문장 분리 + 정규화
    A = [_normalize_for_exact(x) for x in _split_sentences(article_text)]
    A = [x for x in A if _is_valid_sentence(x, min_chars, min_tokens)]
    if not A:
        return 0.0

    P_sent = [_normalize_for_exact(x) for x in _split_sentences(post_text)]
    P_set = set(P_sent)
    P_all = _normalize_for_exact(post_text)

    copied = 0

    if mode in ("sentence", "hybrid"):
        # 1차: 완전 일치
        unmatched = []
        for s in A:
            if s in P_set:
                copied += 1
            else:
                unmatched.append(s)

        # 2차: 거의-일치(미세 구두점/공백 차이 허용)
        if unmatched:
            for s in list(unmatched):
                candidates = [t for t in P_sent if abs(len(t) - len(s)) / max(1, len(s)) < 0.2]
                if any(_almost_equal(s, t, tol=almost_tol) for t in candidates):
                    copied += 1
                    unmatched.remove(s)

        # hybrid 모드면 남은 unmatched를 substr로 확인
        if mode == "hybrid" and unmatched:
            for s in unmatched:
                if s and s in P_all:
                    copied += 1

    elif mode == "substr":
        for s in A:
            if s and s in P_all:
                copied += 1

    total = len(A)
    if total == 0:
        return 0.0
    return round(copied / total, 2)   # ✅ 소수점 둘째자리까지 반올림


# core_utils.py

import re
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

    base_path = "../../oid 리스트"  # 폴더 경로에 맞게 수정
    news_oids = load_oid_from_excel(os.path.join(base_path, "네이버뉴스 신탁언론 oid.xlsx"))
    sports_oids = load_oid_from_excel(os.path.join(base_path, "네이버스포츠 신탁언론 oid.xlsx"))
    entertain_oids = load_oid_from_excel(os.path.join(base_path, "네이버엔터 신탁언론 oid.xlsx"))

    return news_oids, sports_oids, entertain_oids

trusted_news_oids, trusted_sports_oids, trusted_entertain_oids = load_trusted_oids()


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
                "imbc.com": "div.news_txt[itemprop='articleBody']",
                "ytn.co.kr": "div#CmAdContent",
                "mt.co.kr": "div#textBody[itemprop='articleBody']",
                "heraldcorp.com": "article.article-body#articleText",
                "hankookilbo.com": "div.col-main[itemprop='articleBody']",
                "edaily.co.kr": "div.news_body[itemprop='articleBody']",
                "fnnews.com": "div#article_content",
                "seoul.co.kr": "div#articleContent .viewContent",
                "pressian.com": "div.article_body",
                "kbs.co.kr": "div#cont_newstext",
                "hani.co.kr": "div.article-text",
                "nocutnews.co.kr": "div#pnlContent",
                "asiae.co.kr": "div.article.fb-quotable#txt_area",
                "mediatoday.co.kr": "article#article-view-content-div",
                "khan.co.kr": "div#articleBody",
                "sedaily.com": "div.article_view[itemprop='articleBody']",
                "imaeil.com": "div#articlebody[itemprop='articleBody']",
                "ebn.co.kr": "article#article-view-content-div",
                "kyeongin.com": "div#article-body",
                "obsnews.co.kr": "article#article-view-content-div",
                "incheonilbo.com": "article#article-view-content-div",

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

def generate_search_queries(title, first, second, last, press):
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
        keywords + " " + press,
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

                seen_links.add(link)
                body, _ = get_news_article_body(link, driver, index=index)
                if body and len(body) > 300:
                    cleaned_body = clean_text(body)
                    results.append({"title": title, "link": link, "body": cleaned_body})

        except Exception as e:
            log(f"❌ API 검색 오류: {e}", index)
            continue

    return results


# -*- coding: utf-8 -*-
import time, re, requests, pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BLOG_ID   = "kity4099"
MAX_PAGES = 10          # 가져올 목록 페이지 수
PAUSE_SEC = 0.6
HEADLESS  = True

REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://blog.naver.com/",
}

# ---------------------- Selenium helpers ----------------------
def setup_driver(headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,2200")
    options.add_argument("--lang=ko-KR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={REQ_HEADERS['User-Agent']}")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def switch_to_mainframe(driver):
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 6).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame"))
        )
        return True
    except Exception:
        return False

def open_list_and_set_30rows(driver):
    wait = WebDriverWait(driver, 8)
    # 목록열기
    for by, sel in [
        (By.ID, "toplistSpanBlind"),
        (By.CSS_SELECTOR, "#toplistSpanBlind"),
        (By.XPATH, "//span[@id='toplistSpanBlind' or contains(.,'목록열기')]"),
    ]:
        try:
            el = wait.until(EC.element_to_be_clickable((by, sel)))
            driver.execute_script("arguments[0].click();", el)
            break
        except Exception:
            pass
    # 30줄 보기
    try:
        toggle = wait.until(EC.element_to_be_clickable((By.ID, "listCountToggle")))
        driver.execute_script("arguments[0].click();", toggle)
        opt = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//div[contains(@class,'_changeListCount')]//a[@data-value='30']")
        ))
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(0.8)
    except Exception:
        pass

def wait_for_list(driver, timeout=8):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "tbody > tr"))
    )

def get_first_title(driver):
    try:
        return driver.find_element(By.CSS_SELECTOR, "tbody > tr td.title span.ell2 a").text.strip()
    except Exception:
        return ""

def get_active_page(driver):
    try:
        strong = driver.find_element(By.CSS_SELECTOR, "div.blog2_paginate > strong.page")
        classes = strong.get_attribute("class") or ""
        m = re.search(r"_param\((\d+)\)", classes)
        if m:
            return int(m.group(1))
        t = strong.text.strip()
        m2 = re.search(r"\d+", t)
        return int(m2.group()) if m2 else 1
    except Exception:
        return 1

def click_page_number(driver, n, timeout=10):
    wait = WebDriverWait(driver, timeout)
    old_first = get_first_title(driver)
    try:
        btn = wait.until(EC.element_to_be_clickable((
            By.XPATH, f"//div[contains(@class,'blog2_paginate')]//a[contains(@class,'page') and contains(@class,'_param({n})')]"
        )))
        driver.execute_script("arguments[0].click();", btn)
        WebDriverWait(driver, timeout).until(
            lambda d: get_active_page(d) == n or get_first_title(d) != old_first
        )
        wait_for_list(driver, 6)
        return True
    except Exception:
        return False

def click_next_block(driver, timeout=10):
    wait = WebDriverWait(driver, timeout)
    old_first = get_first_title(driver)
    try:
        nxt = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.blog2_paginate a.next")))
        alt = nxt.get_attribute("alt")  # '11','21',...
        driver.execute_script("arguments[0].click();", nxt)
        if alt and alt.isdigit():
            tgt = int(alt)
            WebDriverWait(driver, timeout).until(
                lambda d: (get_active_page(d) or 0) >= tgt or get_first_title(d) != old_first
            )
        else:
            WebDriverWait(driver, timeout).until(lambda d: get_first_title(d) != old_first)
        wait_for_list(driver, 6)
        return True
    except Exception:
        return False

# ---------------------- Parsing helpers ----------------------
def parse_list_rows(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, "tbody > tr")
    items = []
    for r in rows:
        try:
            a = r.find_element(By.CSS_SELECTOR, "td.title span.ell2 a")
            href = a.get_attribute("href") or ""
            title = a.text.strip()
            date_el = r.find_element(By.CSS_SELECTOR, "td.date span.date")
            date_text = date_el.text.strip() if date_el else ""
            url = href if href.startswith("http") else urljoin("https://blog.naver.com", href)
            items.append({"제목(목록)": title, "URL": url, "등록시간(목록)": date_text})
        except Exception:
            continue
    return items

def robust_get_html(url: str):
    try:
        resp = requests.get(url, headers=REQ_HEADERS, timeout=15)
        if resp.ok:
            return resp.text
    except Exception:
        pass
    return None

def extract_detail(html: str, url: str):
    soup = BeautifulSoup(html, "lxml")
    # 제목
    title = None
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = og["content"].strip()
    if not title:
        h = soup.select_one("h1, h2, h3, .se_textarea")
        if h:
            title = h.get_text(strip=True)
    # 등록시간
    publish = None
    for name, attrs in [
        ("span", {"class": "se_publishDate"}),
        ("span", {"class": "se_publish_date"}),
        ("span", {"class": "date"}),
        ("time", {}),
    ]:
        el = soup.find(name, attrs=attrs)
        if el and el.get_text(strip=True):
            publish = el.get_text(strip=True)
            break
    # 본문
    content = soup.select_one("div.se-main-container") or soup.select_one("#postViewArea") or soup.select_one("article")
    text = ""
    if content:
        for bad in content(["script", "style"]):
            bad.decompose()
        text = content.get_text(separator="\n", strip=True)

    return {
        "게시물 제목": title or "제목 없음",
        "게시물 내용": text or "",
        "등록시간": publish or "",
        "URL": url,
    }

def scrape_detail_with_selenium(driver, url: str):
    driver.get(url)
    switch_to_mainframe(driver)
    time.sleep(0.7)
    return extract_detail(driver.page_source, url)

def normalize_postview(url: str) -> str:
    try:
        p = urlparse(url); qs = parse_qs(p.query)
        if p.path.endswith("PostView.naver") and "blogId" in qs and "logNo" in qs:
            return f"https://blog.naver.com/PostView.naver?blogId={qs['blogId'][0]}&logNo={qs['logNo'][0]}"
    except Exception:
        pass
    return url

# ---------------------- Main crawl ----------------------
def crawl_blog_by_click(blog_id: str, max_pages: int):
    driver = setup_driver(HEADLESS)
    results = []
    try:
        driver.get(f"https://blog.naver.com/{blog_id}")
        switch_to_mainframe(driver)
        open_list_and_set_30rows(driver)
        wait_for_list(driver)

        pages_done = 0
        while pages_done < max_pages:
            items = parse_list_rows(driver)
            if not items:
                break

            for it in items:
                post_url = normalize_postview(it["URL"])
                html = robust_get_html(post_url)
                detail = extract_detail(html, post_url) if html else scrape_detail_with_selenium(driver, post_url)

                # 상세에 등록시간 없으면 목록의 날짜로 보강
                if not detail.get("등록시간") and it.get("등록시간(목록)"):
                    detail["등록시간"] = it["등록시간(목록)"]

                # 상세 제목 비면 목록 제목으로 보강
                if (not detail.get("게시물 제목") or detail["게시물 제목"] == "제목 없음") and it.get("제목(목록)"):
                    detail["게시물 제목"] = it["제목(목록)"]

                results.append(detail)
                time.sleep(PAUSE_SEC)

            pages_done += 1
            cur = get_active_page(driver) or 1
            if not click_page_number(driver, cur + 1):
                if not click_next_block(driver):
                    break
            time.sleep(0.5)
    finally:
        driver.quit()
    return results

if __name__ == "__main__":
    data = crawl_blog_by_click(BLOG_ID, MAX_PAGES)
    df = pd.DataFrame(data)

    # URL 기준 중복 제거
    if "URL" in df.columns:
        df = df.drop_duplicates(subset=["URL"])

    # 요청 컬럼명으로 정리 (게시물url 포함)
    df_out = df.rename(columns={"URL": "게시물url"})[["게시물 제목", "게시물 내용", "등록시간", "게시물url"]]

    # 엑셀 저장 (.xlsx)
    out_name = f"naver_blog_{BLOG_ID}.xlsx"
    df_out.to_excel(out_name, index=False)  # openpyxl 필요
    print(f"총 {len(df_out)}건 저장 → {out_name}")

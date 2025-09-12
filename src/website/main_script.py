# main_script.py
import os
import re
import time
import pandas as pd
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from dotenv import load_dotenv

from src.core_utils import (
    clean_text,
    exact_copy_rate,
    create_driver,
    kill_driver,
    log,
    extract_first_sentences,
    generate_search_queries,
    search_news_with_api,
)

today = datetime.now().strftime("%y%m%d")
input_path = f"../../전처리/디시인사이드_전처리_250911.xlsx"
output_path = f"../../결과/디시인사이드 테스트_9월_{today}.csv"
os.makedirs(f"../../결과/기사본문_{today}", exist_ok=True)

def find_original_article_multiprocess(index, row_dict, total_count):
    from dotenv import load_dotenv
    # api 키 설정
    load_dotenv(dotenv_path="../../.gitignore/.env")

    # 키 읽기
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    driver = create_driver(index)
    if index == 0:
        time.sleep(10)  # 첫 태스크만 잠시 대기
    if driver is None:
        log("❌ 드라이버 생성 실패 → 스킵", index)
        return index, "", 0.0

    driver_quit_needed = True

    try:
        title = clean_text(str(row_dict["게시물 제목"]))
        content = clean_text(str(row_dict["게시물 내용"]))

        first, second, last = extract_first_sentences(content)
        queries = generate_search_queries(title, first, second, last)
        log(f"🔍 검색어: {queries}", index)

        search_results = search_news_with_api(queries, driver, client_id, client_secret, index=index)
        if not search_results:
            log("❌ 관련 뉴스 없음", index)
            return index, "", 0.0

        # ✅ 기존 calculate_copy_ratio → exact_copy_rate 로 교체
        best = max(
            search_results,
            key=lambda x: exact_copy_rate(x["body"], title + " " + content, mode="sentence", min_chars=20, min_tokens=5)
        )
        score = exact_copy_rate(
            best["body"],
            f"{title} {content}",
            mode="hybrid",  # 문장 일치 + 거의-일치 + substr 보정
            min_chars=20,
            min_tokens=5,
            almost_tol=0.98
        )

        if score > 0.0:
            safe_title = re.sub(r'[/*?:<>|]', '', title)[:50]  # 전역 import re 활용
            filename = f"../../결과/기사본문_{today}/{index + 1:03d}_{safe_title}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"[URL] {best['link']}\n\n{best['body']}")
            log(f"📝 저장 완료 → {filename} (복제율: {score})", index)

            hyperlink = f'=HYPERLINK("{best["link"]}")'
            return index, hyperlink, score
        else:
            log(f"⚠️ 복제율 낮음 (복제율: {score})", index)
            return index, "", 0.0

    except Exception as e:
        log(f"❌ 에러 발생: {e}", index)
        return index, "", 0.0
    finally:
        if driver_quit_needed:
            kill_driver(driver, index)

if __name__ == "__main__":
    df = pd.read_excel(input_path, dtype={"게시글 등록일자": str})
    total = len(df)
    log(f"📄 전체 게시글 수: {total}개")
    if "게시물 URL" in df.columns:
        df["게시물 URL"] = df["게시물 URL"].apply(
            lambda x: f'=HYPERLINK("{x}")' if pd.notna(x) and not str(x).startswith("=HYPERLINK") else x
        )
    df["원본기사"] = ""
    df["복사율"] = 0.0
    total = len(df)
    start_index = 0
    tasks = [(start_index+ i, row.to_dict(), total) for i, row in df.iterrows()]

    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(find_original_article_multiprocess, *args) for args in tasks]
        for future in as_completed(futures):
            try:
                index, link, score = future.result()
                df.at[index, "원본기사"] = link
                df.at[index, "복사율"] = score
            except Exception as e:
                log(f"❌ 결과 처리 오류: {e}")

    # 매칭 통계 계산
    matched_count = df["복사율"].gt(0).sum()  # 복사율 > 0
    above_90_count = df["복사율"].ge(0.9).sum()  # 복사율 ≥ 0.9
    above_50_count = df["복사율"].ge(0.5).sum() - above_90_count  # 0.3 이상 중 0.8 미만

    # 통계 행 구성
    stats_rows = pd.DataFrame([
        {"검색어": "매칭건수", "플랫폼": f"{matched_count}건"},
        {"검색어": "0.5 이상", "플랫폼": f"{above_50_count}건"},
        {"검색어": "0.9 이상", "플랫폼": f"{above_90_count}건"},
    ])

    # 기존 df에 행 추가
    df = pd.concat([df, stats_rows], ignore_index=True)

    # 저장
    df.to_csv(output_path, index=False)
    log("📊 통계 요약")
    log(f" 매칭건수: {matched_count}건")
    log(f" 0.5 이상: {above_50_count}건")
    log(f" 0.9 이상: {above_90_count}건")
    log(f"🎉 완료! 저장됨 → {output_path}")

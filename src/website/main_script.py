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
    calculate_sequence_matcher_ratio,
    calculate_copy_ratio,
    create_driver,
    kill_driver,
    log,
    extract_first_sentences,
    generate_search_queries,
    search_news_with_api,
)

today = datetime.now().strftime("%y%m%d")
input_path = f"../../전처리/네이트판_전처리_251229.xlsx"
output_path = f"../../결과/네이트판_12월 4주차_{today}.csv"
os.makedirs(f"../../결과/기사본문_{today}", exist_ok=True)

# 게시글 제목+내용을 기반으로 뉴스 검색 및 복제율 평가 → 기사 본문 저장
def find_original_article_multiprocess(index, row_dict, total_count):
    from dotenv import load_dotenv

    # API 키 로드
    load_dotenv(dotenv_path="../../.gitignore/.env")
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    driver = create_driver(index)
    if index == 0:
        time.sleep(10)
    if driver is None:
        log("❌ 드라이버 생성 실패 → 스킵", index)
        return index, "", 0.0, 0.0

    try:
        title = clean_text(str(row_dict["게시물 제목"]))
        content = clean_text(str(row_dict["게시물 내용"]))
        merged_post = f"{title} {content}"

        # 검색어 생성
        first, second, last = extract_first_sentences(content)
        queries = generate_search_queries(title, first, second, last)
        log(f"🔍 검색어: {queries}", index)

        # 기사 후보 검색
        search_results = search_news_with_api(queries, driver, client_id, client_secret, index=index)
        if not search_results:
            log("❌ 관련 뉴스 없음", index)
            return index, "", 0.0, 0.0

        # -----------------------------------------------------------
        # 1) TF-IDF 기준으로 best 기사 선택하도록 명확히 변경
        # -----------------------------------------------------------
        best = max(
            search_results,
            key=lambda x: calculate_copy_ratio(x["body"], merged_post)
        )

        # -----------------------------------------------------------
        # 2) TF-IDF 복제율 계산
        # -----------------------------------------------------------
        tfidf_score = calculate_copy_ratio(best["body"], merged_post)

        # -----------------------------------------------------------
        # 3) 문장완전일치 복제율 계산 (exact_copy_rate)
        # -----------------------------------------------------------
        exact_score = exact_copy_rate(
            best["body"],
            merged_post,
            mode="hybrid",
            min_chars=20,
            min_tokens=5,
            almost_tol=0.98
        )

        sequence_score = calculate_sequence_matcher_ratio(best["body"], merged_post)

        if tfidf_score > 0.0 or exact_score > 0.0:
            safe_title = re.sub(r'[/*?:<>|]', '', title)[:50]
            filename = f"../../결과/기사본문_{today}/{index + 1:03d}_{safe_title}.txt"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"[URL] {best['link']}\n\n{best['body']}")

            log(
                f"📝 저장 완료 → {filename} (TF-IDF: {tfidf_score}, 문장완전일치: {exact_score})",
                index
            )

            hyperlink = f'=HYPERLINK("{best["link"]}")'
            return index, hyperlink, tfidf_score, exact_score, sequence_score

        else:
            log(f"⚠️ 복제율 낮음 (TF-IDF: {tfidf_score}, 문장완전일치: {exact_score})", index)
            return index, "", tfidf_score, exact_score

    except Exception as e:
        log(f"❌ 에러 발생: {e}", index)
        return index, "", 0.0, 0.0

    finally:
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
    df["TF-IDF"] = 0.0
    df["Sequence"] = 0.0
    df["문장완전일치"] = 0.0

    total = len(df)
    start_index = 0
    tasks = [(start_index+ i, row.to_dict(), total) for i, row in df.iterrows()]

    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(find_original_article_multiprocess, *args) for args in tasks]
        for future in as_completed(futures):
            try:
                index, link, tfidf_score, sequence_score, exact_score = future.result()
                df.at[index, "원본기사"] = link
                df.at[index, "TF-IDF"] = tfidf_score
                df.at[index, "Sequence"] = sequence_score
                df.at[index, "문장완전일치"] = exact_score


            except Exception as e:
                log(f"❌ 결과 처리 오류: {e}")

    # 매칭 통계 계산
    matched_count = df["TF-IDF"].gt(0).sum()  # 복사율 > 0
    above_90_count = df["TF-IDF"].ge(0.9).sum()  # 복사율 ≥ 0.9
    above_50_count = df["TF-IDF"].ge(0.5).sum() - above_90_count  # 0.3 이상 중 0.8 미만

    # 통계 행 구성
    stats_rows = pd.DataFrame([
        {"검색어": "매칭건수", "플랫폼": f"{matched_count}건"},
        {"검색어": "0.5 이상", "플랫폼": f"{above_50_count}건"},
        {"검색어": "0.9 이상", "플랫폼": f"{above_90_count}건"},
    ])

    # 기존 df에 행 추가
    df = pd.concat([df, stats_rows], ignore_index=True)

    df.to_csv(output_path, index=False)
    log("📊 통계 요약")
    log(f" 매칭건수: {matched_count}건")
    log(f" 0.5 이상: {above_50_count}건")
    log(f" 0.9 이상: {above_90_count}건")
    log(f"🎉 완료! 저장됨 → {output_path}")

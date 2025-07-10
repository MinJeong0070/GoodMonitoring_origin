# main_script.py

import os
import re
import time
import pandas as pd
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from dotenv import load_dotenv

from src.core_utils import (
    create_driver, kill_driver, clean_text,
    extract_first_sentences, generate_search_queries,
    calculate_copy_ratio, log, search_news_with_api, similar_sentence
)

today = datetime.now().strftime("%y%m%d")
input_path = f"../../전처리/6월/뽐뿌_전처리_250704.xlsx"
output_path = f"../../결과/뽐뿌_원문기사_6월_{today}.csv"
os.makedirs(f"../../결과/기사본문_{today}", exist_ok=True)

def find_original_article_multiprocess(index, row_dict, total_count):
    # api 키 설정
    load_dotenv(dotenv_path="../../.gitignore/네이버API키_2.env")

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
        press = clean_text(str(row_dict["검색어"]))
        # #티스토리
        # title = clean_text(str(row_dict["게시글 제목"]))
        # content = clean_text(str(row_dict["게시글내용"]))
        # press = clean_text(str(row_dict["검색어"]))

        first, second, last = extract_first_sentences(content)
        queries = generate_search_queries(title, first, second,last, press)
        log(f"🔍 검색어: {queries}", index)

        search_results = search_news_with_api(queries, driver, client_id, client_secret, index=index)
        if not search_results:
            log("❌ 관련 뉴스 없음", index)
            return index, "", 0.0

        best = max(search_results, key=lambda x: calculate_copy_ratio(x["body"], title + " " + content))
        score = calculate_copy_ratio(best["body"], title + " " + content)

        # if not similar_sentence(best["body"], title + " " + content):
        #     log("⚠️ 유사 문장 없음", index)
        #     return index, "", 0.0

        if score >= 0.0:
            filename = f"../../결과/기사본문_{today}/{index+1:03d}_{re.sub(r'[\\/*?:\"<>|]', '', title)[:50]}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"[URL] {best['link']}\n\n{best['body']}")
            log(f"📝 저장 완료 → {filename} (복사율: {score})", index)

            # ⬇ 엑셀에 하이퍼링크 포맷으로 저장
            hyperlink = f'=HYPERLINK("{best["link"]}")'
            return index, hyperlink, score
        else:
            log(f"⚠️ 복사율 낮음 (복사율: {score})", index)
            return index, "", 0.0  # 복사율 낮으면 아무것도 저장 안 함

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

    with ProcessPoolExecutor(max_workers=5) as executor:
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
    above_80_count = df["복사율"].ge(0.8).sum()  # 복사율 ≥ 0.8
    above_30_count = df["복사율"].ge(0.3).sum() - above_80_count  # 0.3 이상 중 0.8 미만

    # 통계 행 구성
    stats_rows = pd.DataFrame([
        {"검색어": "매칭건수", "플랫폼": f"{matched_count}건"},
        {"검색어": "0.3 이상", "플랫폼": f"{above_30_count}건"},
        {"검색어": "0.8 이상", "플랫폼": f"{above_80_count}건"},
    ])

    # 기존 df에 행 추가
    df = pd.concat([df, stats_rows], ignore_index=True)

    # 저장
    df.to_csv(output_path, index=False)
    log("📊 통계 요약")
    log(f" 매칭건수: {matched_count}건")
    log(f" 0.3 이상: {above_30_count}건")
    log(f" 0.8 이상: {above_80_count}건")
    log(f"🎉 완료! 저장됨 → {output_path}")

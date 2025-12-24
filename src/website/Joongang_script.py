# Joongang_script.py
"""
특정 기사 1개(예: 중앙일보 기사)와
각 게시물(제목+내용) 간의 유사도(TF-IDF / SequenceMatcher / 문장완전일치)를
직접 계산하는 전용 스크립트.

전제:
- src.core_utils 에 다음 함수들이 이미 구현되어 있음:
  clean_text, exact_copy_rate, calculate_copy_ratio,
  create_driver, kill_driver, log,
  get_news_article_body
- 입력 파일: 게시물 제목/내용이 들어 있는 엑셀/CSV
    * 필수 컬럼: "게시물 제목", "게시물 내용"
"""

import os
import re
from datetime import datetime

import pandas as pd
from difflib import SequenceMatcher

from src.core_utils import (
    clean_text,
    exact_copy_rate,
    calculate_copy_ratio,
    create_driver,
    kill_driver,
    log,
    get_news_article_body,
)

# ✅ 유사도 계산 대상 기사 URL (필요시 이 값만 바꿔서 사용)
TARGET_ARTICLE_URL = "https://www.joongang.co.kr/article/25328097"



# ============================================================
# 1. SequenceMatcher 기반 복제율 계산
# ============================================================
def calculate_sequence_matcher_ratio(article: str, post: str) -> float:
    """
    SequenceMatcher 기반 단방향 복제율:
      - article(원문)의 글자 중 post(게시글)에 포함되는 비율 계산
      - 글자 단위 비교이므로 띄어쓰기/순서 일치에 민감
    """
    def _clean(t: str) -> str:
        t = "" if t is None else str(t)
        t = re.sub(r"[^\w\s]", "", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    article_clean = _clean(article)
    post_clean = _clean(post)

    if not article_clean or not post_clean:
        return 0.0

    matcher = SequenceMatcher(None, post_clean, article_clean)
    matched_len = sum(block.size for block in matcher.get_matching_blocks() if block.size > 0)
    ratio = matched_len / len(article_clean)
    return round(ratio, 3)


# ============================================================
# 2. 단일 게시물에 대한 유사도 계산 함수
# ============================================================
def find_article_similarity(index, row_dict, total_count,
                            article_body: str, article_url: str):
    """
    - 게시글 1건(row_dict)에 대해:
      1) 게시물 제목+내용 정제
      2) 주어진 article_body 와 유사도 계산
         - TF-IDF
         - 문장완전일치
         - SequenceMatcher
    """
    try:
        title = clean_text(str(row_dict.get("제목", "")))
        content = clean_text(str(row_dict.get("내용", "")))
        merged_post = f"{title} {content}".strip()

        if not merged_post:
            log(f"[{index+1}/{total_count}] ⚠️ 게시물 내용이 비어 있어 스킵", index)
            return index, "", 0.0, 0.0, 0.0

        if not article_body:
            # 기사 본문을 못 가져온 경우 안전하게 0 처리
            log(f"[{index+1}/{total_count}] ❌ 기사 본문이 비어 있어 유사도 계산 불가", index)
            return index, "", 0.0, 0.0, 0.0

        log(f"[{index+1}/{total_count}] 🔍 유사도 계산 수행", index)

        # 1) TF-IDF 복제율
        tfidf_score = calculate_copy_ratio(article_body, merged_post)

        # 2) 문장완전일치 복제율
        exact_score = exact_copy_rate(
            article_body,
            merged_post,
            mode="hybrid",
            min_chars=20,
            min_tokens=5,
            almost_tol=0.98,
        )

        # 3) SequenceMatcher 복제율
        seq_score = calculate_sequence_matcher_ratio(article_body, merged_post)

        hyperlink = f'=HYPERLINK("{article_url}")'

        return index, hyperlink, tfidf_score, exact_score, seq_score

    except Exception as e:
        log(f"❌ 유사도 계산 중 에러 발생: {e}", index)
        return index, "", 0.0, 0.0, 0.0


# ============================================================
# 3. 메인 실행부
# ============================================================
def main():
    """
    - 입력 엑셀/CSV에서 게시글 읽기
    - TARGET_ARTICLE_URL 기사 본문 1회 수집
    - 각 게시물과 기사 간 유사도 계산 (단일 프로세스 루프)
    - 결과 저장
    """
    # --------------------------------------------
    # 1) 입력/출력 경로 설정 (필요시 수정)
    # --------------------------------------------
    input_path = r"F:\Daum_심장에 좋은 음식 뭐냐고요_ 살부터 빼세요_251205.xlsx" # ← 사용 환경에 맞게 수정
    output_dir = r"C:\Users\USER\Downloads\다음 카페"
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d_%H%M")
    # [수정됨] 확장자를 .csv -> .xlsx 로 변경
    output_path = os.path.join(output_dir, f"단일기사_유사도결과_{today}.xlsx")

    # --------------------------------------------
    # 2) 데이터 불러오기
    # --------------------------------------------
    if input_path.lower().endswith(".csv"):
        df = pd.read_csv(input_path)
    else:
        df = pd.read_excel(input_path)

    total_count = len(df)
    log(f"📄 전체 게시글 수: {total_count}건")

    # --------------------------------------------
    # 3) 대상 기사 본문 1회 수집
    # --------------------------------------------
    log(f"📰 대상 기사 URL: {TARGET_ARTICLE_URL}")
    driver = create_driver(0)
    article_body_raw = ""
    try:
        body, new_driver = get_news_article_body(TARGET_ARTICLE_URL, driver, index=0)
        if new_driver is not None and new_driver is not driver:
            driver = new_driver

        if body:
            article_body_raw = body
            log("✅ 기사 본문 로딩 완료", 0)
        else:
            log("❌ 기사 본문이 비어 있습니다.", 0)
    except Exception as e:
        log(f"❌ 기사 본문 수집 중 에러: {e}", 0)
    finally:
        if driver is not None:
            kill_driver(driver, 0)

    # 정제된 기사 본문
    article_body = clean_text(article_body_raw) if article_body_raw else ""

    if not article_body:
        log("❌ 정제된 기사 본문이 비어 있어, 유사도 계산 없이 종료합니다.", 0)
        return

    # --------------------------------------------
    # 4) 결과 컬럼 초기화
    # --------------------------------------------
    df["원본기사"] = ""
    df["TF-IDF"] = 0.0
    df["문장완전일치"] = 0.0
    df["SequenceMatcher"] = 0.0

    # --------------------------------------------
    # 5) 단일 프로세스 루프로 유사도 계산
    # --------------------------------------------
    for idx, row in df.iterrows():
        index, link, tfidf_score, exact_score, seq_score = find_article_similarity(
            idx,
            row.to_dict(),
            total_count,
            article_body,
            TARGET_ARTICLE_URL,
        )
        df.at[index, "원본기사"] = link
        df.at[index, "TF-IDF"] = tfidf_score
        df.at[index, "문장완전일치"] = exact_score
        df.at[index, "SequenceMatcher"] = seq_score

    # --------------------------------------------
    # 6) 간단 통계 및 저장
    # --------------------------------------------
    matched_count = df["TF-IDF"].gt(0).sum()
    above_50_count = df["TF-IDF"].ge(0.5).sum()
    above_90_count = df["TF-IDF"].ge(0.9).sum()

    log("📊 통계 요약")
    log(f" TF-IDF>0 인 게시물 수: {matched_count}건")
    log(f" TF-IDF≥0.5 인 게시물 수: {above_50_count}건")
    log(f" TF-IDF≥0.9 인 게시물 수: {above_90_count}건")

    # [수정됨] to_csv 대신 to_excel 사용
    df.to_excel(output_path, index=False)
    log(f"🎉 완료! 저장됨 → {output_path}")


if __name__ == "__main__":
    main()
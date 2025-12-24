import pandas as pd
import glob
import os

# 최종 결과에 포함할 11개 컬럼
FINAL_COLUMNS = [
    "검색어", "플랫폼", "게시물 URL", "게시물 제목",
    "게시물 내용", "게시물 등록일자", "계정명",
    "원본기사", "TF-IDF", "Sequence", "문장완전일치",
]


def load_csv(file_path: str) -> pd.DataFrame:
    """CSV를 UTF-8 우선, 실패 시 CP949로 읽기"""
    try:
        return pd.read_csv(file_path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding="cp949", low_memory=False)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    각 파일의 컬럼을 FINAL_COLUMNS 형태로 맞춰준다.
    없으면 NaN으로 컬럼을 생성하고, 컬럼 순서를 통일한다.
    """
    # 필수 점수 컬럼이 없으면 생성 (NaN)
    for col in ["TF-IDF", "Sequence", "문장완전일치"]:
        if col not in df.columns:
            df[col] = pd.NA

    # 최종 컬럼 순서에 맞춰 재정렬 (없으면 NaN으로 생성)
    df = df.reindex(columns=FINAL_COLUMNS)
    return df


def merge_csv(input_folder: str, output_file: str) -> None:
    # 1) 폴더 내 CSV 파일 리스트
    all_files = glob.glob(os.path.join(input_folder, "*.csv"))
    if not all_files:
        print("❌ 병합할 CSV 파일이 없습니다.")
        return

    merged_df_list = []

    # 2) 각 파일 읽어서 컬럼 통일
    for file in all_files:
        df = load_csv(file)
        before = len(df)

        df = normalize_columns(df)
        after = len(df)
        merged_df_list.append(df)

        print(f"📄 {os.path.basename(file)}: 원본 {before}행 → 컬럼 통일 후 {after}행")

    # 3) 전체 병합
    merged_df = pd.concat(merged_df_list, ignore_index=True)
    print(f"📊 병합 직후 전체 행 수: {len(merged_df)}")

    # 4) URL이 비어 있는 행 제거 (NaN 및 공백 문자열)
    merged_df = merged_df[merged_df["게시물 URL"].notna()]
    merged_df = merged_df[merged_df["게시물 URL"].astype(str).str.strip() != ""]
    print(f"🔎 URL 비어있는 행 제거 후 행 수: {len(merged_df)}")

    # 5) TF-IDF, Sequence, 문장완전일치 3개 값이 모두 0인 행 제거
    #    - 문자열 "0", "0.0" 등도 숫자로 변환
    score_cols = ["TF-IDF", "Sequence", "문장완전일치"]

    scores_num = (
        merged_df[score_cols]
        .apply(pd.to_numeric, errors="coerce")   # 숫자로 변환, 실패 시 NaN
        .fillna(0)                               # NaN은 0으로 간주
    )

    all_zero_mask = (scores_num == 0).all(axis=1)
    removed_count = all_zero_mask.sum()

    filtered_df = merged_df[~all_zero_mask]
    print(f"🚫 TF-IDF/Sequence/문장완전일치 모두 0인 행 제거: {removed_count}행")
    print(f"✅ 최종 남은 행 수: {len(filtered_df)}")

    # 6) 엑셀 저장 (FINAL_COLUMNS 11개만)
    filtered_df.to_excel(output_file, index=False, engine="xlsxwriter")
    print(f"✅ 병합 및 저장 완료: {output_file}")


if __name__ == "__main__":
    input_path = "../../결과/12월 3주차"
    output_path = "../../결과/웹사이트_원문기사통계_12월 3주차.xlsx"
    merge_csv(input_path, output_path)

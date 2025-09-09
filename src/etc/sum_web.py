import pandas as pd
import glob
import os

# 유지할 컬럼 정의
FINAL_COLUMNS = [
    "검색어", "플랫폼", "게시물 URL", "게시물 제목",
    "게시물 내용", "게시물 등록일자", "계정명", "원본기사", "복사율"
]

# CSV 병합 예시
def merge_csv(input_folder, output_file):
    all_files = glob.glob(os.path.join(input_folder, "*.csv"))
    merged_df_list = []

    for file in all_files:
        try:
            df = pd.read_csv(file, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="cp949", low_memory=False)

        # 지정한 컬럼만 강제 추출 (없으면 NaN 생성)
        df = df.reindex(columns=FINAL_COLUMNS)

        merged_df_list.append(df)

    if not merged_df_list:
        print("❌ 병합할 CSV가 없습니다.")
        return

    merged_df = pd.concat(merged_df_list, ignore_index=True)

    # 1단계: NaN 제거
    merged_df = merged_df.dropna(subset=FINAL_COLUMNS)

    # 2단계: 공백만 있는 경우 제거
    merged_df = merged_df[
        merged_df[FINAL_COLUMNS].astype(str).apply(lambda row: all(v.strip() for v in row), axis=1)
    ]

    # 엑셀 저장
    merged_df.to_excel(output_file, index=False, engine="xlsxwriter")
    print(f"✅ 병합 및 저장 완료: {output_file}")


if __name__ == "__main__":
    input_path = "../../결과/8월 원문기사자료"
    output_path = "../../결과/웹사이트_원문기사통계_월.xlsx"
    merge_csv(input_path, output_path)

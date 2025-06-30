import pandas as pd
import glob
import os

folder_path = '결과/4월 블로그 원문기사자료'
files = glob.glob(os.path.join(folder_path, '*.xlsx'))

merged_df = pd.DataFrame()

for file in files:
    try:
        df = pd.read_excel(file, engine='openpyxl')

        # 열 이름 정리
        df.columns = df.columns.str.strip()

        # 제거 대상 열 제거
        for col in ['수집시간', '이미지 유무']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        # 복사율이 숫자인 행만 유지
        df = df[df['복사율'].apply(lambda x: isinstance(x, (int, float)))]

        # 병합
        merged_df = pd.concat([merged_df, df], ignore_index=True)

    except Exception as e:
        print(f"❌ 파일 열기 실패: {file}\n오류: {e}\n")

# 복사율 0 초과 필터링
merged_df = merged_df[merged_df['복사율'] > 0].reset_index(drop=True)

# 전체 통계 계산
match_count = len(merged_df)
low_count = len(merged_df[merged_df['복사율'] < 0.3])
mid_count = len(merged_df[(merged_df['복사율'] >= 0.3) & (merged_df['복사율'] < 0.8)])
high_count = len(merged_df[merged_df['복사율'] >= 0.8])

# 통계 열 추가
merged_df['매칭개수'] = pd.NA
merged_df['0.3미만'] = pd.NA
merged_df['0.3이상 0.8미만'] = pd.NA
merged_df['0.8이상'] = pd.NA

# 첫 번째 행에 통계 수치 삽입
merged_df.loc[0, '매칭개수'] = match_count
merged_df.loc[0, '0.3미만'] = low_count
merged_df.loc[0, '0.3이상 0.8미만'] = mid_count
merged_df.loc[0, '0.8이상'] = high_count

# 저장
merged_df.to_excel('결과/네이버블로그_원문기사통계_4월4월.xlsx', index=False)

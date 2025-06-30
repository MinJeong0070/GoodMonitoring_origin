import pandas as pd
import glob
import os

# CSV 파일들이 들어있는 폴더 경로 (여기만 수정)
csv_folder = '결과/3월 원문기사자료'

# 결과 저장 경로
output_path = '결과/웹사이트_원문기사통계_3월.xlsx'

# CSV 파일 목록 가져오기
files = glob.glob(os.path.join(csv_folder, '*.xlsx'))
merged_df = pd.DataFrame()

# 파일 병합
for file in files:
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()

        # 불필요한 열 제거 (URL 열은 유지)
        for col in ['수집시간', '이미지 유무']:
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        # 복사율 숫자 처리
        df = df[df['복사율'].apply(lambda x: isinstance(x, (int, float)) or str(x).replace('.', '', 1).isdigit())]
        df['복사율'] = df['복사율'].astype(float)

        # 병합
        merged_df = pd.concat([merged_df, df], ignore_index=True)

    except Exception as e:
        print(f"❌ CSV 병합 실패: {file}\n오류: {e}")

# 전체 게시글 수 (필터 전)
total_count = len(merged_df)

# 복사율 > 0 필터링
merged_df = merged_df[merged_df['복사율'] > 0].reset_index(drop=True)

# 복사율 통계 계산
match_count = len(merged_df)
low_count = len(merged_df[merged_df['복사율'] < 0.3])
mid_count = len(merged_df[(merged_df['복사율'] >= 0.3) & (merged_df['복사율'] < 0.8)])
high_count = len(merged_df[merged_df['복사율'] >= 0.8])

# 통계 열 삽입
merged_df.loc[0, '전체개수'] = total_count
merged_df.loc[0, '매칭개수'] = match_count
merged_df.loc[0, '0.3미만'] = low_count
merged_df.loc[0, '0.3이상 0.8미만'] = mid_count
merged_df.loc[0, '0.8이상'] = high_count

# 결과 저장
merged_df.to_excel(output_path, index=False)
print(f"✅ 병합 및 저장 완료: {output_path}")
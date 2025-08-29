import pandas as pd

# 파일 경로 지정
file1_path = "../../배정안_정수연_7월_추가(2).xlsx"
file2_path = "../../excel/(언진) 전처리용 도메인 주소.xlsx"

# 엑셀 파일 불러오기
df1_raw = pd.read_excel(file1_path)
df2 = pd.read_excel(file2_path)

# 첫 번째 행을 열 이름으로 설정
df1_raw.columns = df1_raw.iloc[0]
df1 = df1_raw[1:]

# 도메인 목록 생성 (소문자 처리 및 공백 제거)
domain_list = df2['도메인'].dropna().str.strip().str.lower().tolist()

# 도메인이 포함된 URL만 필터링
filtered_df = df1[df1['원문 기사 URL'].apply(
    lambda url: any(domain in url for domain in domain_list)
)]

# 결과를 엑셀 파일로 저장
filtered_df.to_excel("filtered_result_by_domain_in_url.xlsx", index=False)

import pandas as pd
import os
# 파일 경로 설정
raw_data_file = "../../네이버 블로그_매칭 데이터_5월_중복 게시물 url 제게 후.xlsx"
exclude_accounts_file = "../../excel/제외 대상 리스트.xlsx"
exclude_domains_file = "../../excel/(언진) 수집 제외 도메인 주소_공식 블로그.xlsx"

output_filtered = "최종_필터링_블로그_데이터.xlsx"
output_removed = "삭제된_블로그_데이터.xlsx"

# 데이터 불러오기
raw_data = pd.read_excel(raw_data_file)
exclude_accounts = pd.read_excel(exclude_accounts_file, header=2)
exclude_domains = pd.read_excel(exclude_domains_file)

# 제외 계정명 리스트
excluded_account_names = exclude_accounts["계정명"].dropna().astype(str).unique().tolist()

# 제외 도메인 URL 리스트
excluded_domain_urls = exclude_domains.iloc[:, 0].dropna().astype(str).unique().tolist()

# 삭제 대상 조건 정의
rows_by_account = raw_data[raw_data["계정명"].isin(excluded_account_names)]
rows_by_domain = raw_data[raw_data["게시물 url"].apply(lambda x: any(domain in str(x) for domain in excluded_domain_urls))]

# 삭제 대상 통합 (중복 제거)
removed_rows = pd.concat([rows_by_account, rows_by_domain]).drop_duplicates()

# 필터링된 데이터
filtered_data = raw_data.drop(removed_rows.index)

# 결과 저장
filtered_data.to_excel(output_filtered, index=False)
removed_rows.to_excel(output_removed, index=False)

# 콘솔 출력
print(f"✅ 필터링 완료!")
print(f"❌ 삭제된 행 수: {len(removed_rows)}")
print(f"📁 저장된 파일: {output_filtered}, {output_removed}")

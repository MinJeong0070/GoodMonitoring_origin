import pandas as pd
# 파일 경로 설정
file1_path = "../../네이버 블로그_매칭 데이터_7월_중복 게시물 url 제게 후_new_공개게시글.xlsx"
file2_path = "../../excel/비신탁사_저작권문구+도메인주소.xlsx"
output_path = "../../네이버 블로그_매칭 데이터_7월_중복 게시물 url 제게 후_new_공개게시글_필터링.xlsx"

# 엑셀 파일 읽기
df_articles = pd.read_excel(file1_path)
df_domains = pd.read_excel(file2_path)

df_articles = df_articles[df_articles["원문기사 url"].notna()]
df_articles = df_articles[df_articles["원문기사 url"].astype(str).str.strip() != ""]
# df_articles = df_articles[df_articles["원본기사"].notna()]
# df_articles = df_articles[df_articles["원본기사"].astype(str).str.strip() != ""]
# 도메인 전처리
domain_list = df_domains["도메인"].dropna().astype(str).str.replace(r"[^\w\.-]", "", regex=True).unique()

# 필터링
# mask = df_articles["원본기사"].astype(str).apply(lambda url: any(domain in url for domain in domain_list))
mask = df_articles["원문기사 url"].astype(str).apply(lambda url: any(domain in url for domain in domain_list))
filtered_df = df_articles[~mask].reset_index(drop=True)

# 통계 계산
match_count = len(filtered_df)
low_count = len(filtered_df[(filtered_df['복사율'] >= 0.5) & (filtered_df['복사율'] < 0.9)])
high_count = len(filtered_df[filtered_df['복사율'] >= 0.9])

# 통계 삽입
filtered_df.loc[0, '매칭개수'] = match_count
filtered_df.loc[0, '0.5이상'] = low_count
filtered_df.loc[0, '0.9이상'] = high_count

# ▶ 하이퍼링크로 저장
with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
    filtered_df.to_excel(writer, index=False, sheet_name='결과')
workbook = writer.book
worksheet = writer.sheets['결과']

# 하이퍼링크 포맷
link_format = workbook.add_format({'font_color': 'blue', 'underline': 1})

# 열 인덱스
# url_cols = ["게시물 URL", "원본기사"]
url_cols = ["게시물 URL", "원문기사 url"]
for col in url_cols:
    if col in filtered_df.columns:
        col_idx = filtered_df.columns.get_loc(col)
for row_num, url in enumerate(filtered_df[col], start=1):  # start=1 to skip header
    if isinstance(url, str) and url.startswith("http"):
        worksheet.write_url(row_num, col_idx, url, link_format, string=url)

print(f"✅ 저장 완료 {output_path}")

import os
import re
import pandas as pd
from datetime import datetime

from src.core_utils import clean_text, calculate_copy_ratio, log

# 날짜
today = datetime.now().strftime("%y%m%d")

# 경로 설정
input_path = f"../../전처리/5월/웃긴대학_전처리_5월_250604.xlsx"
article_folder = f"../../결과/5월 원문기사자료/기사본문_웃긴대학5월_250611"
output_path = f"../../결과/원문기사_웃긴대학_{today}.csv"

# 엑셀 로드
# 전처리된 엑셀 파일 불러오기
df = pd.read_excel(input_path, dtype={"게시글 등록일자": str})
log(f"📂 엑셀 로드 완료 → {input_path}")

if "게시물 URL" in df.columns:
# 게시물 URL을 엑셀 하이퍼링크 형식으로 변환
    df["게시물 URL"] = df["게시물 URL"].apply(
        lambda x: f'=HYPERLINK("{x}")' if pd.notna(x) and not str(x).startswith("=HYPERLINK") else x
    )

# 복사율 및 원본기사 열이 없으면 생성
if "원본기사" not in df.columns:
    df["원본기사"] = ""
if "복사율" not in df.columns:
    df["복사율"] = 0.0

# 기사본문 텍스트 파일 목록
if not os.path.exists(article_folder):
    log(f"🚫 기사본문 폴더가 존재하지 않습니다: {article_folder}")
    exit()

# 기사 본문 텍스트 파일 목록 불러오기
files = [f for f in os.listdir(article_folder) if f.endswith(".txt")]
log(f"📰 기사본문 파일 {len(files)}개 확인됨")

# 기사 본문 기반 복사율 계산 수행
for filename in files:
    try:
        index_str = filename.split("_")[0]
        if not index_str.isdigit():
            continue
        index = int(index_str) - 1  # 파일 번호는 1부터 시작, df index는 0부터

        if index >= len(df):
            continue

        title = clean_text(str(df.at[index, "게시물 제목"]))
        content = clean_text(str(df.at[index, "게시물 내용"]))

        filepath = os.path.join(article_folder, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            continue

        url_match = re.search(r'\[URL\]\s*(\S+)', lines[0])
        if not url_match:
            continue

        url = url_match.group(1)
        body = "".join(lines[2:]).strip()
        if not body or len(body) < 100:
            continue

        score = calculate_copy_ratio(body, title + " " + content)
        hyperlink = f'=HYPERLINK("{url}")'

        df.at[index, "원본기사"] = hyperlink
        df.at[index, "복사율"] = round(score, 3)

        log(f"✅ 복구 완료 [{index+1:03d}] → 복사율: {score}")

    except Exception as e:
        log(f"❌ 복구 실패 [{filename}] → {e}")

# 복사율 기준 통계 계산
matched_count = df["복사율"].gt(0).sum()
above_80_count = df["복사율"].ge(0.8).sum()
above_30_count = df[(df["복사율"] >= 0.3) & (df["복사율"] < 0.8)].shape[0]

log("📊 복사율 통계 요약")
log(f" 매칭건수: {matched_count}건")
log(f" 0.3 이상: {above_30_count}건")
log(f" 0.8 이상: {above_80_count}건")

# 통계 행을 데이터프레임 끝에 추가
stats_rows = pd.DataFrame([
    {"검색어": "매칭건수", "플랫폼": f"{matched_count}건"},
    {"검색어": "0.3 이상", "플랫폼": f"{above_30_count}건"},
    {"검색어": "0.8 이상", "플랫폼": f"{above_80_count}건"},
])

# 📈 통계 결과를 원본 데이터프레임에 추가
df = pd.concat([df, stats_rows], ignore_index=True)

# 💾 복사율 계산 결과 저장
df.to_csv(output_path, index=False)
log(f"💾 복구된 엑셀 저장 완료 → {output_path}")

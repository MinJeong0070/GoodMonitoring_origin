import os, re, pandas as pd

# 입력 CSV 경로
INPUT_PATH = r"D:\jupyter\community_site_crawling-main\원문기사\결과\티스토리_12월 3주차_251223.csv"

# 출력 경로: 입력 파일과 같은 폴더에 저장
out_dir = os.path.dirname(INPUT_PATH)
OUTPUT_XLSX = os.path.join(out_dir, "티스토리_원문기사통계_12월 3주차.xlsx")

# 최종 결과에 포함할 11개 컬럼
FINAL_COLUMNS = [
    "검색어", "플랫폼", "게시물 URL", "게시물 제목",
    "게시물 내용", "게시물 등록일자", "계정명",
    "원본기사", "TF-IDF", "Sequence", "문장완전일치",
]

PSEUDO_NULLS = {"", "none", "nan", "null", "-", "_", ".", "na", "n/a", "없음"}


def unwrap_hyperlink(v):
    """엑셀 HYPERLINK 수식에서 실제 URL만 추출"""
    if pd.isna(v):
        return v
    s = str(v).strip()
    m = re.match(r'^\s*=HYPERLINK\(\s*"([^"]+)"', s, flags=re.I)
    return m.group(1) if m else s


def is_nonempty(v):
    """NaN/공백/의미 없는 토큰(PSEUDO_NULLS) 여부"""
    if pd.isna(v):
        return False
    s = str(v).strip()
    return bool(s) and s.lower() not in PSEUDO_NULLS


# --- 파일 읽기 (CSV/XLSX 자동 구분) ---
ext = os.path.splitext(INPUT_PATH)[1].lower()
if ext in [".xlsx", ".xls"]:
    df = pd.read_excel(INPUT_PATH, sheet_name=0)
elif ext == ".csv":
    try:
        df = pd.read_csv(INPUT_PATH, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(INPUT_PATH, encoding="cp949", low_memory=False)
else:
    raise ValueError(f"지원하지 않는 형식: {ext}")

print(f"📄 원본 행 수: {len(df)}")

# HYPERLINK 해제 (있을 경우만)
for col in ["게시물 URL", "원본기사"]:
    if col in df.columns:
        df[col] = df[col].map(unwrap_hyperlink)

# 스키마 맞추기: 필요한 컬럼이 없으면 생성
for c in FINAL_COLUMNS:
    if c not in df.columns:
        df[c] = pd.NA

# 1) URL이 비어 있지 않은 행만 사용 (매칭 건 보존용)
url_mask = df["게시물 URL"].map(is_nonempty)
df = df[url_mask].copy()
print(f"🔎 URL 비어있는 행 제거 후: {len(df)}행")

# 2) TF-IDF / Sequence / 문장완전일치 3개 값이 모두 0인 행 제거
score_cols = ["TF-IDF", "Sequence", "문장완전일치"]

# 숫자로 변환 (문자열 "0", "0.0" 등 포함), 변환 실패는 0으로 처리
scores_num = (
    df[score_cols]
    .apply(pd.to_numeric, errors="coerce")
    .fillna(0)
)

all_zero_mask = (scores_num == 0).all(axis=1)
removed_cnt = all_zero_mask.sum()

filtered = df.loc[~all_zero_mask, FINAL_COLUMNS].copy()

print(f"🚫 TF-IDF/Sequence/문장완전일치 모두 0인 행 제거: {removed_cnt}행")
print(f"✅ 최종 남은 행 수: {len(filtered)}")

# 저장 (엑셀 URL 자동 변환 끔)
os.makedirs(out_dir, exist_ok=True)
with pd.ExcelWriter(
    OUTPUT_XLSX,
    engine="xlsxwriter",
    engine_kwargs={"options": {"strings_to_urls": False}},
) as w:
    filtered.to_excel(w, index=False, sheet_name="final")

print("✅ 저장 완료:", os.path.abspath(OUTPUT_XLSX))

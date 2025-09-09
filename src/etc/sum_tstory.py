import os, re, pandas as pd

INPUT_PATH = r"D:\jupyter\community_site_crawling-main\원문기사\결과\티스토리\티스토리_8월_250905.csv"

# (1) 출력 경로를 '입력 파일과 같은 폴더'로 먼저 확정
out_dir = os.path.dirname(INPUT_PATH)
OUTPUT_XLSX = os.path.join(out_dir, "티스토리_원문기사통계_8월.xlsx")

FINAL_COLUMNS = ["검색어","플랫폼","게시물 URL","게시물 제목",
                 "게시물 내용","게시물 등록일자","계정명","원본기사","복사율"]
PSEUDO_NULLS = {"","none","nan","null","-","_",".","na","n/a","없음"}

def unwrap_hyperlink(v):
    if pd.isna(v): return v
    s = str(v).strip()
    m = re.match(r'^\s*=HYPERLINK\(\s*"([^"]+)"', s, flags=re.I)
    return m.group(1) if m else s

def is_nonempty(v):
    if pd.isna(v): return False
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

# HYPERLINK 해제
for col in ["게시물 URL","원본기사"]:
    if col in df.columns:
        df[col] = df[col].map(unwrap_hyperlink)

# 스키마 맞추기
for c in FINAL_COLUMNS:
    if c not in df.columns:
        df[c] = pd.NA

# 필수 컬럼 채워진 행만 남기기(실무 핵심 4개)
essential = [c for c in ["게시물 URL","게시물 제목","원본기사","복사율"] if c in df.columns]
mask = df[essential].apply(lambda r: all(is_nonempty(r[c]) for c in essential), axis=1)
filtered = df.loc[mask, FINAL_COLUMNS].copy()

# 저장 (엑셀 URL 자동 변환 끔)
os.makedirs(out_dir, exist_ok=True)
with pd.ExcelWriter(OUTPUT_XLSX, engine="xlsxwriter",
                    engine_kwargs={"options":{"strings_to_urls":False}}) as w:
    filtered.to_excel(w, index=False, sheet_name="final")

print("✅ 저장 완료:", os.path.abspath(OUTPUT_XLSX))

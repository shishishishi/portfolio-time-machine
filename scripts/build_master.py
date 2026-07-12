# scripts/build_master.py
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SRC = DATA_DIR / "data_j.xls"
OUT = DATA_DIR / "master.csv"


def main():
    if not SRC.exists():
        raise SystemExit(f"元ファイルが見つかりません: {SRC}")

    df = pd.read_excel(SRC, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    col_code = "コード"
    col_name = "銘柄名"
    col_market = "市場・商品区分"

    for col in (col_code, col_name, col_market):
        if col not in df.columns:
            raise SystemExit(f"想定した列がありません: {col} / 実際の列: {list(df.columns)}")

    out = df[[col_code, col_name, col_market]].copy()
    out.columns = ["code", "name", "market"]
    out["code"] = out["code"].str.strip().str.zfill(4)
    out["name"] = out["name"].str.strip()

    keep = out["market"].str.contains("内国株式|ETF|ETN|REIT|出資証券", na=False)
    out = out[keep].reset_index(drop=True)
    out["label"] = out["code"] + " " + out["name"]

    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"OK: {len(out)}銘柄を書き出しました -> {OUT}")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

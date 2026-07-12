# core/data.py の _fetch_from_yf を、異常値クリーニング版に差し替える
from pathlib import Path
import re

p = Path("core/data.py")
src = p.read_text(encoding="utf-8")

new_func = '''def _fetch_from_yf(code: str) -> pd.DataFrame:
    ticker = f"{code}.T"
    raw = yf.download(ticker, period="max", auto_adjust=False, progress=False)
    if raw.empty:
        return pd.DataFrame()
    df = pd.DataFrame({
        "close": raw["Close"].squeeze(),
        "adj_close": raw["Adj Close"].squeeze(),
    })
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
    df.index.name = "date"
    df = df.reset_index()
    # --- 異常値クリーニング ---
    # 1) 0以下・欠損の価格を除外
    df = df[(df["close"] > 0) & (df["adj_close"] > 0)].dropna()
    # 2) 前日比で極端に飛ぶ点(半減以下 or 2倍超)を異常スパイクとして除外
    for col in ["close", "adj_close"]:
        ratio = df[col] / df[col].shift(1)
        spike = (ratio < 0.5) | (ratio > 2.0)
        df = df[~spike.fillna(False)]
    return df.reset_index(drop=True)
'''

pattern = r"def _fetch_from_yf\(code: str\) -> pd\.DataFrame:.*?return df\.reset_index\(\)\n"
src2 = re.sub(pattern, new_func, src, count=1, flags=re.DOTALL)

if src2 == src:
    print("NG: 置き換え対象が見つかりませんでした")
else:
    p.write_text(src2, encoding="utf-8")
    print("OK: _fetch_from_yf をクリーニング版に差し替えました")

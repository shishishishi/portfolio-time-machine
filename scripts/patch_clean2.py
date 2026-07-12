# core/data.py の _fetch_from_yf を、より堅牢なクリーニング版に再差し替え
from pathlib import Path
import re

p = Path("core/data.py")
src = p.read_text(encoding="utf-8")

new_func = '''def _fetch_from_yf(code: str) -> pd.DataFrame:
    ticker = f"{code}.T"
    # auto_adjust=Trueで分割・配当調整済みの素直な価格を取得
    adj = yf.download(ticker, period="max", auto_adjust=True, progress=False)
    raw = yf.download(ticker, period="max", auto_adjust=False, progress=False)
    if adj.empty or raw.empty:
        return pd.DataFrame()
    df = pd.DataFrame({
        "close": raw["Close"].squeeze(),
        "adj_close": adj["Close"].squeeze(),
    })
    df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
    df.index.name = "date"
    df = df.reset_index()
    # 0以下・欠損を除外
    df = df[(df["close"] > 0) & (df["adj_close"] > 0)].dropna()
    # 前日比のlog変化が極端(約±40%超)な点を異常として除外
    import numpy as np
    for col in ["close", "adj_close"]:
        r = np.log(df[col] / df[col].shift(1))
        df = df[(r.abs() < 0.4) | r.isna()]
    return df.reset_index(drop=True)
'''

pattern = r"def _fetch_from_yf\(code: str\) -> pd\.DataFrame:.*?return df\.reset_index\(drop=True\)\n"
src2 = re.sub(pattern, new_func, src, count=1, flags=re.DOTALL)

if src2 == src:
    print("NG: 置き換え対象が見つかりませんでした")
else:
    p.write_text(src2, encoding="utf-8")
    print("OK: _fetch_from_yf をより堅牢な版に差し替えました")

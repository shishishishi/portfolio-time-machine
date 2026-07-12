# core/data.py に「既知の分割補正」機能を追加する
from pathlib import Path

p = Path("core/data.py")
src = p.read_text(encoding="utf-8")

# 1) 分割補正テーブルと補正関数を、import群の直後に差し込む
inject = '''
# 既知の分割補正リスト(Yahoo Financeが記録漏れしている分割を手で補う)
# {銘柄コード: [(分割適用日, 分割前の株価に掛ける倍率), ...]}
# 例: 1306は2015-01-07に約10分割 -> それ以前の株価を1/10にする
KNOWN_SPLITS = {
    "1306": [("2015-01-07", 0.1)],
}


def _apply_known_splits(code: str, df: pd.DataFrame) -> pd.DataFrame:
    if code not in KNOWN_SPLITS or df.empty:
        return df
    for split_date, factor in KNOWN_SPLITS[code]:
        mask = df["date"] < split_date
        df.loc[mask, "close"] = df.loc[mask, "close"] * factor
        df.loc[mask, "adj_close"] = df.loc[mask, "adj_close"] * factor
    return df

'''

anchor = "DATA_DIR = Path(__file__).resolve().parent.parent / \\"data\\""
src = src.replace(anchor, inject + "\\n" + anchor, 1)

# 2) get_prices の中で、yfから取得した直後に分割補正をかける
old = "    df = _fetch_from_yf(code)\\n    if df.empty:\\n        return df\\n    _save_to_db(code, df)"
new = "    df = _fetch_from_yf(code)\\n    if df.empty:\\n        return df\\n    df = _apply_known_splits(code, df)\\n    _save_to_db(code, df)"
src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
print("OK: 分割補正機能を追加しました")
print("KNOWN_SPLITS に登録:", "1306 -> 2015-01-07 に1/10")

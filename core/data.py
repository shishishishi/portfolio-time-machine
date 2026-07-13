# core/data.py (分割補正つき完成版)
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "prices.db"

# 既知の分割補正リスト(Yahoo Financeが記録漏れしている分割を手で補う)
# {銘柄コード: [(分割適用日, 分割前の株価に掛ける倍率)]}
KNOWN_SPLITS = {
    "1306": [("2015-01-07", 0.1)],
    "2558": [("2026-06-11", 0.1)],
}


def _init_db():
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL,
            adj_close REAL,
            PRIMARY KEY (code, date)
        )
    """)
    con.commit()
    con.close()


def _fetch_from_yf(code: str) -> pd.DataFrame:
    ticker = f"{code}.T"
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
    df = df[(df["close"] > 0) & (df["adj_close"] > 0)].dropna()
    for col in ["close", "adj_close"]:
        r = np.log(df[col] / df[col].shift(1))
        df = df[(r.abs() < 0.4) | r.isna()]
    return df.reset_index(drop=True)


def _apply_splits(code: str, df: pd.DataFrame):
    """
    分割補正を適用し、(補正後df, 適用した分割の記録) を返す。
    手動登録(KNOWN_SPLITS)を優先。無ければ自動検出。
    記録は [{"date":..., "factor":..., "source":"manual"/"auto"}]。
    """
    if df.empty:
        return df, []

    applied = []
    if code in KNOWN_SPLITS:
        # 手動登録を優先(確定した傷)
        for split_date, factor in KNOWN_SPLITS[code]:
            mask = df["date"] < split_date
            df.loc[mask, "close"] = df.loc[mask, "close"] * factor
            df.loc[mask, "adj_close"] = df.loc[mask, "adj_close"] * factor
            applied.append({"date": split_date, "factor": factor, "source": "manual"})
    else:
        # 未登録の銘柄は自動検出
        detected = _detect_splits(df)
        for split_date, factor in detected:
            mask = df["date"] < split_date
            df.loc[mask, "close"] = df.loc[mask, "close"] * factor
            df.loc[mask, "adj_close"] = df.loc[mask, "adj_close"] * factor
            applied.append({"date": split_date, "factor": factor, "source": "auto"})

    return df, applied


def _save_to_db(code: str, df: pd.DataFrame):
    con = sqlite3.connect(DB_PATH)
    rows = [(code, r["date"], r["close"], r["adj_close"]) for _, r in df.iterrows()]
    con.executemany(
        "INSERT OR REPLACE INTO prices (code, date, close, adj_close) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    con.close()


def _load_from_db(code: str) -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, close, adj_close FROM prices WHERE code = ? ORDER BY date",
        con, params=(code,),
    )
    con.close()
    return df


def get_prices(code: str, force_refresh: bool = False) -> pd.DataFrame:
    _init_db()
    if not force_refresh:
        cached = _load_from_db(code)
        if not cached.empty:
            return cached
    df = _fetch_from_yf(code)
    if df.empty:
        return df
    df, applied = _apply_splits(code, df)
    _save_to_db(code, df)
    _SPLIT_INFO_CACHE[code] = applied
    return _load_from_db(code)


def get_listing_date(code: str) -> str | None:
    df = get_prices(code)
    if df.empty:
        return None
    return df["date"].min()

# ============================================================
# 分割の自動検出(SPEC v2.1) — 未登録の分割を見つけて補正する
# 設計思想: 「1日で40%超の急変」かつ「比率が整数分の1にきれい」の
# 両方を満たす日だけを分割と判定。暴落(半端な比率)は素通しする。
# ============================================================

# 分割としてありうる比率の候補(分割: 1/n、併合: n倍)
_SPLIT_RATIOS = [0.5, 1/3, 0.25, 0.2, 0.1, 2.0, 3.0, 4.0, 5.0, 10.0]
_RATIO_TOLERANCE = 0.08  # 候補比率との許容誤差(±8%)


def _match_split_ratio(ratio: float):
    """前日比ratioが分割候補のどれかに近ければ、そのきれいな比率を返す。なければNone。"""
    for cand in _SPLIT_RATIOS:
        if abs(ratio - cand) / cand <= _RATIO_TOLERANCE:
            return cand
    return None


def _detect_splits(df: pd.DataFrame) -> list:
    """
    close列の前日比を全期間スキャンし、分割の疑いが極めて高い日を
    [(日付, factor)] のリストで返す。factorは「分割日より前に掛ける倍率」。
    分割(1/n)ならfactor=1/n、併合(n倍)ならfactor=n。
    """
    if df.empty or len(df) < 2:
        return []
    splits = []
    closes = df["close"].values
    dates = df["date"].values
    for i in range(1, len(closes)):
        prev, cur = closes[i-1], closes[i]
        if prev <= 0 or cur <= 0:
            continue
        ratio = cur / prev
        # 手がかり①: 1日で40%超の急変(下落 or 上昇)
        if 0.6 <= ratio <= 1.67:
            continue  # 急変が小さい → 分割ではない(暴落含め素通し)
        # 手がかり②: 比率が整数分の1にきれいか
        matched = _match_split_ratio(ratio)
        if matched is None:
            continue  # 半端な比率 → 暴落の可能性が高い、補正しない
        # ①②を両方満たす → 分割と判定
        splits.append((dates[i], matched))
    return splits

# 分割補正の記録を保持し、外部(app.py)から参照できるようにする
_SPLIT_INFO_CACHE = {}


def get_split_info(code: str):
    """直近のget_pricesで、その銘柄にどんな分割補正を適用したかを返す。"""
    return _SPLIT_INFO_CACHE.get(code, [])

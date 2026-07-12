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


def _apply_known_splits(code: str, df: pd.DataFrame) -> pd.DataFrame:
    if code not in KNOWN_SPLITS or df.empty:
        return df
    for split_date, factor in KNOWN_SPLITS[code]:
        mask = df["date"] < split_date
        df.loc[mask, "close"] = df.loc[mask, "close"] * factor
        df.loc[mask, "adj_close"] = df.loc[mask, "adj_close"] * factor
    return df


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
    df = _apply_known_splits(code, df)
    _save_to_db(code, df)
    return _load_from_db(code)


def get_listing_date(code: str) -> str | None:
    df = get_prices(code)
    if df.empty:
        return None
    return df["date"].min()

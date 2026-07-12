# 2014年12月前後の1306の生データを覗く
import sqlite3
import pandas as pd

con = sqlite3.connect("data/prices.db")
df = pd.read_sql_query(
    "SELECT date, close, adj_close FROM prices WHERE code = ? AND date BETWEEN ? AND ? ORDER BY date",
    con, params=("1306", "2014-12-01", "2015-01-20"),
)
con.close()

pd.set_option("display.max_rows", None)
print(df.to_string(index=False))
print()
print("close列の前日比:")
df["ratio"] = df["close"] / df["close"].shift(1)
print(df[["date", "close", "ratio"]].to_string(index=False))

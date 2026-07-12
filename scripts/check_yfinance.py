# scripts/check_yfinance.py
# yfinanceで1306の株価が取得できるかの動作確認
import yfinance as yf

code = "1306.T"  # TOPIX連動型ETF(末尾.Tが東証の意味)
print(f"{code} の株価を取得します...")

df = yf.download(code, start="2024-01-01", end="2024-02-01", auto_adjust=False)

if df.empty:
    print("NG: データが取得できませんでした(ネット接続かコードを確認)")
else:
    print(f"OK: {len(df)}日分のデータを取得しました")
    print(df[["Close", "Adj Close"]].head())

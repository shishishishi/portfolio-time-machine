# core/calc.py
# 「銘柄+株数+期間」から評価額の推移と4指標を計算する頭脳

import pandas as pd
from core.data import get_prices, get_listing_date


def _nearest_on_or_after(dates: pd.Series, target: str) -> str | None:
    after = dates[dates >= target]
    return after.min() if not after.empty else None


def _nearest_on_or_before(dates: pd.Series, target: str) -> str | None:
    before = dates[dates <= target]
    return before.max() if not before.empty else None


def check_listing(holdings: dict, start: str) -> list[str]:
    """開始日より後にしかデータがない銘柄をエラーメッセージのリストで返す。空なら問題なし。"""
    errors = []
    for code in holdings:
        first = get_listing_date(code)
        if first is None:
            errors.append(f"{code}: 株価データを取得できませんでした")
        elif first > start:
            errors.append(f"{code}: データ開始が {first} のため、開始日 {start} には購入できません")
    return errors


def simulate(holdings: dict, start: str, end: str) -> dict:
    """
    holdings: {"1306": 500, "6501": 200} のような 銘柄コード:株数 の辞書
    start, end: "YYYY-MM-DD"
    戻り値: 構成比・4指標・推移データをまとめた辞書
    """
    series_list = []
    principals = {}

    for code, shares in holdings.items():
        px = get_prices(code)
        if px.empty:
            continue
        px = px[(px["date"] >= start) & (px["date"] <= end)].copy()
        if px.empty:
            continue

        start_day = _nearest_on_or_after(px["date"], start)
        base_close = px.loc[px["date"] == start_day, "close"].iloc[0]
        base_adj = px.loc[px["date"] == start_day, "adj_close"].iloc[0]

        # 元本 = 株数 × 開始日の終値(配当未調整)
        principals[code] = shares * base_close

        # 評価額推移 = 元本 × (調整済み終値 / 開始日の調整済み終値) → 配当再投資込み
        s = pd.Series(
            (px["adj_close"].values / base_adj) * principals[code],
            index=px["date"].values,
            name=code,
        )
        series_list.append(s)

    if not series_list:
        return {"ok": False, "reason": "有効なデータがありませんでした"}

    # 全銘柄を共通営業日で結合し、欠けはある分で埋めて合計
    matrix = pd.concat(series_list, axis=1).sort_index().ffill()
    portfolio = matrix.sum(axis=1)

    principal_total = sum(principals.values())
    final_value = float(portfolio.iloc[-1])

    # 経過日数からCAGR(年率)
    days = (pd.to_datetime(portfolio.index[-1]) - pd.to_datetime(portfolio.index[0])).days
    years = days / 365.25 if days > 0 else 1
    multiple = final_value / principal_total
    cagr = multiple ** (1 / years) - 1

    # 最大ドローダウン
    running_max = portfolio.cummax()
    drawdown = portfolio / running_max - 1
    max_dd = float(drawdown.min())
    trough_date = drawdown.idxmin()
    peak_date = portfolio[:trough_date].idxmax()

    return {
        "ok": True,
        "principals": principals,          # 銘柄ごとの元本(円グラフ用)
        "principal_total": principal_total,
        "final_value": final_value,
        "multiple": multiple,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "dd_peak": peak_date,
        "dd_trough": trough_date,
        "series_dates": list(portfolio.index),   # 推移チャート用
        "series_values": [float(v) for v in portfolio.values],
    }


if __name__ == "__main__":
    holdings = {"1306": 500}
    start, end = "2015-01-01", "2026-07-07"

    errs = check_listing(holdings, start)
    if errs:
        print("上場日チェックNG:")
        for e in errs:
            print("  -", e)
    else:
        r = simulate(holdings, start, end)
        print(f"=== 1306を500口 / {start}〜{end} ===")
        print(f"投資元本    : {r['principal_total']:,.0f}円")
        print(f"最終評価額  : {r['final_value']:,.0f}円")
        print(f"リターン    : {r['multiple']:.2f}倍 (年率 {r['cagr']*100:+.1f}%)")
        print(f"最大DD      : {r['max_drawdown']*100:.1f}% ({r['dd_peak']}→{r['dd_trough']})")
        print(f"データ点数  : {len(r['series_values'])}日分")

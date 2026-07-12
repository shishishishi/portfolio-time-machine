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

# ============================================================
# モードB: 積立(金額指定 / 株数指定) SPEC v2準拠
# 買い付けリスト方式: 一括もハイブリッドも同じ仕組みで扱える土台
# ============================================================

def _monthly_buy_dates(px_dates, start, end, buy_day):
    """開始〜終了の各月について、指定日(休場日なら直後の営業日)の実営業日リストを返す。"""
    dates = pd.to_datetime(pd.Series(px_dates))
    dates = dates[(dates >= pd.to_datetime(start)) & (dates <= pd.to_datetime(end))]
    if len(dates) == 0:
        return []
    result = []
    cur = pd.to_datetime(start).replace(day=1)
    last = pd.to_datetime(end).replace(day=1)
    while cur <= last:
        try:
            target = cur.replace(day=buy_day)
        except ValueError:
            target = cur + pd.offsets.MonthEnd(0)
        after = dates[dates >= target]
        if len(after) > 0:
            d = after.min()
            if d.month == target.month and d.year == target.year:
                result.append(d.strftime("%Y-%m-%d"))
        cur = cur + pd.offsets.MonthBegin(1)
    return result


def simulate_accumulation(code, start, end, mode, amount_or_shares, buy_day):
    """
    単一銘柄の積立シミュレーション。
    mode: "amount"(金額指定) / "shares"(株数指定)
    amount_or_shares: 金額指定なら毎月の円、株数指定なら毎月の株数
    """
    px = get_prices(code)
    if px.empty:
        return None
    px = px[(px["date"] >= start) & (px["date"] <= end)].copy().reset_index(drop=True)
    if px.empty:
        return None

    buy_dates = _monthly_buy_dates(px["date"], start, end, buy_day)
    if not buy_dates:
        return None

    # 各買い付けを記録
    buys = []
    for d in buy_dates:
        row = px[px["date"] == d]
        if row.empty:
            continue
        close = float(row["close"].iloc[0])
        adj = float(row["adj_close"].iloc[0])
        if mode == "amount":
            shares = amount_or_shares / close   # 金額 ÷ 株価 = 小数株
            paid = float(amount_or_shares)      # 支払いは固定
        else:
            shares = float(amount_or_shares)    # 指定株数
            paid = amount_or_shares * close     # 支払いは変動
        buys.append({"date": d, "shares": shares, "paid": paid, "adj_at_buy": adj})

    if not buys:
        return None

    # 日次評価額: 各買い付け分を「株数 × (今のadj / 買った時のadj)」で成長させ合算
    values = []
    invested = []  # その日までの累計投資額(階段状)
    for _, prow in px.iterrows():
        t = prow["date"]
        adj_t = float(prow["adj_close"])
        v = 0.0
        inv = 0.0
        for b in buys:
            if b["date"] <= t:
                v += b["paid"] * (adj_t / b["adj_at_buy"])
                inv += b["paid"]
        values.append(v)
        invested.append(inv)

    return {
        "buys": buys,
        "dates": list(px["date"].values),
        "values": values,        # 日次の保有評価額
        "invested": invested,    # 日次の累計投資額(階段状ライン用)
    }


if __name__ == "__main__":
    print("=== 積立テスト: 1306 毎月25日 1万円 金額指定 ===")
    r = simulate_accumulation("1306", "2015-01-01", "2026-07-07", "amount", 10000, 25)
    if r is None:
        print("NG: データが取得できませんでした")
    else:
        total_paid = sum(b["paid"] for b in r["buys"])
        total_shares = sum(b["shares"] for b in r["buys"])
        final_value = r["values"][-1]
        print(f"買付回数    : {len(r['buys'])}回")
        print(f"累計投資額  : {total_paid:,.0f}円")
        print(f"累計取得株数: {total_shares:,.2f}株")
        print(f"平均取得単価: {total_paid/total_shares:,.1f}円")
        print(f"最終評価額  : {final_value:,.0f}円")
        print(f"リターン    : {final_value/total_paid:.2f}倍")


# ============================================================
# モードC: ハイブリッド(積立枠 + 成長枠スポット)
# 買い付けリスト方式。既存の simulate_accumulation は無改変のまま、
# 評価を「code 付き buys の合成」に一般化して A/B/C を同一エンジンで扱う。
# 各 buy = {"date","code","shares","paid","adj_at_buy"}
# ============================================================

def _build_dca_buys(code, start, end, mode, val, buy_day):
    """積立枠。既存 _monthly_buy_dates を流用するので旧Bと日付ロジックは同一。"""
    px = get_prices(code)
    if px.empty:
        return []
    px = px[(px["date"] >= start) & (px["date"] <= end)].copy()
    if px.empty:
        return []
    out = []
    for d in _monthly_buy_dates(px["date"], start, end, buy_day):
        row = px[px["date"] == d]
        if row.empty:
            continue
        close = float(row["close"].iloc[0])
        adj = float(row["adj_close"].iloc[0])
        if mode == "amount":
            shares, paid = val / close, float(val)
        else:
            shares, paid = float(val), val * close
        out.append({"date": d, "code": code, "shares": shares, "paid": paid, "adj_at_buy": adj})
    return out


def _build_spot_buys(spot_specs, start, end):
    """成長枠。任意日→直後の営業日へ(_nearest_on_or_after を流用)。
    spot_specs: [{"date","code","mode","val"}, ...]  mode: 'amount'|'shares'"""
    out = []
    for sp in spot_specs:
        code = sp["code"]
        px = get_prices(code)
        if px.empty:
            continue
        px = px[(px["date"] >= start) & (px["date"] <= end)]
        d = _nearest_on_or_after(px["date"], sp["date"])
        if d is None:
            continue
        row = px[px["date"] == d]
        close = float(row["close"].iloc[0])
        adj = float(row["adj_close"].iloc[0])
        if sp["mode"] == "amount":
            shares, paid = sp["val"] / close, float(sp["val"])
        else:
            shares, paid = float(sp["val"]), sp["val"] * close
        out.append({"date": d, "code": code, "shares": shares, "paid": paid, "adj_at_buy": adj})
    return out


def _evaluate_buys(buys, start, end):
    """code 付き buys を評価。評価軸=使う全銘柄の[start,end]営業日の和集合。
    未上場期間の銘柄は寄与ゼロ。単一銘柄なら simulate_accumulation と同一結果になる。"""
    codes = sorted({b["code"] for b in buys})
    adj_series, axis = {}, None
    for c in codes:
        px = get_prices(c)
        px = px[(px["date"] >= start) & (px["date"] <= end)]
        s = pd.Series(px["adj_close"].values, index=px["date"].values).sort_index()
        adj_series[c] = s
        axis = s.index if axis is None else axis.union(s.index)
    axis = axis.sort_values()

    value = pd.Series(0.0, index=axis)
    invested = pd.Series(0.0, index=axis)
    for b in buys:
        s = adj_series[b["code"]].reindex(axis).ffill()
        contrib = b["paid"] * (s / b["adj_at_buy"])
        contrib[axis < b["date"]] = 0.0            # 購入前は保有なし
        value = value.add(contrib, fill_value=0.0)
        invested.loc[axis >= b["date"]] += b["paid"]
    return {"dates": list(axis),
            "values": [float(v) for v in value.values],
            "invested": [float(v) for v in invested.values]}


def cost_by_code(buys):
    """平均取得単価は必ず銘柄ごと(株数は銘柄横断で足せない)。"""
    agg = {}
    for b in buys:
        a = agg.setdefault(b["code"], {"paid": 0.0, "shares": 0.0})
        a["paid"] += b["paid"]
        a["shares"] += b["shares"]
    for a in agg.values():
        a["avg_cost"] = a["paid"] / a["shares"] if a["shares"] else float("nan")
    return agg


def simulate_hybrid(dca_code, start, end, dca_mode, dca_val, buy_day, spot_specs):
    """
    dca_code : 積立枠の銘柄(単一)
    dca_mode : 'amount'|'shares'  / dca_val: 毎月の円 or 株数 / buy_day: 毎月◯日
    spot_specs: [{"date","code","mode","val"}, ...]  成長枠の任意日スポット(複数可)
    戻り値: {dates, values, invested, buys, cost}  ※ app は積立チャートを流用可
    """
    buys = _build_dca_buys(dca_code, start, end, dca_mode, dca_val, buy_day) \
        + _build_spot_buys(spot_specs, start, end)
    if not buys:
        return None
    ev = _evaluate_buys(buys, start, end)
    ev["buys"] = buys
    ev["cost"] = cost_by_code(buys)
    return ev

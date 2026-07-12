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

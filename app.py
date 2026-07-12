# app.py
# ポートフォリオ・タイムマシン (一括 / 積立モード対応)
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.calc import simulate, check_listing, simulate_accumulation
from core.data import get_split_info


def show_split_notice(codes):
    """補正があった銘柄について、画面に明示する"""
    for c in codes:
        info = get_split_info(c)
        for s in info:
            n = round(1 / s["factor"]) if s["factor"] < 1 else s["factor"]
            kind = "自動検出" if s["source"] == "auto" else "登録済み"
            st.info(f"銘柄 {c}: {s['date']} に約1/{n}の分割を補正しました({kind})。分割は資産価値に影響しませんが、表示の正確性のため過去株価を調整しています。")

st.set_page_config(page_title="ポートフォリオ・タイムマシン", layout="wide")

BLUE = "#4169E1"
PINK = "#E73895"
COLORS = [BLUE, "#2E4FB8", PINK, "#B8527A", "#5B8DEF", "#1D9E75",
          "#D85A30", "#7F77DD", "#BA7517", "#639922"]

# --- LINE Seed Bold フォントのみ(背景は暗いテーマのまま) ---
st.markdown("""
<style>
@font-face {
    font-family: "LINE Seed JP";
    src: url("https://vos.line-scdn.net/lineseed-fonts/LINESeedJP_OTF_Bd.woff2") format("woff2");
    font-weight: 700;
    font-display: swap;
}
html, body, [class*="css"], .stMarkdown, .stButton, .stRadio,
.stSelectbox, .stNumberInput, h1, h2, h3, h4, p, div, span, label {
    font-family: "LINE Seed JP", "Hiragino Sans", "Meiryo", sans-serif !important;
    font-weight: 700 !important;
}
h1 { color: #4169E1 !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_master():
    return pd.read_csv("data/master.csv", dtype=str)


master = load_master()
labels = master["label"].tolist()


def name_of(code):
    hit = master.loc[master["code"] == code, "name"]
    return hit.iloc[0] if not hit.empty else code


st.title("ポートフォリオ・タイムマシン")
st.caption("過去に日本株でポートフォリオを組み、そのまま持ち続けたら今いくらか。暴落込みで振り返る。")

mode = st.radio("モード", ["一括投資", "積立投資"], horizontal=True)

left, right = st.columns([1, 2])

if mode == "一括投資":
    with left:
        st.subheader("STEP 1  期間")
        c1, c2 = st.columns(2)
        start = c1.date_input("開始日", value=pd.to_datetime("2015-01-05")).strftime("%Y-%m-%d")
        end = c2.date_input("終了日", value=pd.to_datetime("2026-07-07")).strftime("%Y-%m-%d")
        st.subheader("STEP 2  銘柄と株数")
        n = st.number_input("銘柄数", min_value=1, max_value=10, value=1, step=1)
        holdings = {}
        for i in range(int(n)):
            ca, cb = st.columns([3, 1])
            pick = ca.selectbox(f"銘柄 {i+1}", options=[""] + labels, key=f"s_{i}")
            sh = cb.number_input("株数", min_value=0, value=100, step=100, key=f"sh_{i}")
            if pick and sh > 0:
                code = pick.split(" ")[0]
                holdings[code] = holdings.get(code, 0) + int(sh)
        run = st.button("シミュレーション実行", type="primary", use_container_width=True)

    with right:
        if not run:
            st.info("左で期間と銘柄・株数を入れて実行してください。")
        elif not holdings:
            st.warning("銘柄を1つ以上選び、株数を入力してください。")
        else:
            errs = check_listing(holdings, start)
            if errs:
                st.error("選んだ開始日には購入できない銘柄があります:")
                for e in errs:
                    st.write("・", e)
            else:
                r = simulate(holdings, start, end)
                show_split_notice(list(holdings.keys()))
                if not r["ok"]:
                    st.error(r["reason"])
                else:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("投資元本", f"¥{r['principal_total']:,.0f}")
                    m2.metric("最終評価額", f"¥{r['final_value']:,.0f}")
                    m3.metric("リターン", f"{r['multiple']:.2f}倍", f"年率 {r['cagr']*100:+.1f}%")
                    m4.metric("最大DD", f"{r['max_drawdown']*100:.1f}%")
                    codes = list(r["principals"].keys())
                    if len(codes) >= 2:
                        g1, g2 = st.columns([1, 2])
                        with g1:
                            pie = go.Figure(go.Pie(
                                labels=[f"{c} {name_of(c)}" for c in codes],
                                values=list(r["principals"].values()),
                                marker=dict(colors=COLORS[:len(codes)]),
                                hole=0.35, textinfo="percent", sort=False))
                            pie.update_layout(title=f"開始時の構成比({start}評価)",
                                              margin=dict(t=40, b=40, l=10, r=10), height=380,
                                              legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"))
                            st.plotly_chart(pie, use_container_width=True)
                    else:
                        st.caption("構成比: 1銘柄のみのため省略")
                        g2 = st.container()
                    with g2:
                        line = go.Figure(go.Scatter(
                            x=pd.to_datetime(r["series_dates"]), y=r["series_values"],
                            mode="lines", line=dict(color=BLUE, width=2),
                            fill="tozeroy", fillcolor="rgba(65,105,225,0.08)", name="評価額"))
                        line.add_hline(y=r["principal_total"], line_dash="dot", line_color=PINK,
                                       annotation_text=f"元本 ¥{r['principal_total']:,.0f}")
                        line.update_layout(title="評価額の推移(配当込み)",
                                           margin=dict(t=40, b=0, l=0, r=0), height=380,
                                           yaxis_title=None)
                        st.plotly_chart(line, use_container_width=True)
                    st.caption(f"最大下落は {r['dd_peak']} の高値から {r['dd_trough']} まで。手数料・税・単元制約・為替は未考慮。")

else:
    with left:
        st.subheader("STEP 1  期間")
        c1, c2 = st.columns(2)
        start = c1.date_input("開始日", value=pd.to_datetime("2015-01-01")).strftime("%Y-%m-%d")
        end = c2.date_input("終了日", value=pd.to_datetime("2026-07-07")).strftime("%Y-%m-%d")
        st.subheader("STEP 2  積立の設定")
        acc_style = st.radio("積立方式", ["金額指定(定額)", "株数指定(定量)"])
        if acc_style.startswith("金額"):
            acc_mode = "amount"
            acc_val = st.number_input("毎月の積立額(円)", min_value=1000, value=10000, step=1000)
        else:
            acc_mode = "shares"
            acc_val = st.number_input("毎月の株数", min_value=1, value=10, step=1)
        buy_day = st.number_input("購入日(毎月・休場日は翌営業日)", min_value=1, max_value=28, value=25, step=1)
        st.subheader("STEP 3  銘柄")
        pick = st.selectbox("銘柄(1つ)", options=[""] + labels, key="acc_stock")
        run = st.button("シミュレーション実行", type="primary", use_container_width=True)

    with right:
        if not run:
            st.info("左で期間・積立設定・銘柄を入れて実行してください。")
        elif not pick:
            st.warning("銘柄を選んでください。")
        else:
            code = pick.split(" ")[0]
            errs = check_listing({code: 1}, start)
            if errs:
                st.error("選んだ開始日には購入できません:")
                for e in errs:
                    st.write("・", e)
            else:
                r = simulate_accumulation(code, start, end, acc_mode, acc_val, int(buy_day))
                show_split_notice([code])
                if r is None:
                    st.error("計算できませんでした。期間や銘柄を確認してください。")
                else:
                    total_paid = sum(b["paid"] for b in r["buys"])
                    total_shares = sum(b["shares"] for b in r["buys"])
                    final_v = r["values"][-1]
                    avg_cost = total_paid / total_shares if total_shares else 0
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("累計投資額", f"¥{total_paid:,.0f}")
                    m2.metric("最終評価額", f"¥{final_v:,.0f}")
                    m3.metric("リターン", f"{final_v/total_paid:.2f}倍")
                    m4.metric("平均取得単価", f"¥{avg_cost:,.1f}")
                    st.markdown(f"**{name_of(code)}** に {r['buys'][0]['date']} から毎月積立({len(r['buys'])}回)")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=pd.to_datetime(r["dates"]), y=r["values"],
                        mode="lines", line=dict(color=BLUE, width=2),
                        fill="tozeroy", fillcolor="rgba(65,105,225,0.08)", name="評価額"))
                    fig.add_trace(go.Scatter(
                        x=pd.to_datetime(r["dates"]), y=r["invested"],
                        mode="lines", line=dict(color=PINK, width=2, dash="dot"), name="累計投資額(元本)"))
                    fig.update_layout(title="評価額と累計投資額の推移",
                                      margin=dict(t=40, b=0, l=0, r=0), height=420,
                                      yaxis_title=None,
                                      legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"))
                    st.plotly_chart(fig, use_container_width=True)
                    if acc_mode == "shares":
                        st.caption(f"株数指定のため月々の支払額は変動します。初回 ¥{r['buys'][0]['paid']:,.0f} → 直近 ¥{r['buys'][-1]['paid']:,.0f}。手数料・税・為替は未考慮。")
                    else:
                        st.caption("金額指定のため毎月一定額を投資。株価が高い月は少なく、安い月は多く買えます。手数料・税・為替は未考慮。")

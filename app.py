# app.py
# ポートフォリオ・タイムマシン UI (Streamlit)
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.calc import simulate, check_listing

st.set_page_config(page_title="ポートフォリオ・タイムマシン", layout="wide")

COLORS = ["#378ADD", "#185FA5", "#888780", "#B4B2A9", "#1D9E75",
          "#D85A30", "#D4537E", "#7F77DD", "#BA7517", "#639922"]


@st.cache_data
def load_master():
    df = pd.read_csv("data/master.csv", dtype=str)
    return df


master = load_master()
labels = master["label"].tolist()

st.title("ポートフォリオ・タイムマシン")
st.caption("過去に日本株でポートフォリオを組み、そのまま持ち続けたら今いくらか。暴落込みで振り返る。")

left, right = st.columns([1, 2])

with left:
    st.subheader("STEP 1  期間")
    c1, c2 = st.columns(2)
    start = c1.date_input("開始日", value=pd.to_datetime("2015-01-05")).strftime("%Y-%m-%d")
    end = c2.date_input("終了日", value=pd.to_datetime("2026-07-07")).strftime("%Y-%m-%d")

    st.subheader("STEP 2  銘柄と株数")
    n = st.number_input("銘柄数", min_value=1, max_value=10, value=3, step=1)

    holdings = {}
    for i in range(int(n)):
        col_a, col_b = st.columns([3, 1])
        pick = col_a.selectbox(f"銘柄 {i+1}", options=[""] + labels, key=f"stock_{i}")
        shares = col_b.number_input("株数", min_value=0, value=100, step=100, key=f"shares_{i}")
        if pick and shares > 0:
            code = pick.split(" ")[0]
            holdings[code] = holdings.get(code, 0) + int(shares)

    run = st.button("シミュレーション実行", type="primary", use_container_width=True)

with right:
    if not run:
        st.info("左で期間と銘柄・株数を入れて「シミュレーション実行」を押してください。")
    elif not holdings:
        st.warning("銘柄を1つ以上選び、株数を入力してください。")
    else:
        errors = check_listing(holdings, start)
        if errors:
            st.error("次の銘柄は選んだ開始日には購入できません(データ開始日より前です):")
            for e in errors:
                st.write("・", e)
        else:
            r = simulate(holdings, start, end)
            if not r["ok"]:
                st.error(r["reason"])
            else:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("投資元本", f"¥{r['principal_total']:,.0f}")
                m2.metric("最終評価額", f"¥{r['final_value']:,.0f}")
                m3.metric("リターン", f"{r['multiple']:.2f}倍", f"年率 {r['cagr']*100:+.1f}%")
                m4.metric("最大ドローダウン", f"{r['max_drawdown']*100:.1f}%")

                codes = list(r["principals"].keys())

                if len(codes) >= 2:
                    g1, g2 = st.columns([1, 2])
                    with g1:
                        names = [master.loc[master["code"] == c, "name"].iloc[0]
                                 if (master["code"] == c).any() else c for c in codes]
                        pie = go.Figure(go.Pie(
                            labels=[f"{c} {n}" for c, n in zip(codes, names)],
                            values=list(r["principals"].values()),
                            marker=dict(colors=COLORS[:len(codes)]),
                            hole=0.35, textinfo="percent",
                            sort=False,
                        ))
                        pie.update_layout(
                            title=f"開始時の構成比({start}評価)",
                            margin=dict(t=40, b=40, l=10, r=10), height=380,
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", y=-0.05,
                                        xanchor="center", x=0.5, font=dict(size=11)),
                        )
                        st.plotly_chart(pie, use_container_width=True)
                else:
                    st.caption("構成比: 1銘柄のみのため省略(複数銘柄で表示されます)")
                    g2 = st.container()

                with g2:
                    line = go.Figure(go.Scatter(
                        x=pd.to_datetime(r["series_dates"]), y=r["series_values"],
                        mode="lines", line=dict(color="#378ADD", width=2),
                        fill="tozeroy", fillcolor="rgba(55,138,221,0.08)",
                    ))
                    line.add_hline(y=r["principal_total"], line_dash="dot",
                                   line_color="#888780",
                                   annotation_text=f"元本 ¥{r['principal_total']:,.0f}")
                    line.update_layout(title="ポートフォリオ評価額の推移(配当込み)",
                                       margin=dict(t=40, b=0, l=0, r=0), height=320,
                                       yaxis_title="評価額(円)")
                    st.plotly_chart(line, use_container_width=True)

                st.caption(f"最大下落は {r['dd_peak']} の高値から {r['dd_trough']} まで。"
                           f"この局面を耐えて上記の着地。手数料・税・単元制約・為替は未考慮。")

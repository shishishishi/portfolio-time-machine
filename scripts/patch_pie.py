# app.py の円グラフ部分を、1銘柄時は非表示・複数時は固定サイズに差し替える
from pathlib import Path

p = Path("app.py")
src = p.read_text(encoding="utf-8")

old_block = '''                g1, g2 = st.columns([1, 2])

                with g1:
                    codes = list(r["principals"].keys())
                    names = [master.loc[master["code"] == c, "name"].iloc[0]
                             if (master["code"] == c).any() else c for c in codes]
                    pie = go.Figure(go.Pie(
                        labels=[f"{c} {n}" for c, n in zip(codes, names)],
                        values=list(r["principals"].values()),
                        marker=dict(colors=COLORS[:len(codes)]),
                        hole=0.35, textinfo="percent",
                    ))
                    pie.update_layout(title=f"開始時の構成比({start}評価)",
                                      margin=dict(t=40, b=0, l=0, r=0), height=320,
                                      showlegend=True, legend=dict(font=dict(size=11)))
                    st.plotly_chart(pie, use_container_width=True)

                with g2:'''

new_block = '''                codes = list(r["principals"].keys())

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

                with g2:'''

if old_block not in src:
    print("NG: 置き換え対象が見つかりませんでした")
else:
    src = src.replace(old_block, new_block, 1)
    p.write_text(src, encoding="utf-8")
    print("OK: 円グラフを1銘柄時は非表示・複数時は固定サイズに変更しました")

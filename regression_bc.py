# regression_bc.py — 本物リポジトリのルートに置いて実行:  python regression_bc.py
# 旧B(simulate_accumulation) と 新エンジンの純積立(スポット無し simulate_hybrid)が
# 実データで完全一致することを確認してから、旧Bをエンジン経由に切り替える判断材料にする。
from core.calc import simulate_accumulation, simulate_hybrid

CODE, START, END = "1306", "2015-01-01", "2026-07-07"

for mode, val in [("amount", 10000), ("shares", 1)]:
    old = simulate_accumulation(CODE, START, END, mode, val, 25)
    new = simulate_hybrid(CODE, START, END, mode, val, 25, spot_specs=[])
    assert old and new, "データ取得に失敗"
    assert old["dates"] == new["dates"], f"[{mode}] 日付軸ずれ"
    dv = max(abs(a - b) for a, b in zip(old["values"], new["values"]))
    di = max(abs(a - b) for a, b in zip(old["invested"], new["invested"]))
    tag = "金額指定" if mode == "amount" else "株数指定"
    print(f"[{tag}] 買付{len(old['buys'])}回  value最大差={dv:.3e}  invested最大差={di:.3e}  "
          f"{'OK 一致' if dv < 1e-6 and di < 1e-6 else 'NG'}")

print("\n一致していれば、simulate_accumulation を _evaluate_buys 経由に載せ替えても結果は変わりません。")

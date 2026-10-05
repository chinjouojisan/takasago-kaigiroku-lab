# B16: ネットワークなし。raw/dayori/D*.txt の「議案概要」部分の書式を確認するための抜き出し(まだ解析しない)
# 出力: raw/analysis/gian_gaiyo_raw_v1.txt (各号の議案概要を行番号つきで原文のまま), summary_gaiyo_probe_v1.txt (見出し位置の一覧)
import glob, os, re
os.makedirs("raw/analysis", exist_ok=True)
raw_out = []; sm = []
for p in sorted(glob.glob("raw/dayori/D*.txt")):
    did = os.path.basename(p)[:-4]
    lines = [l.rstrip("\n") for l in open(p, encoding="utf-8", errors="replace").read().split("\n")]
    idx = [i for i, l in enumerate(lines) if "議案概要" in l]
    idx2 = [i for i, l in enumerate(lines) if "表決結果" in l]
    kinds = [(i, l.strip()) for i, l in enumerate(lines) if re.match(r"^\s*(事件議案|条例議案|補正予算|予算|陳情|請願|意見書|報告|同意|諮問|人事|決算)\S{0,12}\s*$", l)]
    sm.append(f"{did}: 総行数{len(lines)} 議案概要の行={idx} 表決結果の行={idx2[:6]} 種別見出し={kinds[:14]}")
    raw_out.append(f"===== {did} =====")
    if idx:
        s = idx[0]
        e = min([i for i in idx2 if i > s] + [s + 90])
        e = min(e, s + 120)
        for i in range(s, e):
            raw_out.append(f"{i}|{lines[i].replace(chr(9), '<TAB>')}")
    else:
        raw_out.append("(議案概要なし)")
open("raw/analysis/gian_gaiyo_raw_v1.txt", "w", encoding="utf-8").write("\n".join(raw_out))
open("raw/analysis/summary_gaiyo_probe_v1.txt", "w", encoding="utf-8").write("\n".join(sm))
print("done", len(sm))

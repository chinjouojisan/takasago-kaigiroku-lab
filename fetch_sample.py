# B9: ネットワークなし。取りこぼしの原因を探すため、議事録の該当箇所の抜粋を出す
import os, re, unicodedata, datetime
A = "raw/analysis"
def nf(s): return unicodedata.normalize("NFKC", s).replace("﨑","崎").replace("髙","高")
def speeches(fn):
    t = open(f"raw/minutes/{fn}.txt", encoding="utf-8", errors="replace").read()
    return [s for s in re.split(r"(?m)^(?=○)", t) if s.startswith("○")]
out = []
def head(s, n=140):
    return re.sub(r"\s+", " ", nf(s))[:n]
# 1) 取りこぼし疑い: 令和5年3月(R050306A, R050315A, R050316A)の議長の発言のうち「番目」「発言を許可」を含むもの
for fn in ["R050306A", "R050315A", "R050316A"]:
    out.append(f"===== {fn}: 議長の呼び出し発言 =====")
    for i, s in enumerate(speeches(fn)):
        lab = nf(s.split("\n", 1)[0])
        if "議長" in lab and re.search(r"番目|発言を許可|発言を許し", nf(s)):
            out.append(f"[{i}] {head(s, 220)}")
# 2) 岩見・藤森・石崎 の名前が出る議長発言(全本会議・質問日のみ、各最大6件ずつ)
for fn in ["R050306A", "R050315A", "R050316A"]:
    for nm in ["岩見", "藤森", "石崎"]:
        hits = [(i, s) for i, s in enumerate(speeches(fn)) if nm in nf(s)[:300] and "議長" in nf(s.split("\n",1)[0])]
        out.append(f"===== {fn} 議長発言に「{nm}」: {len(hits)}件 =====")
        for i, s in hits[:4]: out.append(f"[{i}] {head(s, 220)}")
# 3) 空欄ID 2件の前後
for fn, nm in [("R041212A", "松野"), ("R080615A", "入江")]:
    out.append(f"===== {fn}: 「{nm}」を含む議長発言(先頭) =====")
    n = 0
    for i, s in enumerate(speeches(fn)):
        if "議長" in nf(s.split("\n",1)[0]) and re.search(r"番目", nf(s)):
            out.append(f"[{i}] {head(s, 160)}"); n += 1
    out.append("--- 議事日程の出席議員(先頭400字) ---")
    sp = speeches(fn)
    out.append(head(sp[0], 600) if sp else "(なし)")
open(f"{A}/probe.txt", "w", encoding="utf-8").write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat()}\n" + "\n".join(out) + "\n")
print("done")

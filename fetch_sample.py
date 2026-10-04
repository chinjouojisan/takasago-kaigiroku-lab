# B7: ネットワークなし。raw/analysis/blocks.csv と days.csv を突き合わせて、短い点検表を作る
import csv, os, collections, datetime
A = "raw/analysis"
def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
blocks = rd(f"{A}/blocks.csv")
days = rd(f"{A}/days.csv")
byfn = collections.Counter(b["fileName"] for b in blocks)
rows = []
for d in days:
    exp = int(d.get("質問のまとまり数") or 0)
    if exp or byfn.get(d["fileName"]):
        got = byfn.get(d["fileName"], 0)
        rows.append([d["fileName"], d["開催日"], d["質問の種別"], exp, got, "OK" if exp == got else "差あり"])
with open(f"{A}/check_days.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["fileName","開催日","種別","日程の想定数","抽出数","判定"]); w.writerows(rows)
# 議員別の件数(一般質問/代表質問)
mem = collections.defaultdict(collections.Counter)
for b in blocks:
    mem[(b["議員ID"], b["議員名(正規化)"])][b["種別"]] += 1
with open(f"{A}/check_members.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["議員ID","氏名","一般質問","代表質問","計"])
    for k in sorted(mem):
        c = mem[k]; g = sum(v for t, v in c.items() if t.startswith("一般")); r = sum(v for t, v in c.items() if t.startswith("代表"))
        w.writerow([k[0], k[1], g, r, g + r])
# 注意付き・低確信
with open(f"{A}/check_flags.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["blockID","開催日","議員名","確信度","注意"])
    for b in blocks:
        try: low = float(b["確信度"]) < 0.95
        except: low = True
        if low or b.get("注意"): w.writerow([b["blockID"], b["開催日"], b["議員名(正規化)"], b["確信度"], b.get("注意","")])
with open(f"{A}/log_check.txt", "w", encoding="utf-8") as f:
    f.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} blocks {len(blocks)}行 / 質問日 {len(rows)}日 / 差あり {sum(1 for r in rows if r[5]!='OK')}日\n")
print("done")

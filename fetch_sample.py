# B8: ネットワークなし。blocks.csv と raw/minutes を使い、3つの疑問点を点検する
import csv, os, re, glob, unicodedata, datetime, collections
A = "raw/analysis"
def sq(s):
    s = unicodedata.normalize("NFKC", s).replace("﨑", "崎").replace("髙", "高")
    return re.sub(r"\s+", "", s)
def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
def wr(p, head, rows):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)
blocks = rd(f"{A}/blocks.csv")
# 1. 議員IDが空欄の行
wr(f"{A}/check_blank.csv", ["blockID","開催日","種別","順番","議席","議員名","会派","確信度","注意","冒頭80字"],
   [[b["blockID"],b["開催日"],b["種別"],b["順番"],b["議席"],b["議員名(正規化)"],b["自己申告の会派"],b["確信度"],b["注意"],b["冒頭80字"]]
    for b in blocks if not b["議員ID"].strip()])
# 2. 質問0件の議員(+全員)の、本会議の議事録での現れ方
ROSTER = {"M001":"石崎徹","M002":"入江啓太","M003":"今竹大祐","M004":"岩見明","M005":"大西由紀","M006":"川端宏明","M007":"北野誠一郎","M008":"坂本まり","M009":"迫川高行","M010":"芝本鎮彰","M011":"島津明香","M012":"鈴木利信","M013":"鷹尾治久","M014":"春増勝利","M015":"藤森誠","M016":"松野優也","M017":"森秀樹","M018":"山田光昭","M019":"横田英樹"}
stat = {m: collections.defaultdict(list) for m in ROSTER}
for p in sorted(glob.glob("raw/minutes/R*A.txt")):
    fn = os.path.basename(p)[:-4]
    txt = open(p, encoding="utf-8", errors="replace").read()
    for sp in re.split(r"(?m)^(?=○)", txt):
        if not sp.startswith("○"): continue
        label = sq(sp.split("\n", 1)[0])[:40]
        for m, nm in ROSTER.items():
            if nm in label:
                role = "議長" if label.startswith("○議長") else "副議長" if label.startswith("○副議長") else "議員として発言"
                stat[m][role].append(fn)
    s = sq(txt)
    for m, nm in ROSTER.items():
        n = len(re.findall(r"\d+番、?" + re.escape(nm) + r"議員", s))
        if n: stat[m]["呼び出し・指名"].append(fn)
rows = []
for m, nm in ROSTER.items():
    for role, fns in stat[m].items():
        rows.append([m, nm, role, len(fns), min(fns), max(fns)])
wr(f"{A}/check_zero.csv", ["議員ID","氏名","現れ方","日数","最初のファイル","最後のファイル"], rows)
# 3. 代表質問の呼び出し順
rows = []
for b in blocks:
    if b["種別"].startswith("代表"):
        rows.append([b["fileName"], b["順番"], b["議席"], b["議員ID"], b["議員名(正規化)"], b["自己申告の会派"], b["開始発言No"], b["終了発言No(次の呼び出しまで)"], b["本人の発言数"], b["冒頭80字"][:40]])
wr(f"{A}/check_daihyo.csv", ["fileName","順番","議席","議員ID","氏名","会派","開始No","終了No","本人の発言数","冒頭40字"], rows)
open(f"{A}/log_check2.txt", "w", encoding="utf-8").write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat()} 空欄ID {sum(1 for b in blocks if not b['議員ID'].strip())}行 / 代表質問 {len(rows)}行\n")
print("done")

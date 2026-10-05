# B14: ネットワークなし。raw/dayori/D*.txt(議会だより)から「議案ごとの議員別の賛否」を取り出す
# 出力: raw/analysis/votes_dayori.csv(1議員×1議案), raw/analysis/summary_votes_dayori.txt(確認用の短い要約)
import csv, glob, os, re, datetime, unicodedata, io
from collections import Counter, defaultdict
ROSTER = {"石崎徹":"M001","入江啓太":"M002","今竹大祐":"M003","岩見明":"M004","大西由紀":"M005","川端宏明":"M006","北野誠一郎":"M007","坂本まり":"M008","迫川高行":"M009","芝本鎮彰":"M010","島津明香":"M011","鈴木利信":"M012","鷹尾治久":"M013","春増勝利":"M014","藤森誠":"M015","松野優也":"M016","森秀樹":"M017","山田光昭":"M018","横田英樹":"M019"}
def sq(s):
    s = unicodedata.normalize("NFKC", s).replace("﨑", "崎").replace("髙", "高").replace("石埼", "石崎")
    return re.sub(r"\s+", "", s)
VOTE = re.compile(r"^[-・●\s]*(\S+(?:[ 　]\S+)?)[ 　\t]+(賛成|反対|注釈\s*\d*|欠席|棄権|退席|除斥|-|－|ー)\s*$")
RESULT = re.compile(r"^(原案可決|修正可決|可決|否決|同意|不同意|承認|不承認|採択|不採択|趣旨採択|継続審査|継続審議|継続|撤回|認定|不認定|廃案|意見書案可決|決議案可決|.{0,10}可決.{0,10}|.{0,10}否決.{0,10}|.{0,6}採択.{0,6}|.{0,6}審議.{0,6})$")
rows = []; per = {}
for p in sorted(glob.glob("raw/dayori/D*.txt")):
    did = os.path.basename(p)[:-4]
    lines = [l.strip() for l in open(p, encoding="utf-8", errors="replace").read().split("\n")]
    lines = [l for l in lines if l]
    recent = []      # 直近の「票でない行」
    bill = None; seq = 0; last_was_vote = False; faction = ""
    for l in lines:
        m = VOTE.match(l)
        if m and (sq(m.group(1)) in ROSTER or re.match(r"^[一-鿿々ぁ-んァ-ヶー]{1,6}[ 　]?[一-鿿々ぁ-んァ-ヶー]{1,6}$", m.group(1))):
            if not last_was_vote:
                # 新しい議案の最初の票: 直前の行から結果と件名を探す
                res_i = None
                for j in range(len(recent) - 1, -1, -1):
                    if RESULT.match(recent[j]): res_i = j; break
                if res_i is not None:
                    seq += 1
                    title = recent[res_i - 1] if res_i >= 1 else ""
                    # 件名が見出し的に短すぎる/括弧だけなら、その前の行も足す
                    if res_i >= 2 and (len(title) < 8 or re.match(r"^[（(].*[)）]$", title)):
                        title = recent[res_i - 2] + " " + title
                    bill = {"seq": seq, "title": title, "result": recent[res_i]}
                    faction = recent[-1] if recent[-1] != recent[res_i] else ""
                elif bill is not None and len(recent) >= 2:
                    seq += 1
                    bill = {"seq": seq, "title": recent[-2], "result": "(結果行なし)"}
                    faction = recent[-1]
                elif bill is not None:
                    faction = recent[-1] if recent else faction
            else:
                faction = faction
            name = sq(m.group(1))
            if bill is not None:
                rows.append([did, bill["seq"], bill["title"], bill["result"], faction, m.group(1), ROSTER.get(name, ""), m.group(2).replace(" ", "")])
            last_was_vote = True
            recent_after_vote = []
        else:
            if last_was_vote:
                recent = []   # 票の並びが終わった
            last_was_vote = False
            recent.append(l)
            recent = recent[-8:]
with open("raw/analysis/votes_dayori.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["号ID","議案の通し番号","件名","結果","会派見出し","議員名(原文)","議員ID","賛否"]); w.writerows(rows)
# 要約
out = io.StringIO(); out.write("生成 %s / 行 %d\n" % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(rows)))
by = defaultdict(lambda: defaultdict(list))
for r in rows: by[r[0]][r[1]].append(r)
for did in sorted(by):
    bills = by[did]; cnt = Counter(len(v) for v in bills.values())
    vals = Counter(r[7] for v in bills.values() for r in v)
    out.write("%s 議案%d件 / 1議案あたりの人数 %s / 賛否 %s\n" % (did, len(bills), dict(sorted(cnt.items())), dict(vals)))
resc = Counter(r[3] for k in by for v in by[k].values() for r in v[:1])
out.write("--- 結果の種類(議案数) --- %s\n" % dict(resc.most_common()))
miss = Counter(); allbills = 0
for did in by:
    for k, v in by[did].items():
        allbills += 1
        ids = {r[6] for r in v}
        for mid in ROSTER.values():
            if mid not in ids: miss[mid] += 1
out.write("--- 議案全体 %d件のうち、各議員の票が載っていない議案数 --- %s\n" % (allbills, dict(sorted(miss.items()))))
un = Counter(r[5] for r in rows if not r[6])
out.write("--- ID未対応の氏名 --- %s\n" % dict(un))
out.write("--- 議案の例(各号の最初の2件の件名と結果) ---\n")
for did in sorted(by):
    for k in sorted(by[did])[:2]:
        r = by[did][k][0]; out.write("%s #%d %s | %s | %d人\n" % (did, k, r[2][:50], r[3], len(by[did][k])))
open("raw/analysis/summary_votes_dayori.txt", "w", encoding="utf-8").write(out.getvalue())
print("done")

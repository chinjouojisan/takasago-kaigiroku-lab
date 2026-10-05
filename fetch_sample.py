# B15: ネットワークなし。本会議の議事録から「議案の全件リスト」と「採決結果の語句」を取り出す
# 出力: raw/analysis/bills_minutes.csv, raw/analysis/summary_bills_v1.txt
import csv, glob, os, re, io, datetime, unicodedata
from collections import Counter, defaultdict
def nf(s): return unicodedata.normalize("NFKC", s)
def one(s): return re.sub(r"\s+", " ", nf(s)).strip()
KIND = r"高[議予報認請陳諮願]"
NUM = re.compile(r"(%s第\s*\d+号)" % KIND)
RES = r"(全会一致|賛成多数|賛成少数|異議なし|異議ありません|原案可決|修正可決|可決|否決|承認|不承認|同意|不同意|認定|不認定|不採択|採択|継続審査|継続審議|撤回|了承|起立)"
def split_speeches(t):
    return [x for x in re.split(r"(?m)^(?=○)", t.replace("\r\n", "\n")) if x.startswith("○")]
def head_of(t):
    h = {}
    for l in t.split("\n")[:6]:
        m = re.match(r"^(開催日|会議名)：(.*)$", l)
        if m: h[m.group(1)] = m.group(2).strip()
    return h
bills = {}        # (session, 号) -> dict
days_by_session = defaultdict(list)
for p in sorted(glob.glob("raw/minutes/R*A.txt")):
    fn = os.path.basename(p)[:-4]
    t = open(p, encoding="utf-8", errors="replace").read()
    h = head_of(t)
    mn = one(h.get("会議名", ""))
    m = re.match(r"(令和\s*\d+年\s*\d+月(?:定例会|臨時会)|令和\s*\d+年\s*\d+月第\d+回臨時会|令和\s*\d+年第\d+回臨時会)", mn.replace(" ", ""))
    sess = re.sub(r"\s+", "", (m.group(1) if m else mn.split("（")[0]))
    days_by_session[sess].append(fn)
    sp = split_speeches(t)
    if not sp: continue
    # 議事日程(先頭の発言)から議案の件名を取る
    agenda = one(sp[0])
    parts = re.split(r"(?=%s第\s*\d+号)|(?=日程第\s*\d+)" % KIND, agenda)
    for part in parts:
        mm = NUM.match(part)
        if not mm: continue
        no = re.sub(r"\s+", "", mm.group(1))
        title = part[mm.end():].strip()
        title = re.sub(r"^[\s　]+", "", title)[:80]
        key = (sess, no)
        b = bills.setdefault(key, {"session": sess, "no": no, "title": title, "days": []})
        if len(title) > len(b["title"]): b["title"] = title
        b["days"].append(fn)
    # 結果の語句: 各日の本文で、議案番号の直後300字以内の語句
    body = nf(t)
    for key, b in bills.items():
        if key[0] != sess: continue
        no_pat = re.escape(key[1][:-1]).replace(r"\ ", r"\s*") + r"号"
        no_pat = re.sub(r"第", r"第\\s*", re.escape(key[1][1:].replace("第", "第"))) if False else None
        for mt in re.finditer(re.escape(key[1][:2]) + r"第\s*" + re.escape(re.search(r"第(\d+)号", key[1]).group(1)) + "号", body):
            seg = body[mt.end(): mt.end() + 300]
            r = re.search(RES, seg)
            if r: b.setdefault("res", Counter())[r.group(1)] += 1
rows = []
for k in sorted(bills, key=lambda k: (min(bills[k]["days"]), k[1])):
    b = bills[k]
    res = b.get("res", Counter())
    rows.append([b["session"], b["no"], b["title"], min(b["days"]), max(b["days"]), len(set(b["days"])), "/".join("%s%d" % (w, c) for w, c in res.most_common(4))])
with open("raw/analysis/bills_minutes.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["会議", "議案番号", "件名(議事日程)", "最初の日", "最後の日", "登場した日数", "近くの結果語(上位)"]); w.writerows(rows)
out = io.StringIO(); out.write("生成 %s / 議案 %d件\n" % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(rows)))
per = Counter(r[0] for r in rows)
out.write("--- 会議ごとの議案数 ---\n")
for s in sorted(per, key=lambda s: min(days_by_session[s]) if days_by_session[s] else ""): out.write("%s %d件(日数%d)\n" % (s, per[s], len(days_by_session[s])))
pre = Counter(re.match(KIND, r[1]).group(0) for r in rows)
out.write("--- 種別 --- %s\n" % dict(pre))
nores = sum(1 for r in rows if not r[6])
out.write("--- 結果語が見つからない議案 --- %d件\n" % nores)
out.write("--- 例(最初の10件) ---\n")
for r in rows[:10]: out.write("%s | %s | %s | %s\n" % (r[0], r[1], r[2][:40], r[6]))
open("raw/analysis/summary_bills_v1.txt", "w", encoding="utf-8").write(out.getvalue())
print("done")

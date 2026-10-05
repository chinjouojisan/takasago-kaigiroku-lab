# B17: ネットワークなし。会議録(raw/minutes)の議題ごとに「採決のようす」を分類し、議案概要(bills_final.csv)の議案と対応づける
# 出力: raw/analysis/minutes_votes.csv, bills_final2.csv, summary_minutes_vote_v1.txt
import csv, re, unicodedata, collections, os
R = list(csv.DictReader(open("raw/analysis/days.csv", encoding="utf-8-sig")))
def nf(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t))
sess = collections.OrderedDict()
for r in R:
    name = re.sub(r"（第.*", "", r["会議名"]); name = re.sub(r"\s+", "", name)
    sess.setdefault(name, []).append(r["fileName"])
SESS_OF = {"D01":["令和4年9月定例会"],"D02":["令和4年12月定例会"],"D03":["令和5年3月定例会"],"D04":["令和5年5月臨時会","令和5年6月定例会"],"D05":["令和5年9月定例会"],"D06":["令和5年12月定例会"],"D07":["令和6年2月臨時会","令和6年3月定例会"],"D08":["令和6年6月定例会"],"D09":["令和6年9月定例会"],"D10":["令和6年12月定例会"],"D11":["令和7年1月臨時会","令和7年3月定例会"],"D12":["令和7年6月定例会"],"D13":["令和7年7月臨時会","令和7年9月定例会"],"D14":["令和7年12月定例会"],"D15":["令和8年1月臨時会","令和8年3月定例会"],"D16":["令和8年5月臨時会","令和8年6月定例会"]}
def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[（(]注釈\s*\d*[）)]", "", s); s = re.sub(r"^[●・\s]+", "", s)
    s = re.sub(r"^高[議予報諮]第\s*\d+号[、\s]*", "", s)
    s = s.replace("﨑", "崎").replace("髙", "高")
    s = re.sub(r"[\s「」『』、。,．.]", "", s)
    s = re.sub(r"(補正予算|予算)$", "", s); s = re.sub(r"補正$", "", s)
    s = re.sub(r"について$", "", s)
    return s
SPLIT = re.compile(r"(?=日程第\s*\d+[、,])")
rows = []
for sname, files in sess.items():
    for fn in files:
        t = nf(open("raw/minutes/%s.txt" % fn, encoding="utf-8", errors="replace").read())
        chunks = SPLIT.split(t)
        for ch in chunks[1:]:
            m = re.match(r"日程第\s*(\d+)[、,]\s*(.*?)(?:を議題といたします|を議題とします|$)", ch[:600])
            if not m: continue
            nit, head = m.group(1), m.group(2)
            if "議題" not in ch[:600]: continue
            body = ch
            nums = []
            for mm in re.finditer(r"(高[議予報諮専])第\s*(\d+)号(?:\s*(?:から|～|〜)\s*(?:高[議予報諮専])?第?\s*(\d+)号(?:まで)?)?", head):
                a = int(mm.group(2)); b = int(mm.group(3)) if mm.group(3) else a
                for n in range(a, b + 1): nums.append("%s第%d号" % (mm.group(1), n))
            items = re.split(r"、(?=高[議予報諮専]第\s*\d+号)", head)
            titles = [re.sub(r"^高[議予報諮専]第\s*\d+号[、\s]*", "", x) for x in items]
            ng = bool(re.search(r"異議あり(?!ま)", body)); el = bool(re.search(r"電子表決|表決システム|ボタン", body)); ki = bool(re.search(r"起立", body))
            tasu = bool(re.search(r"賛成多数", body)); zen = bool(re.search(r"全員賛成|賛成全員|全会一致|全員起立", body))
            hi = bool(re.search(r"否決", body)); inasi = bool(re.search(r"異議なし", body))
            hantai = len(re.findall(r"反対の?討論", body)); sansei = len(re.findall(r"賛成の?討論", body))
            dec = bool(re.search(r"可決(いた|され|しま)|承認(いた|され|しま)|同意(いた|され|しま)|認定(いた|され|しま)|否決(いた|され|しま)|採択(いた|され|しま)|決定いたしました|可決であります|承認であります|同意であります|認定であります|否決であります|採択であります", body))
            if not dec:
                rows_skip = True
            if ng or el or ki or tasu or hi:
                kind = "採決あり(" + ("電子表決" if el else "") + ("起立" if ki else "") + ("、賛成多数" if tasu else "") + ("、全員賛成" if zen else "") + ("、否決語あり" if hi else "") + ")"
            elif inasi: kind = "異議なし(全会一致)"
            else: kind = "判定不能"
            rows.append({"会議":sname,"ファイル":fn,"日程":nit,"議案番号":"|".join(nums),"件名":"|".join(titles)[:200],"採決区分":kind,"一括議題":"はい" if len(nums) > 1 else "","反対討論語":hantai,"賛成討論語":sansei,"議題冒頭":head[:80],"決定語あり":"はい" if dec else ""})
os.makedirs("raw/analysis", exist_ok=True)
with open("raw/analysis/minutes_votes.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# 対応づけ
B = list(csv.DictReader(open("raw/analysis/bills_final.csv", encoding="utf-8-sig")))
idx = collections.defaultdict(list)
for r in [x for x in rows if x["決定語あり"]]:
    for tt in (r["件名"].split("|") if r["件名"] else []):
        idx[(r["会議"], norm(tt))].append(r)
    for nn in r["議案番号"].split("|"):
        if nn: idx[(r["会議"], nn)].append(r)
out = []
for b in B:
    cands = []
    for s in SESS_OF[b["号ID"]]:
        if b["議案番号"]: cands += idx.get((s, b["議案番号"]), [])
        cands += idx.get((s, b["照合キー"] and norm(b["件名"])), [])
    if not cands:   # 予備: かっこ内を除いた件名で比較
        key0 = re.sub(r"[（(].*?[）)]", "", unicodedata.normalize("NFKC", b["件名"]))
        k0 = norm(key0)
        for s_ in SESS_OF[b["号ID"]]:
            for r_ in rows:
                if r_["会議"] != s_ or not r_["決定語あり"]: continue
                for tt in r_["件名"].split("|"):
                    k1 = norm(re.sub(r"[（(].*?[）)]", "", tt))
                    if k0 and k1 and (k0 == k1 or (len(k0) > 10 and (k1.startswith(k0) or k0.startswith(k1)))): cands.append(r_)
    seen = []; 
    for c in cands:
        if c not in seen: seen.append(c)
    kinds = sorted(set(c["採決区分"] for c in seen))
    b2 = dict(b); b2["会議録の採決区分"] = "/".join(kinds); b2["会議録の候補数"] = len(seen)
    b2["会議録ファイル"] = "|".join(sorted(set(c["ファイル"] for c in seen)))[:60]
    out.append(b2)
with open("raw/analysis/bills_final2.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
S = []
S.append("会議録の議題: %d件 (採決区分: %s)" % (len(rows), dict(collections.Counter(re.sub(r"\(.*", "", r["採決区分"]) for r in rows))))
S.append("議案概要の議案 %d件 のうち 会議録で見つかった: %d件, 見つからない: %d件" % (len(out), sum(1 for o in out if o["会議録の候補数"]), sum(1 for o in out if not o["会議録の候補数"])))
S.append("--- 状態×会議録の区分 ---")
c = collections.Counter((o["賛否の状態"][:12], o["会議録の採決区分"][:14] or "(見つからず)") for o in out)
for k, v in sorted(c.items()): S.append("%s | %s : %d" % (k[0], k[1], v))
S.append("--- 推定(全員賛成)なのに会議録は採決あり ---")
for o in out:
    if o["賛否の状態"].startswith("賛否表になし") and "採決あり" in o["会議録の採決区分"]: S.append("%s %s %s | %s" % (o["号ID"], o["種別"], o["件名"][:30], o["会議録の採決区分"]))
S.append("--- 推定で会議録に見つからない ---")
for o in out:
    if o["賛否の状態"].startswith("賛否表になし") and not o["会議録の候補数"]: S.append("%s %s %s" % (o["号ID"], o["種別"], o["件名"][:34]))
open("raw/analysis/summary_minutes_vote_v1.txt", "w", encoding="utf-8").write("\n".join(S))
print("done")

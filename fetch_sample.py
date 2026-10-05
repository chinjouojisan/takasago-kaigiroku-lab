# B16: ネットワークなし。raw/dayori/D*.txt の「議案概要」から全議案リストを作り、賛否表(votes_dayori.csv)と突き合わせる
# 出力: raw/analysis/bills_gaiyo.csv, bills_match.csv, summary_gaiyo_match_v1.txt
import csv, glob, os, re, unicodedata
from collections import Counter, defaultdict
os.makedirs("raw/analysis", exist_ok=True)
MONTH = {"D01":"R4/9","D02":"R4/12","D03":"R5/3","D04":"R5/6","D05":"R5/9","D06":"R5/12","D07":"R6/3","D08":"R6/6","D09":"R6/9","D10":"R6/12","D11":"R7/3","D12":"R7/6","D13":"R7/9","D14":"R7/12","D15":"R8/3","D16":"R8/6"}
def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[（(]注釈\s*\d*[）)]", "", s)
    s = re.sub(r"^[●・\s]+", "", s)
    s = re.sub(r"^高[議予報諮]第\s*\d+号\s*", "", s)
    s = s.replace("﨑", "崎").replace("髙", "高")
    return re.sub(r"[\s　「」『』、。,．.]", "", s)
HEAD_KIND = re.compile(r"^[●\s]*(可決した|継続審議とした|否決した|撤回した)?(事件議案・条例議案|事件議案|条例議案|補正予算|予算議案|予算)(?:[（(]\d+年度[）)])?\s*$")
HEAD_PET = re.compile(r"^[●\s]*(請願及び陳情|請願・陳情|陳\s*情|請願)\s*$")
HEAD_OUT = re.compile(r"^[●\s【\[]*(採択|趣旨採択|不採択|継続審議|継続審査|撤回)[】\]\s]*$")
STOP = re.compile(r"委員会審査の概要報告|議案の表決結果|議案等の表決結果|表決結果を公表|^決算|^人事|^意見書を提出|^[（(]?.{0,12}[）)]?\s*議案概要|^\S{0,12}議案概要")
NUMB = re.compile(r"^[●\s]*(高[議予報諮]第\s*\d+号)\s*(.+)$")
PETEND = re.compile(r"(陳情書?|請願書?|件)\s*$")
def session_of(line, did):
    m = re.search(r"第\s*(\d+)\s*回\s*臨時会", line)
    if m: return "第%s回臨時会" % m.group(1)
    m = re.search(r"(\d+)\s*月\s*定例会", line)
    if m: return "%s月定例会" % m.group(1)
    return ""
rows = []
for p in sorted(glob.glob("raw/dayori/D*.txt")):
    did = os.path.basename(p)[:-4]
    L = [l.strip() for l in open(p, encoding="utf-8", errors="replace").read().split("\n")]
    starts = [i for i, l in enumerate(L) if "議案概要" in l]
    if did == "D15":   # 見出しなしの号: 「事件議案・条例議案」から開始
        starts = [i for i, l in enumerate(L) if l == "事件議案・条例議案"][:1]
    for si in starts:
        sess = session_of(L[si], did) or ("3月定例会" if did == "D15" else "")
        kind = res = ""; pet = False
        i = si if did == "D15" else si + 1
        n_items = 0
        while i < len(L):
            l = L[i]
            if not l: i += 1; continue
            if i > si and (STOP.search(l) and not HEAD_KIND.match(l)) and not (did == "D15" and i == si):
                break
            m = HEAD_KIND.match(l)
            if m:
                res = (m.group(1) or "可決").replace("した","").replace("とした",""); kind = m.group(2); pet = False; i += 1; continue
            if HEAD_PET.match(l):
                kind = "陳情"; pet = True; res = ""; i += 1; continue
            m = HEAD_OUT.match(l)
            if m and pet:
                res = m.group(1); i += 1; continue
            if pet and not PETEND.search(l):
                break
            if not kind: i += 1; continue
            if re.search(r"実施される主な事業|^以上、決議|^\d{4}年|^【", l):
                break
            if kind in ("補正予算", "予算", "予算議案"):
                if not re.search(r"会計|予算", l) or len(l) > 80 or re.search(r"決議|議決にあたって|事業（", l): i += 1; continue
            elif kind != "陳情":
                if not re.search(r"(について|のこと|件|変更|ついて)$", re.sub(r"[（(][^（()）]*(?:[（(][^（()）]*[）)][^（()）]*)*[）)]\s*$", "", l)) or len(l) > 140: i += 1; continue
            mm = NUMB.match(l)
            no = mm.group(1).replace(" ", "") if mm else ""
            title = (mm.group(2) if mm else l).lstrip("●・ ")
            rows.append({"号ID":did,"号の月":MONTH[did],"会議":sess,"種別":kind,"結果(議会だより)":res or "(D16/D15は結果欄なし)","議案番号":no,"件名":title,"照合キー":norm(title)})
            i += 1
with open("raw/analysis/bills_gaiyo.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# 賛否表の議案
V = list(csv.DictReader(open("raw/analysis/votes_dayori.csv", encoding="utf-8-sig")))
vb = {}; cnt = defaultdict(Counter)
for r in V:
    k = (r["号ID"], r["議案の通し番号"])
    vb.setdefault(k, {"title": r["件名"], "result": r["結果"]})
    cnt[k][r["賛否"]] += 1
# 突き合わせ: 同じ号の中でキー一致(同名の議案が複数ある場合は順番に消費)
pool = defaultdict(list)
for idx, r in enumerate(rows): pool[(r["号ID"], r["照合キー"])].append(idx)
used = set(); match = []
for k, v in sorted(vb.items(), key=lambda x: (x[0][0], int(x[0][1]))):
    key = norm(v["title"]).replace("補正予算", "補正")
    cand = None
    for kk in ((k[0], norm(v["title"])), (k[0], key)):
        for idx in pool.get(kk, []):
            if idx not in used: cand = idx; break
        if cand is not None: break
    if cand is None:   # 補正予算は「第N回令和x年度高砂市○○会計」(補正の語なし)と比較
        a = norm(v["title"]).replace("補正予算", "")
        for idx, r in enumerate(rows):
            if r["号ID"] == k[0] and idx not in used and (r["照合キー"].replace("補正", "") == a or (len(a) > 12 and (a in r["照合キー"] or r["照合キー"] in a))):
                cand = idx; break
    if cand is not None: used.add(cand)
    c = cnt[k]
    match.append({"号ID":k[0],"通し番号":k[1],"賛否表の件名":v["title"],"賛否表の結果":v["result"],"賛成":c["賛成"],"反対":c["反対"],"欠席等":sum(c.values())-c["賛成"]-c["反対"],
                  "概要の件名":rows[cand]["件名"] if cand is not None else "","概要の種別":rows[cand]["種別"] if cand is not None else "","概要の結果":rows[cand]["結果(議会だより)"] if cand is not None else "","照合":"一致" if cand is not None else "概要になし"})
with open("raw/analysis/bills_match.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(match[0].keys())); w.writeheader(); w.writerows(match)


def expand(t):
    t = unicodedata.normalize("NFKC", t); out = set(); pre = ""
    for part in re.split(r"[、,，]", t):
        part = part.strip()
        m = re.match(r"^(高[議予])", part)
        if m: pre = m.group(1)
        nums = re.findall(r"(\d+)", part)
        if re.search(r"[～~〜]", part) and len(nums) >= 2:
            a, b = int(nums[0]), int(nums[1])
            out |= {(pre, n) for n in range(a, b + 1)}
        else:
            out |= {(pre, int(n)) for n in nums}
    return out
grp = {}
for m in match:
    if m["照合"] != "一致" and m["号ID"] in ("D15", "D16"):
        nums = expand(m["賛否表の件名"] if m["賛否表の件名"].startswith("高") else re.sub(r"^高[議予]第\d+号", lambda x: x.group(0), m["賛否表の件名"]))
        if nums:
            for x in nums: grp[(m["号ID"], x)] = m
byrow = {}
for idx, r in enumerate(rows):
    if r["議案番号"]:
        mm = re.match(r"(高[議予])第(\d+)号", r["議案番号"])
        key = (r["号ID"], (mm.group(1), int(mm.group(2)))) if mm else None
        if key in grp: byrow[idx] = grp[key]
for m in match:
    if m["照合"] != "一致" and m["号ID"] in ("D15", "D16"):
        m["照合"] = "グループ表示で一致" if any(v is m for v in byrow.values()) else "概要外(臨時会など)"
final = []
for idx, r in enumerate(rows):
    vk = None; st = ""
    if idx in used:
        st = "議員別の賛否あり"
        for m in match:
            if m["照合"] == "一致" and m["概要の件名"] == r["件名"] and m["号ID"] == r["号ID"]: vk = m["通し番号"]; break
    elif idx in byrow:
        vk = byrow[idx]["通し番号"]; st = "議員別の賛否あり(グループ表示)"
    else:
        st = "継続審議(採決なし)" if r["結果(議会だより)"].startswith("継続審") else "賛否表になし→全員賛成と推定(要:会議録確認)"
    final.append({**r, "賛否の状態": st, "賛否表の通し番号": vk or ""})
with open("raw/analysis/bills_final.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(final[0].keys())); w.writeheader(); w.writerows(final)
used |= set(byrow.keys())
with open("raw/analysis/bills_match.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(match[0].keys())); w.writeheader(); w.writerows(match)
S = []
S.append("概要の議案数: %d (号別: %s)" % (len(rows), dict(Counter(r["号ID"] for r in rows))))
S.append("種別: %s" % dict(Counter(r["種別"] for r in rows)))
S.append("結果: %s" % dict(Counter(r["結果(議会だより)"] for r in rows)))
S.append("賛否表の議案 %d 件のうち 概要と一致 %d / 概要になし %d" % (len(match), sum(m["照合"]=="一致" for m in match), sum(m["照合"]!="一致" for m in match)))
S.append("--- 概要になし(賛否表側) ---")
for m in match:
    if m["照合"] != "一致": S.append("%s-%s %s [%s]" % (m["号ID"], m["通し番号"], m["賛否表の件名"][:40], m["賛否表の結果"]))
S.append("--- 概要にあるが賛否表に無い(=全員賛成と推定の候補)号別 ---")
rest = [r for i, r in enumerate(rows) if i not in used]
S.append("件数 %d: %s" % (len(rest), dict(Counter(r["号ID"] for r in rest))))
S.append("種別: %s" % dict(Counter(r["種別"] for r in rest)))
S.append("状態別: %s" % dict(Counter(r["賛否の状態"] for r in final)))
S.append("--- 賛否表側の照合結果 ---")
S.append(str(dict(Counter(m["照合"] for m in match))))
S.append("--- 陳情で推定になった議案 ---")
for r in final:
    if r["種別"]=="陳情" and r["賛否の状態"].startswith("賛否表になし"): S.append("%s %s %s" % (r["号ID"], r["結果(議会だより)"], r["件名"][:40]))
open("raw/analysis/summary_gaiyo_match_v1.txt", "w", encoding="utf-8").write("\n".join(S))
print("done")

# ===== ここから B17 部分 =====
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
SPLIT = re.compile(r"(?=日程第\s*\d+号?[、,])")
rows = []
for sname, files in sess.items():
    for fn in files:
        t = nf(open("raw/minutes/%s.txt" % fn, encoding="utf-8", errors="replace").read())
        chunks = SPLIT.split(t)
        for ch in chunks[1:]:
            m = re.match(r"日程第\s*(\d+)号?[、,]\s*(.*?)(?:を議題といたします|を議題とします|$)", ch[:600])
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

# 同名議案のグループ照合: 会議録で採決ありの数 K と 議会だよりで議員別賛否のある数 M を比べる
def gkey(t): return norm(re.sub(r"[（(].*?[）)]", "", unicodedata.normalize("NFKC", t)))
groups = collections.defaultdict(list)
for o in out: groups[(o["号ID"], gkey(o["件名"]))].append(o)
mrows = collections.defaultdict(list)
for r in rows:
    if not r["決定語あり"] or "判定" in r["採決区分"]: continue
    for tt in r["件名"].split("|"):
        mrows[(r["会議"], gkey(tt))].append(r)
for (d, k), g in groups.items():
    ch = []
    for s_ in SESS_OF[d]: ch += mrows.get((s_, k), [])
    seen_ = []
    for c in ch:
        if (c["ファイル"], c["日程"]) not in [(x["ファイル"], x["日程"]) for x in seen_]: seen_.append(c)
    K = sum(1 for c in seen_ if c["採決区分"].startswith("採決あり")); N = len(seen_)
    M = sum(1 for o in g if o["賛否の状態"].startswith("議員別"))
    for o in g:
        if o["賛否の状態"].startswith("賛否表になし") or o["賛否の状態"].startswith("継続"):
            if not seen_: o["最終判定"] = "会議録で未発見(要確認)"
            elif K == 0: o["最終判定"] = "全会一致(会議録で確定)"
            elif K <= M: o["最終判定"] = "全会一致(同名議案の数から確定)"
            else: o["最終判定"] = "要確認(会議録は採決あり、議会だよりに賛否表なし)"
        else: o["最終判定"] = "議員別の賛否あり"
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

S2 = ["--- 最終判定の内訳 ---", str(dict(collections.Counter(o["最終判定"] for o in out))), "--- 要確認 ---"]
for o in out:
    if o["最終判定"].startswith("要確認"): S2.append("%s %s %s | %s" % (o["号ID"], o["種別"], o["件名"][:34], o["会議録ファイル"]))
S2.append("--- 会議録で未発見 ---")
for o in out:
    if o["最終判定"].startswith("会議録で未発見"): S2.append("%s %s %s %s" % (o["号ID"], o["種別"], o["結果(議会だより)"], o["件名"][:34]))
open("raw/analysis/summary_minutes_vote_v2.txt", "w", encoding="utf-8").write("\n".join(S2))

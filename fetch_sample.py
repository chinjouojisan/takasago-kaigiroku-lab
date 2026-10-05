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
HEAD_PET = re.compile(r"^[●\s]*(請願及び陳情|請願・陳情|陳情|請願)\s*$")
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
        if "～" in part and len(nums) >= 2:
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

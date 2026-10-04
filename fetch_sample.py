# 高砂市議会 会議録の解析 B10(B6の修正版)(通信は行わない。取得済みの raw/minutes/*.txt を読んで、CSVを作る)
# 出力: raw/analysis/ 以下
#   days.csv            本会議の日ごと(議事日程、質問の種別、見つかった質問数、議席表の人数)
#   seats.csv           日ごとの議席番号と議員名(議員IDつき)
#   blocks.csv          質問のまとまり(1人分): 議員、日付、種別、発言数、答弁者、自己申告の会派、確信度
#   committee_members.csv  委員会ごとの出席委員(委員長・副委員長・委員)
#   unmatched.csv       規則に合わず、人が確認する日・場所
#   labels_sample.txt   発言者表記の種類(規則の調整用)
#   log_parse.txt       実行の記録
import csv
import datetime
import pathlib
import re
import sys
import unicodedata
from collections import Counter

RAW = pathlib.Path("raw")
MIN = RAW / "minutes"
OUT = RAW / "analysis"
OUT.mkdir(parents=True, exist_ok=True)
LOG = []

ROSTER = [
    ("M001", "石崎徹"), ("M002", "入江啓太"), ("M003", "今竹大祐"), ("M004", "岩見明"),
    ("M005", "大西由紀"), ("M006", "川端宏明"), ("M007", "北野誠一郎"), ("M008", "坂本まり"),
    ("M009", "迫川高行"), ("M010", "芝本鎮彰"), ("M011", "島津明香"), ("M012", "鈴木利信"),
    ("M013", "鷹尾治久"), ("M014", "春増勝利"), ("M015", "藤森誠"), ("M016", "松野優也"),
    ("M017", "森秀樹"), ("M018", "山田光昭"), ("M019", "横田英樹"),
]


def log(msg):
    line = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + msg
    print(line, flush=True)
    LOG.append(line)


def nfkc(s):
    return unicodedata.normalize("NFKC", s)


def squash(s):
    """全角・半角の差と空白を消して、名前の比較に使う形にする(石﨑と石崎の違いもNFKCで揃う)。"""
    s = nfkc(s).replace("\ufa11", "崎").replace("髙", "高").replace("\u9ad9", "高")
    return re.sub(r"\s+", "", s)


NAME2ID = {squash(n): i for i, n in ROSTER}
ID2NAME = {i: n for i, n in ROSTER}


def read_meta():
    meta = {}
    p = RAW / "meeting_days.csv"
    if p.exists():
        with open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                meta[r["fileName"]] = r
    return meta


def split_speeches(text):
    """行頭の「○」で発言を区切る。先頭の「開催日」「会議名」の行は別に返す。"""
    lines = text.replace("\r\n", "\n").split("\n")
    head = {}
    i = 0
    while i < len(lines) and not lines[i].startswith("○"):
        m = re.match(r"^(開催日|会議名)：(.*)$", lines[i])
        if m:
            head[m.group(1)] = m.group(2).strip()
        i += 1
    speeches = []
    cur = None
    for ln in lines[i:]:
        if ln.startswith("○"):
            if cur:
                speeches.append(cur)
            rest = ln[1:]
            # 氏名の間に空白がある表記(「岩見 明さん」「副議長（森 秀樹君）」)も1つの発言者表記として扱う
            m = re.match(r"^(\S*[（(][^）)]*[）)])[ 　]?(.*)$", rest) \
                or re.match(r"^(\S{1,4}[ 　]\S{1,4}(?:さん|君))[ 　]?(.*)$", rest) \
                or re.match(r"^(\S+)[ 　]?(.*)$", rest)
            label = m.group(1) if m else rest.strip()
            first = m.group(2) if m else ""
            cur = {"label": label, "lines": [first] if first.strip() else []}
        elif cur is not None:
            cur["lines"].append(ln)
    if cur:
        speeches.append(cur)
    for sp in speeches:
        sp["body"] = "\n".join(sp["lines"]).strip()
    return head, speeches


def label_info(label):
    """発言者表記から (役割, 名前) を返す。役割: chair / member / official / agenda。"""
    l = nfkc(label)
    if l.startswith("議事日程"):
        return "agenda", ""
    m = re.match(r"^(副議長|議長)", l)
    if m:
        n = re.search(r"[（(](.+?)(?:君|さん)[）)]", l)
        return "chair", squash(n.group(1)) if n else ""
    n = re.search(r"[（(](.+?)(?:君|さん)[）)]", l)
    if re.match(r"^\d+番", l) and n:
        return "member", squash(n.group(1))
    m = re.match(r"^(.+?)(?:君|さん)$", l)
    if m and squash(m.group(1)) in NAME2ID:
        return "member", squash(m.group(1))
    if n:
        return "official", squash(n.group(1))
    if m and not re.search(r"(長|員|者|官|監|理事|参事|主幹)$", squash(m.group(1))):
        return "member", squash(m.group(1))  # 役職のない名前だけの表記は議員とみなす(確信度を下げる)
    return "official", squash(l)


def parse_seats(agenda_body):
    seats = {}
    for ln in nfkc(agenda_body).split("\n"):
        m = re.match(r"^\s*(\d{1,2})番\s+(.+?)\s*$", ln)
        if m:
            seats[int(m.group(1))] = squash(m.group(2))
    return seats


def agenda_items(agenda_body):
    items = []
    for ln in nfkc(agenda_body).split("\n"):
        m = re.match(r"^\s*第\s*(\d+)\s+(.+?)\s*$", ln)
        if m:
            items.append(m.group(2).strip())
    return items


CALL = re.compile(r"(\d+)番目、\s*(\d+)番、\s*([^、。]+?)議員")
END = re.compile(r"(質問を終|質問は終|質問を終了)|散会|閉会|延会|日程第\s*[2-9]")


STOP = re.compile(r"(ございます|こんにちは|こんばんは|ありがとう|皆様|皆さん|よろしく|議長|番$|^\d+番|通告|質問)")


def norm_faction(f):
    f = re.sub(r"(高砂市議団|市議団|議員団|議員)$", "", f)
    return f


def claimed_faction(body, name):
    """冒頭200字から、本人が名乗った会派を取り出す。見つからなければ空。name は空白なしの氏名。"""
    head = squash(body)[:200]
    # 1) 氏名の直前の語(「新政会の川端宏明」「民主クラブ山田光昭」「2番、新政会、坂本まり」)
    k = head.find(name)
    if k < 0:
        k = head.find(name[:2])
    if k > 0:
        seg = re.split(r"[。！!？?]", head[:k])[-1]
        seg = re.split(r"、", seg)
        piece = seg[-1] if seg[-1] else (seg[-2] if len(seg) > 1 else "")
        piece = re.sub(r"の$", "", piece)
        piece = re.sub(r"^\d+番", "", piece)
        if 2 <= len(piece) <= 14 and not STOP.search(piece) and piece not in ("会派", "当会派"):
            return norm_faction(piece)
    # 2) 「○○を代表し(て)」
    m = re.search(r"([^、。！!？?\s]{2,14}?)を代表", head)
    if m and not STOP.search(m.group(1)) and m.group(1) not in ("会派", "当会派", "各会派"):
        return norm_faction(m.group(1))
    return ""


def topic_hints(body):
    t = nfkc(body)[:900]
    hs = re.findall(r"[^。\n]{0,60}について[^。\n]{0,30}", t)
    return " / ".join(h.strip() for h in hs[:3])


def analyze_plenary(fn, text, meta, w_days, w_seats, w_blocks, w_unm, labels):
    head, sp = split_speeches(text)
    if not sp:
        w_unm.writerow([fn, "", "発言が見つからない", ""])
        return
    agenda = sp[0]["body"] if sp[0]["label"].startswith("議事日程") else ""
    items = agenda_items(agenda)
    seats = parse_seats(agenda)
    for no, nm in sorted(seats.items()):
        w_seats.writerow([fn, no, nm, NAME2ID.get(nm, "")])
    qtype = ""
    joined = " ".join(items)
    if "総括質問" in joined:
        qtype = "代表質問(会議録上は総括質問)"
    elif "一般質問" in joined:
        qtype = "一般質問"
    for s in sp:
        labels[re.sub(r"[^\s（）()]{1,6}(?=[（(])", "〇〇", nfkc(s["label"]))[:30]] += 1
    infos = [label_info(s["label"]) for s in sp]
    starts = []
    for idx, s in enumerate(sp):
        if infos[idx][0] != "chair":
            continue
        for m in CALL.finditer(nfkc(s["body"])):
            starts.append((idx, int(m.group(1)), int(m.group(2)), squash(m.group(3))))
    # 同じ順番が複数回出る場合は、実際の呼び出し(最後)だけ残す。冒頭の発言順の予告を除くため
    last_of = {}
    for pos, st in enumerate(starts):
        last_of[st[1]] = pos
    starts = [st for pos, st in enumerate(starts) if last_of[st[1]] == pos]
    orders = sorted(st[1] for st in starts)
    if orders and orders != list(range(orders[0], orders[0] + len(orders))):
        w_unm.writerow([fn, head.get("開催日", ""), "質問の順番が連続していない(取りこぼしの疑い)", ",".join(map(str, orders))])
    date = head.get("開催日", "")
    nblocks = 0
    if qtype and not starts:
        w_unm.writerow([fn, date, "質問の日だが、議長の呼び出しが見つからない", joined])
    for k, (idx, order, seat, nm) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(sp)
        found_end = k + 1 < len(starts)
        if k + 1 == len(starts):
            for j in range(idx + 1, len(sp)):
                if infos[j][0] == "chair" and END.search(nfkc(sp[j]["body"])):
                    end = j + 1
                    found_end = True
                    break
        blk = list(range(idx + 1, end))
        member_sp = [j for j in blk if infos[j][0] == "member" and infos[j][1] == nm]
        official_sp = [j for j in blk if infos[j][0] == "official"]
        chars = sum(len(sp[j]["body"]) for j in blk)
        seat_name = seats.get(seat, "")
        flags = []
        conf = 0.95
        if nm not in NAME2ID and seat_name and seat_name.startswith(nm) and seat_name in NAME2ID:
            flags.append("名字だけの呼び出しを議席表で補った(%s→%s)" % (nm, seat_name)); conf -= 0.05
            nm = seat_name
            member_sp = [j for j in blk if infos[j][0] == "member" and infos[j][1] == nm]
        if not qtype:
            flags.append("議事日程に質問の項目がない"); conf -= 0.25
        if seat_name and seat_name != nm:
            flags.append("議席表の名前と呼び出しの名前が違う"); conf -= 0.3
        if not seat_name:
            flags.append("議席表に該当の議席がない"); conf -= 0.2
        if nm not in NAME2ID:
            flags.append("名簿にない名前"); conf -= 0.3
        if not member_sp:
            flags.append("本人の発言が見つからない"); conf -= 0.4
        if not found_end:
            flags.append("終了位置が見つからない(日の終わりまで)"); conf -= 0.15
        first = sp[member_sp[0]]["body"] if member_sp else ""
        faction = claimed_faction(first, nm) if first else ""
        answerers = []
        for j in official_sp:
            lb = nfkc(sp[j]["label"])
            lb = re.sub(r"[（(].*$", "", lb)
            if lb not in answerers:
                answerers.append(lb)
        mid = NAME2ID.get(nm, "")
        w_blocks.writerow([
            "%s-%02d" % (fn, order), fn, date, head.get("会議名", ""), qtype or "(不明)", order, seat, mid, nm,
            faction, idx + 1, end, len(member_sp), len(official_sp), chars,
            " / ".join(answerers[:8]), re.sub(r"\s+", " ", first)[:80], topic_hints(first),
            round(max(conf, 0.05), 2), " ; ".join(flags),
        ])
        nblocks += 1
    w_days.writerow([fn, date, head.get("会議名", ""), joined[:200], qtype, nblocks, len(seats), len(sp)])


ROLE = re.compile(r"(副委員長|委員長|副議長|議長|委員)([^委副議長]+?)(?=副委員長|委員長|副議長|議長|委員|$)")


def analyze_committee(fn, text, meta, w_cm, w_unm):
    head, sp = split_speeches(text)
    body = sp[0]["body"] if sp else text[:3000]
    m = re.search(r"出席委員(.*?)(?:欠席委員|理事者側|協議事項|付議事件)", body, re.S)
    if not m:
        w_unm.writerow([fn, head.get("開催日", ""), "出席委員の欄が見つからない", head.get("会議名", "")])
        return
    s = squash(m.group(1))
    found = ROLE.findall(s)
    if not found:
        w_unm.writerow([fn, head.get("開催日", ""), "出席委員の名前が読み取れない", s[:60]])
        return
    for role, name in found:
        w_cm.writerow([fn, head.get("開催日", ""), head.get("会議名", ""), role, name, NAME2ID.get(name, "")])


def main():
    if not MIN.exists():
        log("raw/minutes がないため終了")
        sys.exit(1)
    meta = read_meta()
    files = sorted(MIN.glob("*.txt"))
    log("対象ファイル %d" % len(files))
    labels = Counter()
    with open(OUT / "days.csv", "w", newline="", encoding="utf-8-sig") as fd, \
         open(OUT / "seats.csv", "w", newline="", encoding="utf-8-sig") as fs, \
         open(OUT / "blocks.csv", "w", newline="", encoding="utf-8-sig") as fb, \
         open(OUT / "committee_members.csv", "w", newline="", encoding="utf-8-sig") as fc, \
         open(OUT / "unmatched.csv", "w", newline="", encoding="utf-8-sig") as fu:
        w_days, w_seats, w_blocks, w_cm, w_unm = map(csv.writer, (fd, fs, fb, fc, fu))
        w_days.writerow(["fileName", "開催日", "会議名", "議事日程(先頭200字)", "質問の種別", "質問のまとまり数", "議席表の人数", "発言数"])
        w_seats.writerow(["fileName", "議席番号", "議員名(正規化)", "議員ID"])
        w_blocks.writerow(["blockID", "fileName", "開催日", "会議名", "種別", "順番", "議席", "議員ID", "議員名(正規化)",
                           "自己申告の会派", "開始発言No", "終了発言No(次の呼び出しまで)", "本人の発言数", "答弁側の発言数",
                           "文字数", "答弁者(役職)", "冒頭80字", "件名の手がかり(「について」を含む文)", "確信度", "注意"])
        w_cm.writerow(["fileName", "開催日", "会議名", "役職", "氏名(正規化)", "議員ID"])
        w_unm.writerow(["fileName", "開催日", "理由", "詳細"])
        nplen = ncom = nerr = 0
        for p in files:
            fn = p.stem
            try:
                text = p.read_text(encoding="utf-8")
                if re.match(r"^R\d{6}A$", fn):
                    analyze_plenary(fn, text, meta, w_days, w_seats, w_blocks, w_unm, labels)
                    nplen += 1
                elif re.match(r"^R\d{6}B\d+$", fn):
                    analyze_committee(fn, text, meta, w_cm, w_unm)
                    ncom += 1
            except Exception as e:
                nerr += 1
                log("ERROR %s: %r" % (fn, e))
                w_unm.writerow([fn, "", "解析中のエラー", repr(e)])
    (OUT / "labels_sample.txt").write_text("\n".join("%6d  %s" % (c, k) for k, c in labels.most_common(60)) + "\n", encoding="utf-8")
    log("本会議 %d日 / 委員会 %d日 / エラー %d" % (nplen, ncom, nerr))
    (OUT / "log_parse.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    write_summary()
    write_faction()


def write_summary():
    """読み取りの確認用に、短い要約を新しい名前のファイルに書く(キャッシュで古い内容が返るのを避けるため)。"""
    import io
    rows = list(csv.DictReader(open(OUT / "blocks.csv", encoding="utf-8-sig", newline="")))
    out = io.StringIO()
    out.write("生成 %s / blocks %d行\n" % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(rows)))
    cnt = {}
    for r in rows:
        k = (r["議員ID"], r["議員名(正規化)"])
        d = cnt.setdefault(k, [0, 0])
        d[1 if r["種別"].startswith("代表") else 0] += 1
    out.write("--- 議員別 (ID 氏名 一般 代表) ---\n")
    for k in sorted(cnt):
        out.write("%s %s 一般%d 代表%d\n" % (k[0] or "(空)", k[1], cnt[k][0], cnt[k][1]))
    out.write("一般計 %d / 代表計 %d\n" % (sum(v[0] for v in cnt.values()), sum(v[1] for v in cnt.values())))
    low = [r for r in rows if r["議員ID"] == "" or float(r["確信度"] or 0) < 0.9]
    out.write("--- 確信度0.9未満・ID空欄: %d件 ---\n" % len(low))
    for r in low:
        out.write("%s %s %s %s\n" % (r["blockID"], r["議員名(正規化)"], r["確信度"], r["注意"]))
    out.write("--- 日ごとの質問数 ---\n")
    per = {}
    for r in rows:
        per[r["fileName"]] = per.get(r["fileName"], 0) + 1
    out.write(" ".join("%s:%d" % (k, v) for k, v in sorted(per.items())) + "\n")
    un = list(csv.DictReader(open(OUT / "unmatched.csv", encoding="utf-8-sig", newline="")))
    out.write("--- unmatched %d件 ---\n" % len(un))
    for r in un:
        out.write("%s %s %s\n" % (r["fileName"], r["理由"], r["詳細"][:40]))
    (OUT / "summary_b10c.txt").write_text(out.getvalue(), encoding="utf-8")




def write_faction():
    rows = list(csv.DictReader(open(OUT / "blocks.csv", encoding="utf-8-sig", newline="")))
    import io
    from collections import defaultdict
    out = io.StringIO()
    out.write("生成 %s / blocks %d行\n" % (datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(rows)))
    names = Counter(r["自己申告の会派"] for r in rows)
    out.write("--- 会派名の出現数 ---\n")
    for k, v in names.most_common():
        out.write("%s %d\n" % (k or "(未検出)", v))
    out.write("--- 議員別の流れ(日付順。同じ会派が続く間は1つにまとめる)。(未)=名乗り未検出 ---\n")
    by = defaultdict(list)
    for r in rows:
        by[(r["議員ID"], r["議員名(正規化)"])].append(r)
    for k in sorted(by):
        rs = sorted(by[k], key=lambda r: r["fileName"])
        runs = []
        for r in rs:
            f = r["自己申告の会派"] or "(未)"
            if runs and runs[-1][0] == f:
                runs[-1][2] = r["fileName"]; runs[-1][3] += 1
            else:
                runs.append([f, r["fileName"], r["fileName"], 1])
        out.write("%s %s: %s\n" % (k[0], k[1], " / ".join("%s %s~%s(%d)" % tuple(x) for x in runs)))
    (OUT / "summary_faction.txt").write_text(out.getvalue(), encoding="utf-8")


main()

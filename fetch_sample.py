# 高砂市議会 会議録検索システムの「調査用B2」
# 目的: (1) 日別の本文ページ (2) 発言のダウンロード機能 (3) 閲覧画面の階層(年→会議→日) の構造を確認する。
# 守ること: 1件ごとに5秒空ける / 取得は最大7件 / robots.txtで禁止なら停止 / CAPTCHAがあれば停止
import datetime
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from urllib.robotparser import RobotFileParser

BASE = "http://www.kensakusystem.jp/takasago/"
INDEX = BASE + "index.html"
CGI = BASE + "cgi-bin2/"
ROBOTS = "http://www.kensakusystem.jp/robots.txt"
UA = "takasago-giin-map-research/0.3 (civic data research, low rate)"
WAIT = 5
OUT = pathlib.Path("raw")
OUT.mkdir(exist_ok=True)
LOG = []


def log(msg):
    line = datetime.datetime.utcnow().isoformat() + "Z " + msg
    print(line)
    LOG.append(line)


def finish(code):
    (OUT / "log_b2.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    sys.exit(code)


def decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp932", errors="replace")


rp = RobotFileParser()
rp.set_url(ROBOTS)
try:
    rp.read()
    log("robots.txt を確認しました")
except Exception as e:
    log("robots.txt の取得に失敗(許可として扱います): " + str(e))


def request(url, name, data=None, soft=True):
    if not rp.can_fetch(UA, url):
        log("robots.txt で禁止されているため停止: " + url)
        finish(1)
    time.sleep(WAIT)
    headers = {"User-Agent": UA}
    body = None
    if data is not None:
        body = urlencode(data, encoding="cp932").encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = BASE + "cgi-bin2/See.exe"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type")
            disp = r.headers.get("Content-Disposition")
    except urllib.error.HTTPError as e:
        log("HTTP %s: %s" % (e.code, url))
        if soft:
            return None
        finish(1)
    except Exception as e:
        log("ERROR %s: %s" % (e, url))
        if soft:
            return None
        finish(1)
    text = decode(raw)
    (OUT / name).write_bytes(raw)
    (OUT / (name + ".utf8.txt")).write_text(text, encoding="utf-8")
    log("OK %s %s disp=%s %d bytes %s %s -> %s" % (status, ctype, disp, len(raw), "POST" if data is not None else "GET", url, name))
    if "captcha" in text.lower():
        log("CAPTCHA らしき記述があるため停止")
        finish(1)
    return text


idx = request(INDEX, "b2_index.html", soft=False)
m = re.search(r"Code=([A-Za-z0-9]+)", idx)
if not m:
    log("Code が見つからないため停止")
    finish(1)
code = m.group(1)
day = "R080312A"  # 令和8年3月12日(B1で確認した本会議の日)

# 1. 日別の本文(B1のフレームに書かれていたURLと同じ形)
request(CGI + "GetText3.exe?%s/%s/83190/10/1//1/%%50%%43%%42/0" % (code, day), "b2_gettext3.html")

# 2. ページ単位の表示(P.651)
request(CGI + "r_PageFrame.exe?%s/%s/651/10/1/1/%%50%%43%%42/0/0" % (code, day), "b2_pageframe651.html")

# 3. 発言のダウンロード機能(画面の「ダウンロード」と同じ送信。発言の位置を2件だけ指定)
request(
    CGI + "GetPerson.exe",
    "b2_getperson.txt",
    data=[("Code", code), ("fileName", day), ("downloadPos", "7794"), ("downloadPos", "8464")],
)

# 4. 閲覧画面の階層: 令和元年〜令和4年のタブ
request(
    CGI + "See.exe",
    "b2_see_r4.html",
    data=[("Code", code), ("treedepth", "令和 4年"), ("page", ""), ("fileName", "")],
)

# 5. 閲覧画面の階層: 令和8年3月定例会(会議日の一覧)
request(
    CGI + "See.exe",
    "b2_see_r8_mar.html",
    data=[("Code", code), ("treedepth", "令和 8年  3月定例会 "), ("page", ""), ("fileName", "")],
)

log("完了")
finish(0)

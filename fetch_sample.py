# 高砂市議会 会議録検索システムの「調査用B1」
# 目的: 検索結果の1件(令和8年3月12日の本会議)を、画面と同じPOST送信で取得し、日別ページの構造を確認する。
# 守ること: 1件ごとに5秒空ける / 取得は最大6件 / robots.txtで禁止なら停止 / CAPTCHAがあれば停止
import datetime
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urljoin
from urllib.robotparser import RobotFileParser

BASE = "http://www.kensakusystem.jp/takasago/"
INDEX = BASE + "index.html"
RESULT_URL = BASE + "cgi-bin2/ResultFrame.exe"
ROBOTS = "http://www.kensakusystem.jp/robots.txt"
UA = "takasago-giin-map-research/0.2 (civic data research, low rate)"
WAIT = 5
OUT = pathlib.Path("raw")
OUT.mkdir(exist_ok=True)
LOG = []


def log(msg):
    line = datetime.datetime.utcnow().isoformat() + "Z " + msg
    print(line)
    LOG.append(line)


def finish(code):
    (OUT / "log_b1.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
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


def request(url, name, data=None):
    if not rp.can_fetch(UA, url):
        log("robots.txt で禁止されているため停止: " + url)
        finish(1)
    time.sleep(WAIT)
    headers = {"User-Agent": UA}
    body = None
    if data is not None:
        body = urlencode(data, encoding="cp932").encode("ascii")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Referer"] = BASE + "cgi-bin2/Search2.exe"
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        log("HTTP %s: %s" % (e.code, url))
        finish(1)
    except Exception as e:
        log("ERROR %s: %s" % (e, url))
        finish(1)
    text = decode(raw)
    (OUT / name).write_bytes(raw)
    (OUT / (name + ".utf8.txt")).write_text(text, encoding="utf-8")
    log("OK %s %s %d bytes %s %s -> %s" % (status, ctype, len(raw), "POST" if data is not None else "GET", url, name))
    if "captcha" in text.lower():
        log("CAPTCHA らしき記述があるため停止")
        finish(1)
    return text


# 1. トップページから Code を取得(値は直接書かない)
idx = request(INDEX, "b1_index.html")
m = re.search(r"Code=([A-Za-z0-9]+)", idx)
if not m:
    log("Code が見つからないため停止")
    finish(1)
code = m.group(1)

# 2. 画面の go('R080312A/83190/1505') と同じ送信(goview フォームの内容)
data = {
    "Code": code,
    "dMode": "0",
    "KeyWord": "PCB",
    "searchMode": "1",
    "keyMode": "10",
    "fromYear": "令和 7年",
    "fromDate": "令和 7年 1月臨時会（第 1日 1月21日）",
    "tillYear": "令和 8年",
    "tillDate": "令和 8年 6月定例会（第 5日 6月22日）",
    "speaker": "",
    "speaker1": "",
    "kaiha": "",
    "speaker2": "",
    "speaker3": "",
    "eTarget": "1",
    "AhitResult": "検索",
    "speakerMode": "1",
    "context": "R080312A/83190/1505",
}
page = request(RESULT_URL, "b1_day_R080312A.html", data=data)

# 3. フレームがあれば最大3つ取得
frames = re.findall(r"""<i?frame[^>]+src=["']([^"']+)["']""", page, re.I)
(OUT / "b1_frames.txt").write_text("\n".join(frames), encoding="utf-8")
log("フレーム数: %d" % len(frames))
for n, src in enumerate(frames[:3], 1):
    request(urljoin(RESULT_URL, src), "b1_frame%d.html" % n)

log("完了")
finish(0)

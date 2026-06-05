#!/usr/bin/env python3
"""Ship Hermes conversation messages from state.db (SQLite) to Loki, so the
Grafana chat panel can show the real per-user conversation. Read-only on the DB.
Resolves Telegram display names via the Bot API (cached) and masks the user id.
Stdlib only."""
import sqlite3, json, time, os, urllib.request
from collections import defaultdict

DB = os.environ.get("STATE_DB", "/hermes/state.db")
LOKI = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
STATE = os.environ.get("STATE_FILE", "/state/last_id")
NAMES = os.environ.get("NAMES_FILE", "/state/names.json")
ENV_FILE = os.environ.get("HERMES_ENV", "/hermes/.env")
INTERVAL = int(os.environ.get("INTERVAL", "8"))

_names = None


def last_id():
    try:
        return int(open(STATE).read().strip())
    except Exception:
        return 0


def save_id(i):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    open(STATE, "w").write(str(i))


def bot_token():
    try:
        for line in open(ENV_FILE):
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def names_cache():
    global _names
    if _names is None:
        try:
            _names = json.load(open(NAMES))
        except Exception:
            _names = {}
    return _names


def mask(uid):
    s = str(uid)
    return s[:-4] + "****" if len(s) > 4 else "****"


def resolve_name(uid, token):
    cache = names_cache()
    if uid in cache:
        return cache[uid] or mask(uid)
    name = ""
    if token:
        try:
            url = f"https://api.telegram.org/bot{token}/getChat?chat_id={uid}"
            d = json.load(urllib.request.urlopen(url, timeout=8))
            if d.get("ok"):
                r = d["result"]
                name = " ".join(x for x in (r.get("first_name"), r.get("last_name")) if x) \
                    or (r.get("username") or "")
        except Exception:
            pass
    cache[uid] = name
    try:
        json.dump(cache, open(NAMES, "w"))
    except Exception:
        pass
    return name or mask(uid)


def push(streams):
    body = json.dumps({"streams": streams}).encode()
    req = urllib.request.Request(LOKI, data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def tick():
    since = last_id()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        rows = con.execute(
            "select m.id, m.role, m.timestamp, m.content, s.user_id "
            "from messages m join sessions s on m.session_id = s.id "
            "where m.id > ? and m.role in ('user','assistant') and m.content <> '' "
            "and s.source = 'telegram' "
            "order by m.id",
            (since,),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return 0
    token = bot_token()
    buckets = defaultdict(list)
    for _id, role, ts, content, uid in rows:
        ns = str(int(float(ts) * 1e9))
        buckets[(role, resolve_name(uid, token), mask(uid))].append([ns, content])
    streams = [
        {"stream": {"source": "hermes_chat", "role": role, "name": name, "uid": uid}, "values": sorted(vals)}
        for (role, name, uid), vals in buckets.items()
    ]
    push(streams)
    save_id(rows[-1][0])
    return len(rows)


if __name__ == "__main__":
    print(f"chat-shipper: DB={DB} LOKI={LOKI} from id {last_id()}", flush=True)
    while True:
        try:
            n = tick()
            if n:
                print(f"shipped {n} messages (now at id {last_id()})", flush=True)
        except Exception as e:
            print("error:", e, flush=True)
        time.sleep(INTERVAL)

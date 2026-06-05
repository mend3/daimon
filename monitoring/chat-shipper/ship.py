#!/usr/bin/env python3
"""Ship Hermes conversation messages from state.db (SQLite) to Loki, so the
Grafana chat panel can show the real user/assistant text. Read-only on the DB;
tracks the last shipped message id in /state. Stdlib only."""
import sqlite3, json, time, os, urllib.request
from collections import defaultdict

DB = os.environ.get("STATE_DB", "/hermes/state.db")
LOKI = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
STATE = os.environ.get("STATE_FILE", "/state/last_id")
INTERVAL = int(os.environ.get("INTERVAL", "8"))


def last_id():
    try:
        return int(open(STATE).read().strip())
    except Exception:
        return 0


def save_id(i):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    open(STATE, "w").write(str(i))


def push(streams):
    body = json.dumps({"streams": streams}).encode()
    req = urllib.request.Request(LOKI, data=body, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def tick():
    since = last_id()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
    try:
        rows = con.execute(
            "select id, role, timestamp, content from messages "
            "where id > ? and role in ('user','assistant') and content <> '' "
            "order by id",
            (since,),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return 0
    buckets = defaultdict(list)
    for _id, role, ts, content in rows:
        ns = str(int(float(ts) * 1e9))
        buckets[role].append([ns, content])
    streams = [
        {"stream": {"source": "hermes_chat", "role": role}, "values": sorted(vals)}
        for role, vals in buckets.items()
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

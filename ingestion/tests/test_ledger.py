"""SqliteLedger behavior — notably that rows are scoped per (source_id, capability),
so the same URL ingested through two capabilities keeps both rows."""
import sqlite3

from ella_kb.core.ledger import SqliteLedger


def test_rows_scoped_by_source_and_capability(tmp_path):
    led = SqliteLedger(str(tmp_path / "l.db"))
    common = dict(source_id="url:x", uri="u", user_id="owner", chunk_count=1,
                  status="indexed", text="t")
    led.record(capability="feeds", title="A", content_hash="h1", now=1, **common)
    led.record(capability="urls", title="B", content_hash="h2", now=2, **common)

    assert led.get("url:x", "feeds").title == "A"
    assert led.get("url:x", "urls").title == "B"     # both coexist, no overwrite


def test_migrates_legacy_single_pk_schema(tmp_path):
    # Simulate a ledger created before the composite key (source_id PRIMARY KEY only).
    p = tmp_path / "legacy.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE sources (source_id TEXT PRIMARY KEY, capability TEXT NOT NULL, "
               "uri TEXT, title TEXT, content_hash TEXT NOT NULL, user_id TEXT DEFAULT 'owner', "
               "chunk_count INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', text TEXT, "
               "created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
    db.execute("INSERT INTO sources VALUES ('url:x','feeds','u','A','h1','owner',1,'indexed','t',1,1)")
    db.commit()
    db.close()

    led = SqliteLedger(str(p))                       # opening migrates the schema
    assert led.get("url:x", "feeds").title == "A"    # legacy row preserved
    # the composite-key upsert now works (would raise on the old single-PK table)
    led.record(source_id="url:x", capability="urls", uri="u", title="B", content_hash="h2",
               user_id="owner", chunk_count=1, status="indexed", text="t", now=2)
    assert led.get("url:x", "urls").title == "B"


def test_delete_and_is_unchanged_are_capability_scoped(tmp_path):
    led = SqliteLedger(str(tmp_path / "l.db"))
    common = dict(source_id="url:x", uri="u", user_id="owner", chunk_count=1,
                  status="indexed", text="t")
    led.record(capability="feeds", title="A", content_hash="h1", now=1, **common)
    led.record(capability="urls", title="B", content_hash="h2", now=2, **common)

    led.delete("url:x", "feeds")
    assert led.get("url:x", "feeds") is None
    assert led.get("url:x", "urls").title == "B"     # the other capability survives

    assert led.is_unchanged("url:x", "h2", "urls")
    assert not led.is_unchanged("url:x", "h2", "feeds")

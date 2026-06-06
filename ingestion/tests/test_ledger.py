"""SqliteLedger behavior — notably that rows are scoped per (source_id, capability),
so the same URL ingested through two capabilities keeps both rows."""
from ella_kb.core.ledger import SqliteLedger


def test_rows_scoped_by_source_and_capability(tmp_path):
    led = SqliteLedger(str(tmp_path / "l.db"))
    common = dict(source_id="url:x", uri="u", user_id="owner", chunk_count=1,
                  status="indexed", text="t")
    led.record(capability="feeds", title="A", content_hash="h1", now=1, **common)
    led.record(capability="urls", title="B", content_hash="h2", now=2, **common)

    assert led.get("url:x", "feeds").title == "A"
    assert led.get("url:x", "urls").title == "B"     # both coexist, no overwrite


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

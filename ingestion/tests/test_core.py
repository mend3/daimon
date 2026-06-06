from ella_kb.core.chunk import chunk_text
from ella_kb.core.ids import canonical_url, content_hash, point_id, source_id_for_url
from ella_kb.core.security import SSRFGuard, SSRFError, SecretRedactor


def test_canonical_url_strips_tracking_and_fragment():
    a = canonical_url("https://Example.com/Post/?utm_source=x&id=7#frag")
    b = canonical_url("https://example.com/Post?id=7")
    assert a == b


def test_source_id_stable_across_tracking():
    assert source_id_for_url("https://x.io/a?utm_medium=1") == source_id_for_url("https://x.io/a")


def test_content_hash_ignores_whitespace():
    assert content_hash("hello   world\n") == content_hash("hello world")


def test_point_id_deterministic():
    assert point_id("url:abc", 3) == point_id("url:abc", 3)
    assert point_id("url:abc", 3) != point_id("url:abc", 4)


def test_chunking_respects_size_and_covers_text():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(8))
    chunks = chunk_text(text, target_chars=400, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)  # target + overlap slack


def test_chunking_short_text_single_chunk():
    assert chunk_text("just a little note") == ["just a little note"]


def test_ssrf_blocks_private_and_bad_scheme():
    g = SSRFGuard()
    for bad in ["http://127.0.0.1/x", "http://169.254.169.254/latest", "file:///etc/passwd"]:
        try:
            g.check(bad)
            assert False, f"should have blocked {bad}"
        except SSRFError:
            pass


def test_secret_redactor():
    out = SecretRedactor().redact("key sk-ABCDEF0123456789ABCD and ghp_ABCDEFGHIJKLMNOPQRSTUVWX")
    assert "sk-ABCDEF" not in out and "ghp_" not in out
    assert "[REDACTED]" in out

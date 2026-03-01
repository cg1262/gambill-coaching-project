from main import _chunk_text


def test_chunk_text_splits_long_content():
    content = "\n".join([f"line {i} " + ("x" * 120) for i in range(20)])
    chunks = _chunk_text(content, max_len=300)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)

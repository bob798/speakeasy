import pytest


def test_explain_request_accepts_source_fields():
    """直接实例化 model：扩展前缺字段会 AttributeError，扩展后 OK。"""
    from app.routers.articles import ExplainRequest
    req = ExplainRequest(
        text="Hello", kind="word", context="",
        source_type="article", source_ref="ep-1", item_type="word",
        series="bbc_eaw",
    )
    assert req.source_type == "article"
    assert req.source_ref == "ep-1"
    assert req.item_type == "word"


def test_stream_request_accepts_source_fields():
    from app.routers.articles import StreamExplainRequest
    req = StreamExplainRequest(
        text="Hello world.", source_type="article",
        source_ref="ep-1", item_type="sentence", context="paragraph context",
        series="bbc_eaw",
    )
    assert req.source_type == "article"
    assert req.context == "paragraph context"


def test_explain_request_omits_new_fields_defaults_none():
    """旧客户端不传新字段也应该正常解析。"""
    from app.routers.articles import ExplainRequest
    req = ExplainRequest(text="Hi", kind="word")
    assert req.source_type is None
    assert req.source_ref is None
    assert req.item_type is None

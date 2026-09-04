"""采集器解析函数测试（纯函数，无需数据库）"""
from collectors.amazon_bestseller import _parse_price, _parse_rating, _parse_int, _parse_rank


def test_parse_price():
    assert _parse_price("$1,234.56") == 1234.56
    assert _parse_price("$99") == 99.0
    assert _parse_price(None) is None
    assert _parse_price("") is None
    assert _parse_price("暂无价格") is None


def test_parse_rating():
    assert _parse_rating("4.5 out of 5 stars") == 4.5
    assert _parse_rating("4.8 out of 5") == 4.8
    assert _parse_rating(None) is None


def test_parse_int():
    assert _parse_int("1,234") == 1234
    assert _parse_int("567 ratings") == 567
    assert _parse_int(None) is None


def test_parse_rank():
    assert _parse_rank("#1") == 1
    assert _parse_rank("#42 in Kitchen") == 42
    assert _parse_rank(None) is None

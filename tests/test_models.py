from app.core.models.request import HttpMethod, RequestDef, RequestParam


def test_request_def_creation():
    req = RequestDef(
        id="r1",
        name="Test",
        method=HttpMethod.GET,
        url="https://example.com",
    )
    assert req.id == "r1"
    assert req.method == HttpMethod.GET
    assert req.headers == []
    assert req.query_params == []


def test_request_def_with_params():
    req = RequestDef(
        id="r1",
        name="Test",
        method=HttpMethod.POST,
        url="https://example.com/api",
        headers=[RequestParam(key="Content-Type", value="application/json")],
        query_params=[RequestParam(key="page", value="1")],
        body='{"key": "value"}',
    )
    assert len(req.headers) == 1
    assert req.headers[0].key == "Content-Type"
    assert len(req.query_params) == 1
    assert req.body == '{"key": "value"}'


def test_http_method_enum():
    assert HttpMethod.GET == "GET"
    assert HttpMethod.POST == "POST"
    assert HttpMethod.DELETE == "DELETE"

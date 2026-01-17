import testbase

from automojo.restclient.base.restapigroup import RestApiGroup


class _ClientStub:
    pass


class _WithFromDict:
    def __init__(self):
        raise RuntimeError("init should not be called")

    @classmethod
    def from_dict(cls, data):
        return {"parsed": data}


class _WithoutFromDict:
    def __init__(self, **kwargs):
        self.data = kwargs
        return


class _FromDictRaises:
    @classmethod
    def from_dict(cls, data):
        raise ValueError("bad data")


def test_restapigroup_client_returns_client():
    client = _ClientStub()
    group = RestApiGroup(client)
    testbase.assert_equal(group.client is client, True)
    return


def test_restapigroup_parse_item_uses_from_dict():
    group = RestApiGroup(_ClientStub())
    result = group._parse_item({"alpha": 1}, _WithFromDict)
    testbase.assert_equal(result, {"parsed": {"alpha": 1}})
    return


def test_restapigroup_parse_item_constructs_type_without_from_dict():
    group = RestApiGroup(_ClientStub())
    result = group._parse_item({"alpha": 1}, _WithoutFromDict)
    testbase.assert_equal(isinstance(result, _WithoutFromDict), True)
    testbase.assert_equal(result.data, {"alpha": 1})
    return


def test_restapigroup_parse_item_returns_raw_dict_on_failure():
    group = RestApiGroup(_ClientStub())
    payload = {"alpha": 1}
    result = group._parse_item(payload, _FromDictRaises)
    testbase.assert_equal(result, payload)
    return

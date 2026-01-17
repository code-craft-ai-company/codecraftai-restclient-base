import dataclasses

import testbase

from automojo.restclient.base.restclientutils import convert_to_foundation_datatype
from automojo.restclient.base.restclientutils import normalize_query_arg_value


@dataclasses.dataclass
class _SampleData:
    alpha: str
    beta: int


class _AsDict:
    def __init__(self, value: str):
        self._value = value
        return

    def as_dict(self) -> dict:
        return {"value": self._value}


def test_normalize_query_arg_value_int_is_passthrough():
    result = normalize_query_arg_value(42)
    testbase.assert_equal(result, 42)
    return


def test_normalize_query_arg_value_quotes_string():
    result = normalize_query_arg_value("alpha beta")
    testbase.assert_equal(result, "alpha%20beta")
    return


def test_convert_to_foundation_datatype_handles_dataclass():
    sample = _SampleData(alpha="one", beta=2)
    result = convert_to_foundation_datatype(sample)
    testbase.assert_equal(result, {"alpha": "one", "beta": 2})
    return


def test_convert_to_foundation_datatype_handles_as_dict():
    sample = _AsDict("value")
    result = convert_to_foundation_datatype(sample)
    testbase.assert_equal(result, {"value": "value"})
    return


def test_convert_to_foundation_datatype_passthroughs_primitives():
    testbase.assert_equal(convert_to_foundation_datatype("alpha"), "alpha")
    testbase.assert_equal(convert_to_foundation_datatype(10), 10)
    testbase.assert_equal(convert_to_foundation_datatype({"alpha": 1}), {"alpha": 1})
    return


def test_convert_to_foundation_datatype_converts_sequences_recursively():
    sample = _SampleData(alpha="one", beta=2)
    payload = [sample, _AsDict("value"), ("alpha", 3), ["nested"]]
    result = convert_to_foundation_datatype(payload)
    expected = [{"alpha": "one", "beta": 2}, {"value": "value"}, ["alpha", 3], ["nested"]]
    testbase.assert_equal(result, expected)
    return


def test_convert_to_foundation_datatype_raises_for_unknown_type():
    error = None

    try:
        convert_to_foundation_datatype(object())
    except ValueError as err:
        error = err

    testbase.assert_equal(error is not None, True)
    if error is not None:
        msg_index = str(error).find("Unable to convert value of type=")
        testbase.assert_equal(msg_index >= 0, True)
    return

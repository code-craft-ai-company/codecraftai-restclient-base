from automojo import testbase

from automojo.restclient.base.schemafield import Field


class _FieldHost:
    alpha = Field(str, required=True)
    beta = Field(int, default=5)
    gamma = Field("CustomType")


def test_schemafield_descriptor_sets_name():
    testbase.assert_equal(_FieldHost.alpha.name, "alpha")
    testbase.assert_equal(_FieldHost.beta.name, "beta")
    testbase.assert_equal(_FieldHost.gamma.name, "gamma")
    return


def test_schemafield_class_access_returns_descriptor():
    testbase.assert_equal(isinstance(_FieldHost.alpha, Field), True)
    testbase.assert_equal(_FieldHost.alpha.required, True)
    return


def test_schemafield_get_and_set_round_trip():
    host = _FieldHost()

    testbase.assert_equal(host.alpha, None)
    testbase.assert_equal(host.beta, 5)

    host.alpha = "value"
    host.beta = 10

    testbase.assert_equal(host.alpha, "value")
    testbase.assert_equal(host.beta, 10)
    testbase.assert_equal(host.__dict__["alpha"], "value")
    testbase.assert_equal(host.__dict__["beta"], 10)
    return


def test_schemafield_repr_includes_type_and_required_flag():
    testbase.assert_equal(repr(_FieldHost.alpha), "Field(str, required)")
    testbase.assert_equal(repr(_FieldHost.beta), "Field(int, optional)")
    testbase.assert_equal(repr(_FieldHost.gamma), "Field(CustomType, optional)")
    return

from ccai import testbase

from ccai.restclient.base.schemafield import Field
from ccai.restclient.base.schemaobject import SchemaObject


class _SimpleSchema(SchemaObject):
    required_value = Field(str, required=True)
    optional_value = Field(int)
    default_value = Field(str, default="default")


class _ChildSchema(SchemaObject):
    name = Field(str)


class _ContainerSchema(SchemaObject):
    child = Field(_ChildSchema)
    children = Field(list)
    mapping = Field(dict)


def test_schemaobject_field_registry_records_fields():
    field_names = list(_SimpleSchema._fields.keys())
    testbase.assert_equal(field_names, ["required_value", "optional_value", "default_value"])
    testbase.assert_equal(_SimpleSchema.required_value.name, "required_value")
    testbase.assert_equal(_SimpleSchema.optional_value.name, "optional_value")
    testbase.assert_equal(_SimpleSchema.default_value.name, "default_value")
    return


def test_schemaobject_init_sets_defaults_and_extras():
    obj = _SimpleSchema(required_value="alpha", extra_field=10)
    testbase.assert_equal(obj.required_value, "alpha")
    testbase.assert_equal(obj.optional_value, None)
    testbase.assert_equal(obj.default_value, "default")
    testbase.assert_equal(obj.extra_field, 10)
    return


def test_schemaobject_to_dict_skips_optional_none_and_includes_required_none():
    obj = _SimpleSchema(required_value=None, extra_field="skip-me")
    result = obj.to_dict()
    testbase.assert_equal("required_value" in result, True)
    testbase.assert_equal(result["required_value"], None)
    testbase.assert_equal("optional_value" in result, False)
    testbase.assert_equal("default_value" in result, True)
    testbase.assert_equal("extra_field" in result, False)
    return


def test_schemaobject_to_dict_handles_nested_schemaobjects():
    child = _ChildSchema(name="one")
    container = _ContainerSchema(
        child=child,
        children=[_ChildSchema(name="two"), "raw"],
        mapping={"first": _ChildSchema(name="three"), "count": 1},
    )

    result = container.to_dict()

    expected = {
        "child": {"name": "one"},
        "children": [{"name": "two"}, "raw"],
        "mapping": {"first": {"name": "three"}, "count": 1},
    }
    testbase.assert_equal(result, expected)
    return


def test_schemaobject_from_dict_creates_instance_and_passthroughs_non_dict():
    obj = _SimpleSchema.from_dict({"required_value": "value", "optional_value": 3})
    testbase.assert_equal(isinstance(obj, _SimpleSchema), True)
    testbase.assert_equal(obj.required_value, "value")
    testbase.assert_equal(obj.optional_value, 3)

    passthrough = _SimpleSchema.from_dict("value")
    testbase.assert_equal(passthrough, "value")
    return


def test_schemaobject_repr_and_eq():
    obj1 = _SimpleSchema(required_value="alpha", optional_value=2)
    obj2 = _SimpleSchema(required_value="alpha", optional_value=2)
    obj3 = _SimpleSchema(required_value="alpha", optional_value=3)

    expected_repr = "_SimpleSchema(required_value='alpha', optional_value=2, default_value='default')"
    testbase.assert_equal(repr(obj1), expected_repr)
    testbase.assert_equal(obj1 == obj2, True)
    testbase.assert_equal(obj1 == obj3, False)
    testbase.assert_equal(obj1 == "alpha", False)
    return

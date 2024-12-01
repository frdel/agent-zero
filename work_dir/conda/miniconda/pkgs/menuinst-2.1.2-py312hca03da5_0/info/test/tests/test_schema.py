import pytest
from conftest import DATA

# from hypothesis import given, settings, HealthCheck
# from hypothesis_jsonschema import from_schema
from pydantic import ValidationError as ValidationErrorV2
from pydantic.v1 import ValidationError as ValidationErrorV1

from menuinst._schema import BasePlatformSpecific, MenuItem, validate

# # suppress_health_check=3 --> too_slow
# @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
# @given(from_schema(MenuInstSchema.schema()))
# def test_schema_can_be_loaded(value):
#     assert value


@pytest.mark.parametrize(
    "path", [pytest.param(path, id=path.name) for path in sorted((DATA / "jsons").glob("*.json"))]
)
def test_examples(path):
    if "invalid" in path.name:
        with pytest.raises((ValidationErrorV1, ValidationErrorV2)):
            assert validate(path)
    else:
        assert validate(path)


def test_MenuItemMetadata_synced_with_OptionalMenuItemMetadata():
    fields_as_required = MenuItem.__fields__.copy()
    fields_as_required.pop("platforms", None)
    fields_as_optional = BasePlatformSpecific.__fields__
    assert fields_as_required.keys() == fields_as_optional.keys()
    for (_, required), (_, optional) in zip(
        sorted(fields_as_required.items()), sorted(fields_as_optional.items())
    ):
        assert required.field_info.description == optional.field_info.description

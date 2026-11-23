from orion_core.root_signature import (
    DescriptorRange, RootParameter, RootSignatureDescription, assess_root_signature,
)


def test_valid_descriptor_table_root_signature():
    desc = RootSignatureDescription((RootParameter(
        "descriptor_table", ranges=(DescriptorRange("srv", 8),)),))
    result = assess_root_signature(desc)
    assert result["status"] == "native_validation_needed"
    assert result["root_cost_dwords"] == 1
    assert result["root_signature_created"] is False


def test_root_constants_cost_and_zero_rejected():
    good = RootSignatureDescription((RootParameter("root_constants", num_32bit_values=4),))
    assert good.root_cost_dwords() == 4
    bad = RootSignatureDescription((RootParameter("root_constants"),))
    assert "parameter 0: root constants must contain at least one 32-bit value" in bad.validate()


def test_root_signature_cost_limit():
    desc = RootSignatureDescription(tuple(
        RootParameter("root_constants", num_32bit_values=33) for _ in range(2)))
    assert "root signature cost exceeds the 64-DWORD limit" in desc.validate()


def test_empty_descriptor_table_is_invalid():
    desc = RootSignatureDescription((RootParameter("descriptor_table"),))
    assert assess_root_signature(desc)["status"] == "invalid_description"

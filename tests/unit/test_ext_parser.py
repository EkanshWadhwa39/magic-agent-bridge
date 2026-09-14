"""Unit tests for ext_parser.py — fully offline, no Magic session required."""

import json
import pytest

from magic_agent_bridge.ext_parser import ExtParseError, parse_ext, parse_ext_text


class TestHeaderParsing:
    def test_version(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["version"] == "8.3"

    def test_tech(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["tech"] == "scmos"

    def test_timestamp(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["timestamp"] == 907716988

    def test_scale_int_scale(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["scale"]["int_scale"] == 1000

    def test_scale_res_scale(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["scale"]["res_scale"] == 1

    def test_scale_cap_scale(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["meta"]["scale"]["cap_scale"] == 9

    def test_resistclasses_is_list_of_ints(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        rc = d["meta"]["resistclasses"]
        assert isinstance(rc, list)
        assert all(isinstance(v, int) for v in rc)

    def test_resistclasses_length(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert len(d["meta"]["resistclasses"]) == 13

    def test_style_is_string(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert isinstance(d["meta"]["style"], str)
        assert len(d["meta"]["style"]) > 0


class TestNodeParsing:
    def test_node_count_inverter_v3(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert len(d["nodes"]) == 4  # GND, out, in, Vdd

    def test_node_count_inverter(self, inverter_ext):
        d = parse_ext(inverter_ext)
        assert len(d["nodes"]) == 5  # gnd, out, vdd, in, w_n8_n5#

    def test_node_names_unquoted(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        names = [n["name"] for n in d["nodes"]]
        assert "GND" in names
        assert "out" in names
        assert "in" in names
        assert "Vdd" in names

    def test_node_names_no_quotes(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for n in d["nodes"]:
            assert not n["name"].startswith('"')
            assert not n["name"].endswith('"')

    def test_node_cap_is_float(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for node in d["nodes"]:
            assert isinstance(node["cap_ff"], float)

    def test_node_has_integer_coords(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for node in d["nodes"]:
            assert isinstance(node["x"], int)
            assert isinstance(node["y"], int)

    def test_node_layer_is_string(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for node in d["nodes"]:
            assert isinstance(node["layer"], str)

    def test_auto_named_node_parsed(self, inverter_ext):
        d = parse_ext(inverter_ext)
        names = [n["name"] for n in d["nodes"]]
        assert "w_n8_n5#" in names


class TestCapParsing:
    def test_cap_count_inverter_v3(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert len(d["caps"]) == 5

    def test_cap_nodes_are_strings(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for c in d["caps"]:
            assert isinstance(c["node_a"], str)
            assert isinstance(c["node_b"], str)

    def test_cap_nodes_unquoted(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for c in d["caps"]:
            assert not c["node_a"].startswith('"')
            assert not c["node_b"].startswith('"')

    def test_cap_in_out_value(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        cap = next(c for c in d["caps"] if c["node_a"] == "in" and c["node_b"] == "out")
        assert cap["value_ff"] == pytest.approx(57.92)

    def test_cap_vdd_out_value(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        cap = next(c for c in d["caps"] if c["node_a"] == "Vdd" and c["node_b"] == "out")
        assert cap["value_ff"] == pytest.approx(244.439)


class TestSubcapParsing:
    def test_subcap_present_in_test_ext(self, test_ext):
        d = parse_ext(test_ext)
        assert len(d["subcaps"]) > 0

    def test_subcap_count_in_test_ext(self, test_ext):
        d = parse_ext(test_ext)
        assert len(d["subcaps"]) == 4  # gnd, vdd, in, w_n2_n3#

    def test_subcap_absent_in_inverter_v3(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert d["subcaps"] == []

    def test_subcap_value_is_float(self, test_ext):
        d = parse_ext(test_ext)
        for s in d["subcaps"]:
            assert isinstance(s["value_ff"], float)

    def test_subcap_value_can_be_negative(self, test_ext):
        d = parse_ext(test_ext)
        assert any(s["value_ff"] < 0 for s in d["subcaps"])

    def test_subcap_node_unquoted(self, test_ext):
        d = parse_ext(test_ext)
        for s in d["subcaps"]:
            assert not s["node"].startswith('"')


class TestFetParsing:
    def test_has_nfet_and_pfet(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        types = {f["type"] for f in d["fets"]}
        assert "nfet" in types
        assert "pfet" in types

    def test_exactly_two_fets_in_inverter(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        assert len(d["fets"]) == 2

    def test_fet_gate_unquoted(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        nfet = next(f for f in d["fets"] if f["type"] == "nfet")
        assert nfet["gate"] == "in"

    def test_fet_source_drain_unquoted(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        nfet = next(f for f in d["fets"] if f["type"] == "nfet")
        assert nfet["source"] == "GND"
        assert nfet["drain"] == "out"

    def test_fet_geometry_is_int(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for f in d["fets"]:
            assert isinstance(f["width"], int)
            assert isinstance(f["length"], int)
            assert isinstance(f["x1"], int)
            assert isinstance(f["y1"], int)

    def test_fet_substrate_unquoted(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        for f in d["fets"]:
            assert not f["substrate"].startswith('"')

    def test_area_field_stored_as_string(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        pfet = next(f for f in d["fets"] if f["type"] == "pfet")
        assert isinstance(pfet.get("source_area", ""), str)


class TestJsonSerialisation:
    def test_inverter_v3_is_json_serialisable(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        dumped = json.dumps(d)
        assert len(dumped) > 0

    def test_test_ext_is_json_serialisable(self, test_ext):
        d = parse_ext(test_ext)
        json.dumps(d)

    def test_inverter_ext_is_json_serialisable(self, inverter_ext):
        d = parse_ext(inverter_ext)
        json.dumps(d)

    def test_roundtrip_preserves_node_count(self, inverter_v3_ext):
        d = parse_ext(inverter_v3_ext)
        restored = json.loads(json.dumps(d))
        assert len(restored["nodes"]) == len(d["nodes"])


class TestErrorHandling:
    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_ext(tmp_path / "nonexistent.ext")

    def test_malformed_node_raises_ext_parse_error(self, malformed_ext):
        with pytest.raises(ExtParseError):
            parse_ext(malformed_ext)

    def test_ext_parse_error_is_value_error_subclass(self, malformed_ext):
        with pytest.raises(ValueError):
            parse_ext(malformed_ext)

    def test_empty_string_returns_empty_sections(self):
        d = parse_ext_text("")
        assert d["nodes"] == []
        assert d["caps"] == []
        assert d["subcaps"] == []
        assert d["fets"] == []
        assert d["meta"] == {}

    def test_only_comments_whitespace_returns_empty(self):
        d = parse_ext_text("\n\n   \n")
        assert d["nodes"] == []

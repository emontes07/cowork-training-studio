import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
from zipfile import ZipFile

from mcp.types import Tool
from jsonschema import Draft202012Validator
from PIL import Image
import pytest

from scripts import build_plugin as builder

SOURCE = Path(__file__).resolve().parents[1] / "plugin"
SKILL = "skills/build-training-lab/SKILL.md"


@pytest.fixture
def tools():
    return [{
        "name": name, "description": f"Fictional test description for {name}.",
        "inputSchema": {
            "type": "object",
            "properties": {"spec": {"type": "object"}} if name in {"validate_lab_spec", "render_lab_page"} else {},
        },
        "outputSchema": {"type": "object", "x-test": True},
        "annotations": {"readOnlyHint": True},
    } for name in sorted(builder.EXPECTED_TOOLS)]


@pytest.fixture
def package_files(tools):
    template = (SOURCE / "manifest.template.json").read_text(encoding="utf-8")
    manifest = builder.fill_manifest(template, "https://mcp.example.test")
    return {
        "manifest.json": json.dumps(manifest).encode(),
        "mcp-tools.json": json.dumps({"tools": tools}).encode(),
        SKILL: (SOURCE / SKILL).read_bytes(),
        **builder.generate_icons(),
    }


@pytest.mark.parametrize(("url", "expected"), [
    ("https://mcp.example.test", "https://mcp.example.test/mcp"),
    ("https://mcp.example.test/", "https://mcp.example.test/mcp"),
    ("https://mcp.example.test/mcp", "https://mcp.example.test/mcp"),
    ("https://mcp.example.test/mcp/", "https://mcp.example.test/mcp"),
    ("https://mcp.example.test:8443/api", "https://mcp.example.test:8443/api/mcp"),
])
def test_normalize_mcp_url(url, expected):
    assert builder.normalize_mcp_url(url) == expected


@pytest.mark.parametrize("url", [
    "http://mcp.example.test", "https://", "https://user:pass@mcp.example.test",
    "https://mcp.example.test/mcp?token=example", "https://mcp.example.test/#fragment",
    "https://mcp.example.test/\n", "https://mcp.example.test\\mcp",
    "https://mcp.example.test:70000", "https://mcp.example.test/" + "a" * 2048,
])
def test_invalid_mcp_urls_fail(url):
    with pytest.raises(ValueError):
        builder.normalize_mcp_url(url)


def test_template_fill_preserves_source_and_fixed_id():
    template = (SOURCE / "manifest.template.json").read_text(encoding="utf-8")
    result = builder.fill_manifest(template, "https://mcp.example.test")
    remote = result["agentConnectors"][0]["toolSource"]["remoteMcpServer"]
    assert remote["mcpServerUrl"] == "https://mcp.example.test/mcp"
    assert remote["authorization"] == {"type": "None"}
    assert result["id"] == json.loads(template)["id"]
    assert builder.PLACEHOLDER in (SOURCE / "manifest.template.json").read_text(encoding="utf-8")
    for bad in (template.replace(builder.PLACEHOLDER, "missing"), template + template):
        with pytest.raises(ValueError, match="exactly one"):
            builder.fill_manifest(bad, "https://mcp.example.test")


@pytest.mark.parametrize(("section", "field", "limit"), [
    ("name", "short", 30), ("name", "full", 100), ("description", "short", 80),
    ("description", "full", 4000), ("developer", "name", 32),
])
def test_manifest_text_length_boundaries(package_files, section, field, limit):
    manifest = json.loads(package_files["manifest.json"])
    manifest[section][field] = "x" * limit
    package_files["manifest.json"] = json.dumps(manifest).encode()
    builder.validate_package(package_files)
    manifest[section][field] += "x"
    package_files["manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError, match=f"{section}.{field}"):
        builder.validate_package(package_files)


@pytest.mark.parametrize("failure", [
    "json", "guid", "version", "connector_id", "connector_name",
    "skill_path", "missing_skill", "front_matter", "skill_name", "skill_description", "long_skill",
])
def test_invalid_manifest_and_skill_cases(package_files, failure):
    manifest = json.loads(package_files["manifest.json"])
    if failure == "json":
        package_files["manifest.json"] = b"{broken"
    elif failure == "guid":
        manifest["id"] = "not-a-guid"
    elif failure == "version":
        manifest["version"] = "../unsafe"
    elif failure == "connector_id":
        manifest["agentConnectors"][0]["id"] = "x" * 65
    elif failure == "connector_name":
        manifest["agentConnectors"][0]["displayName"] = "x" * 129
    elif failure == "skill_path":
        manifest["agentSkills"][0]["folder"] = "../outside"
    elif failure == "missing_skill":
        del package_files[SKILL]
    elif failure == "front_matter":
        package_files[SKILL] = b"# No front matter\n"
    elif failure == "skill_name":
        package_files[SKILL] = package_files[SKILL].replace(b"name: build-training-lab", b"name: wrong-name")
    elif failure == "skill_description":
        package_files[SKILL] = package_files[SKILL].replace(b"description:", b"missing-description:", 1)
    else:
        package_files[SKILL] += b"\nextra" * 121
    if failure != "json":
        package_files["manifest.json"] = json.dumps(manifest).encode()
    with pytest.raises(ValueError):
        builder.validate_package(package_files)


@pytest.mark.parametrize("line_count", [150, 151])
def test_skill_line_limit(package_files, line_count):
    lines = package_files[SKILL].decode().splitlines()
    package_files[SKILL] = ("\n".join(lines + ["Practice detail."] * (line_count - len(lines))) + "\n").encode()
    if line_count == 150:
        builder.validate_package(package_files)
    else:
        with pytest.raises(ValueError, match="exceeds 150 lines"):
            builder.validate_package(package_files)


@pytest.mark.parametrize("failure", ["size", "opaque", "colored"])
def test_invalid_icons_fail(package_files, failure):
    if failure == "size":
        image = Image.new("RGB", (64, 64), "blue")
        name = "color.png"
    else:
        image = Image.new("RGBA", (32, 32), (255, 255, 255, 255 if failure == "opaque" else 0))
        if failure == "colored":
            image.putpixel((16, 16), (0, 0, 255, 255))
        name = "outline.png"
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    package_files[name] = buffer.getvalue()
    with pytest.raises(ValueError, match="icon"):
        builder.validate_package(package_files)


@pytest.mark.parametrize("failure", ["count", "duplicate", "output_schema"])
def test_invalid_tool_catalogs_fail(package_files, failure):
    catalog = json.loads(package_files["mcp-tools.json"])
    if failure == "count":
        catalog["tools"].pop()
    elif failure == "duplicate":
        catalog["tools"][0] = deepcopy(catalog["tools"][1])
    else:
        del catalog["tools"][0]["outputSchema"]
    package_files["mcp-tools.json"] = json.dumps(catalog).encode()
    with pytest.raises(ValueError):
        builder.validate_package(package_files)


def test_live_tool_projection_uses_response_metadata(monkeypatch, tools):
    class Client:
        def __init__(self, transport, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def list_tools(self):
            return [Tool.model_validate({**tool, "title": "Not exported", "_meta": {"extra": True}}) for tool in tools]

    monkeypatch.setattr(builder, "Client", Client)
    assert asyncio.run(builder.fetch_tools("https://mcp.example.test/mcp/")) == tools


@pytest.mark.parametrize("raw_schemas", [False, True])
def test_zip_root_layout_and_stubbed_catalog(monkeypatch, tmp_path, tools, raw_schemas):
    calls = []

    async def fetch(url):
        calls.append(url)
        return tools

    monkeypatch.setattr(builder, "fetch_tools", fetch)
    out = tmp_path / "dist"
    archive_path = asyncio.run(builder.build_plugin("https://mcp.example.test", out, raw_schemas=raw_schemas))
    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {"manifest.json", "mcp-tools.json", "color.png", "outline.png", SKILL}
        assert json.loads(archive.read("mcp-tools.json")) == {
            "tools": tools if raw_schemas else builder.sanitize_tools(tools),
        }
        files = {name: archive.read(name) for name in archive.namelist()}
        assert all(content == (out / name).read_bytes() for name, content in files.items())
        builder.validate_package(files)
    assert calls == ["https://mcp.example.test/mcp"]
    assert archive_path.name == "cowork-training-studio-0.1.3.zip"


def test_sanitizer_resolves_nested_refs_and_preserves_constraints():
    schema = {
        "$defs": {
            "a/b": {"type": "string", "minLength": 2, "title": "Noise", "x-extra": True},
            "entry": {"$ref": "#/$defs/a~1b", "maxLength": 4},
        },
        "type": "object", "title": "Noise", "invented": True,
        "properties": {
            "value": {"$ref": "#/$defs/entry"},
            "values": {"type": "array", "items": {"$ref": "#/$defs/a~1b"}},
        },
        "required": ["value"],
    }
    original = deepcopy(schema)
    cleaned = builder.sanitize_schema(schema)
    Draft202012Validator.check_schema(cleaned)
    encoded = json.dumps(cleaned)
    for term in ('"$ref"', '"$defs"', '"title"', '"x-', '"invented"'):
        assert term not in encoded
    validator = Draft202012Validator(cleaned)
    assert validator.is_valid({"value": "abc", "values": ["ok"]})
    for invalid in ({}, {"value": "x"}, {"value": "abcde"}, {"value": "ok", "values": ["x"]}):
        assert not validator.is_valid(invalid)
    assert schema == original


def test_sanitizer_keeps_property_names_and_literal_objects():
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "title": "Noise"},
            "x-label": {"enum": [{"title": "literal", "x-data": True}]},
        },
        "additionalProperties": False,
    }
    result = builder.sanitize_schema(schema)
    assert result["properties"]["title"] == {"type": "string"}
    assert result["properties"]["x-label"] == schema["properties"]["x-label"]
    assert result["additionalProperties"] is False


@pytest.mark.parametrize(("reference", "definitions", "message"), [
    ("https://example.test/schema", {}, "Only local"),
    ("#/$defs/missing", {}, "Unresolved"),
    ("#/$defs/loop", {"loop": {"$ref": "#/$defs/loop"}}, "Cyclic"),
])
def test_sanitizer_rejects_unresolvable_references(reference, definitions, message):
    with pytest.raises(ValueError, match=message):
        builder.sanitize_schema({"$defs": definitions, "$ref": reference})


def test_tool_sanitizer_keeps_metadata_and_simplifies_spec_and_outputs(tools):
    original = deepcopy(tools)
    result = builder.sanitize_tools(tools)
    assert len(result) == 5
    assert tools == original
    for before, after in zip(tools, result):
        for field in ("name", "description", "annotations"):
            assert after[field] == before[field]
        assert after["outputSchema"] == {"type": "object", "additionalProperties": True}
        for field in ("inputSchema", "outputSchema"):
            Draft202012Validator.check_schema(after[field])
            assert not any(term in json.dumps(after[field]) for term in ('"$ref"', '"$defs"', '"x-'))
        if after["name"] in {"validate_lab_spec", "render_lab_page"}:
            assert after["inputSchema"]["properties"]["spec"] == {
                "type": "object", "additionalProperties": True,
                "description": "Call get_lab_spec_schema first and follow it",
            }


def test_failed_discovery_does_not_create_package(monkeypatch, tmp_path):
    async def fail(url):
        raise RuntimeError("Tool discovery failed")

    monkeypatch.setattr(builder, "fetch_tools", fail)
    out = tmp_path / "dist"
    with pytest.raises(RuntimeError, match="Tool discovery failed"):
        asyncio.run(builder.build_plugin("https://mcp.example.test", out))
    assert not out.exists()

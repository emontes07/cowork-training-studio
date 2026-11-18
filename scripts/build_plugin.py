"""Build a Cowork plugin ZIP from local sources and the live MCP tool catalog."""

import argparse
import asyncio
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import httpx
from jsonschema.validators import validator_for
from mcp.types import Tool
from PIL import Image, ImageDraw, ImageFont
import yaml

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "{{MCP_SERVER_URL}}"
TOOL_FIELDS = {"name", "description", "inputSchema", "outputSchema", "annotations"}
EXPECTED_TOOLS = {"list_session_formats", "get_lab_spec_schema", "validate_lab_spec", "render_lab_page"}
# Only schema locations are traversed; property names and literal values stay intact.
SCHEMA_MAP_KEYS = {"properties", "patternProperties", "dependentSchemas"}
SCHEMA_LIST_KEYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
SCHEMA_CHILD_KEYS = {
    "items", "additionalItems", "additionalProperties", "contains", "propertyNames",
    "not", "if", "then", "else", "unevaluatedItems", "unevaluatedProperties", "contentSchema",
}
SCHEMA_VALUE_KEYS = {
    "type", "enum", "const", "description", "default", "examples", "format",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems",
    "minContains", "maxContains", "minProperties", "maxProperties", "required",
    "dependentRequired", "readOnly", "writeOnly", "deprecated", "contentEncoding", "contentMediaType",
}


def sanitize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline local JSON pointers and retain standard, non-title schema keywords."""
    validator_for(schema).check_schema(schema)

    def walk(node: Any, references: tuple[str, ...] = ()) -> Any:
        if isinstance(node, bool):
            return node
        if not isinstance(node, dict):
            raise ValueError("A schema reference must resolve to an object or boolean.")
        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not reference.startswith("#/"):
                raise ValueError(f"Only local JSON pointer references are supported: {reference!r}")
            if reference in references:
                raise ValueError(f"Cyclic schema reference: {reference}")
            target: Any = schema
            for part in unquote(reference[2:]).split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                if isinstance(target, dict) and key in target:
                    target = target[key]
                elif isinstance(target, list) and key.isdecimal() and int(key) < len(target):
                    target = target[int(key)]
                else:
                    raise ValueError(f"Unresolved schema reference: {reference}")
            resolved = walk(target, (*references, reference))
            siblings = walk({key: value for key, value in node.items() if key != "$ref"}, references)
            return {"allOf": [resolved, siblings]} if siblings else resolved
        result = {}
        for key, value in node.items():
            if key in SCHEMA_MAP_KEYS:
                result[key] = {name: walk(child, references) for name, child in value.items()}
            elif key in SCHEMA_LIST_KEYS:
                result[key] = [walk(child, references) for child in value]
            elif key in SCHEMA_CHILD_KEYS:
                result[key] = (
                    [walk(child, references) for child in value]
                    if isinstance(value, list) else walk(value, references)
                )
            elif key == "dependencies":
                result[key] = {
                    name: deepcopy(child) if isinstance(child, list) else walk(child, references)
                    for name, child in value.items()
                }
            elif key in SCHEMA_VALUE_KEYS:
                result[key] = deepcopy(value)
        return result

    result = walk(schema)
    if not isinstance(result, dict):
        raise ValueError("A tool schema must resolve to an object.")
    validator_for(result).check_schema(result)
    return result


def sanitize_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(tools)
    for tool in result:
        tool["inputSchema"] = sanitize_schema(tool["inputSchema"])
        tool["outputSchema"] = {"type": "object", "additionalProperties": True}
        if tool["name"] in {"validate_lab_spec", "render_lab_page"}:
            properties = tool["inputSchema"].get("properties", {})
            if "spec" not in properties:
                raise ValueError(f"{tool['name']} is missing its spec parameter.")
            properties["spec"] = {
                "type": "object", "additionalProperties": True,
                "description": "Call get_lab_spec_schema first and follow it",
            }
    return result


def normalize_mcp_url(value: str) -> str:
    if any(character.isspace() or ord(character) < 32 for character in value) or "\\" in value:
        raise ValueError("MCP URL must not contain whitespace, controls or backslashes.")
    parts = urlsplit(value)
    if (
        parts.scheme != "https" or not parts.hostname or parts.username is not None
        or parts.password is not None or parts.query or parts.fragment
    ):
        raise ValueError("MCP URL must be HTTPS, without credentials, query or fragment.")
    if parts.port is not None and not 1 <= parts.port <= 65535:
        raise ValueError("MCP URL port must be between 1 and 65535.")
    path = parts.path.rstrip("/")
    if not path.endswith("/mcp"):
        path += "/mcp"
    result = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    if len(result) > 2048:
        raise ValueError("MCP URL exceeds the Teams 2048-character limit.")
    return result


def fill_manifest(template: str, mcp_url: str) -> dict[str, Any]:
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("Manifest template must contain exactly one MCP URL placeholder.")
    filled = template.replace(json.dumps(PLACEHOLDER), json.dumps(normalize_mcp_url(mcp_url)))
    manifest = json.loads(filled)
    if not isinstance(manifest, dict) or PLACEHOLDER in filled:
        raise ValueError("Manifest must be an object with a standalone MCP URL placeholder.")
    return manifest


def generate_icons() -> dict[str, bytes]:
    icons = {}
    for name, size, mode, background, font_size in (
        ("color.png", 192, "RGB", "#0F6CBD", 100),
        ("outline.png", 32, "RGBA", (255, 255, 255, 0), 22),
    ):
        image = Image.new(mode, (size, size), background)
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=font_size)
        left, top, right, bottom = draw.textbbox((0, 0), "TS", font=font)
        position = ((size - (right - left)) / 2 - left, (size - (bottom - top)) / 2 - top)
        draw.text(position, "TS", font=font, fill="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        icons[name] = buffer.getvalue()
    return icons


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise ValueError(f"Package path must stay inside the ZIP: {value!r}")
    return path.as_posix()


def bounded_text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonblank text of at most {limit} characters.")
    return value


def validate_package(files: dict[str, bytes]) -> dict[str, Any]:
    for name in files:
        relative_path(name)
    manifest = json.loads(files["manifest.json"])
    if not isinstance(manifest, dict) or manifest.get("manifestVersion") != "1.28":
        raise ValueError("Manifest must be a Teams 1.28 object.")
    identifier = bounded_text(manifest.get("id"), "id", 36)
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", identifier):
        raise ValueError("Manifest id must be a GUID.")
    version = bounded_text(manifest.get("version"), "version", 256)
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("Plugin version must use major.minor.patch.")
    for section, field, limit in (
        ("name", "short", 30), ("name", "full", 100),
        ("description", "short", 80), ("description", "full", 4000),
        ("developer", "name", 32),
    ):
        bounded_text(manifest[section].get(field), f"{section}.{field}", limit)
    for field in ("websiteUrl", "privacyUrl", "termsOfUseUrl"):
        value = bounded_text(manifest["developer"].get(field), f"developer.{field}", 2048)
        if not re.match(r"https?://", value, re.I) or not urlsplit(value).hostname:
            raise ValueError(f"developer.{field} must be an HTTP(S) URL.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", manifest.get("accentColor", "")):
        raise ValueError("accentColor must be a six-digit hex color.")

    connectors = manifest.get("agentConnectors", [])
    if not isinstance(connectors, list) or len(connectors) != 1:
        raise ValueError("This plugin needs exactly one agent connector.")
    connector = connectors[0]
    for field, limit in (("id", 64), ("displayName", 128), ("description", 4000)):
        bounded_text(connector.get(field), f"agentConnectors.{field}", limit)
    remote = connector["toolSource"]["remoteMcpServer"]
    if normalize_mcp_url(remote["mcpServerUrl"]) != remote["mcpServerUrl"]:
        raise ValueError("Manifest MCP URL must end in /mcp without a trailing slash.")
    if remote["authorization"] != {"type": "None"}:
        raise ValueError("This demo connector uses authorization None.")
    if remote["mcpToolDescription"] != {"file": "mcp-tools.json"}:
        raise ValueError("Connector must reference mcp-tools.json at the ZIP root.")

    skills = manifest.get("agentSkills", [])
    if not isinstance(skills, list) or not 1 <= len(skills) <= 20:
        raise ValueError("Manifest needs 1-20 skill folders.")
    for skill in skills:
        folder = relative_path(bounded_text(skill.get("folder"), "agentSkills.folder", 256))
        name = f"{folder}/SKILL.md"
        if name not in files:
            raise ValueError(f"Missing skill file: {name}")
        text = files[name].decode("utf-8")
        if len(text.splitlines()) > 140:
            raise ValueError(f"{name} exceeds 140 lines.")
        front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
        if front is None:
            raise ValueError(f"{name} needs YAML front matter.")
        metadata = yaml.safe_load(front.group(1))
        if not isinstance(metadata, dict):
            raise ValueError(f"{name} front matter must be a mapping.")
        skill_name = bounded_text(metadata.get("name"), f"{name}: name", 64)
        if skill_name != PurePosixPath(folder).name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name):
            raise ValueError(f"{name} name must match its kebab-case folder.")
        bounded_text(metadata.get("description"), f"{name}: description", 1024)
        bounded_text(metadata.get("license"), f"{name}: license", 256)
        for field in ("author", "version"):
            bounded_text(metadata.get("metadata", {}).get(field), f"{name}: metadata.{field}", 256)

    for kind, size in (("color", 192), ("outline", 32)):
        name = relative_path(manifest["icons"][kind])
        with Image.open(io.BytesIO(files[name])) as image:
            if image.format != "PNG" or image.size != (size, size):
                raise ValueError(f"{kind} icon must be a {size}x{size} PNG.")
            if kind == "color" and image.mode not in {"RGB", "RGBA"}:
                raise ValueError("Color icon must be full color.")
            if kind == "outline":
                if image.mode != "RGBA" or image.getchannel("A").getextrema() != (0, 255):
                    raise ValueError("Outline icon must have a visible mark and transparent background.")
                if any(
                    pixel[3] and pixel[:3] != (255, 255, 255)
                    for y in range(size) for x in range(size) for pixel in [image.getpixel((x, y))]
                ):
                    raise ValueError("Outline icon must be white on transparent.")

    catalog = json.loads(files["mcp-tools.json"])
    tools = catalog["tools"]
    if not isinstance(tools, list) or len(tools) != 4 or {tool["name"] for tool in tools} != EXPECTED_TOOLS:
        raise ValueError("Tool catalog must contain exactly the four Training Studio tools.")
    for tool in tools:
        if set(tool) - TOOL_FIELDS:
            raise ValueError("Tool catalog contains unsupported metadata fields.")
        Tool.model_validate(tool)
        bounded_text(tool.get("description"), f"{tool['name']}: description", 100_000)
        for field in ("inputSchema", "outputSchema"):
            schema = tool.get(field)
            if not isinstance(schema, dict):
                raise ValueError(f"{tool['name']} needs an object {field}.")
            validator_for(schema).check_schema(schema)
    return manifest


async def fetch_tools(url: str) -> list[dict[str, Any]]:
    transport = StreamableHttpTransport(url, httpx_client_factory=httpx.AsyncClient)
    async with Client(transport, timeout=30) as client:
        tools = await client.list_tools()
    return [
        tool.model_dump(mode="json", by_alias=True, include=TOOL_FIELDS, exclude_none=True)
        for tool in tools
    ]


async def build_plugin(
    mcp_url: str, out: Path, source: Path = ROOT / "plugin", *, raw_schemas: bool = False,
) -> Path:
    url = normalize_mcp_url(mcp_url)
    manifest = fill_manifest((source / "manifest.template.json").read_text(encoding="utf-8"), url)
    tools = await fetch_tools(url)
    catalog = {"tools": tools if raw_schemas else sanitize_tools(tools)}
    files = {
        "manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
        "mcp-tools.json": (json.dumps(catalog, indent=2) + "\n").encode("utf-8"),
        **generate_icons(),
    }
    for skill in manifest["agentSkills"]:
        folder = relative_path(skill["folder"])
        directory = source / folder
        directory.resolve().relative_to(source.resolve())
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Skill files must not be symbolic links: {path}")
            if path.is_file():
                files[path.relative_to(source).as_posix()] = path.read_bytes()
    validate_package(files)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    archive_path = out / f"cowork-training-studio-{manifest['version']}.zip"
    with ZipFile(archive_path, "w") as archive:
        for name, content in sorted(files.items()):
            entry = ZipInfo(name)
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, content)
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-url", required=True, help="HTTPS MCP endpoint or server base URL")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="Output directory (default: dist/)")
    parser.add_argument(
        "--raw-schemas", action="store_true",
        help="Keep the live schemas unchanged for comparison (use a separate --out directory)",
    )
    args = parser.parse_args()
    archive = asyncio.run(build_plugin(args.mcp_url, args.out, raw_schemas=args.raw_schemas))
    print(f"ZIP: {archive.resolve()}")
    print(f"Bytes: {archive.stat().st_size:,}")
    print(f"SHA-256: {hashlib.sha256(archive.read_bytes()).hexdigest()}")
    with ZipFile(archive) as package:
        print("Files:\n" + "\n".join(package.namelist()))


if __name__ == "__main__":
    main()

from typing import Any

from studio.schemas.demo_pack import DemoPackSpec


def get_demo_pack_schema() -> dict[str, Any]:
    """Return DemoPackSpec 1.0 JSON Schema before drafting a fictional demo pack.

    Choose function_pack or prompt_pack; keep public audience context separate
    from fictional companies, cast and records. Draft inputs before scenario
    prompts, then call validate_demo_pack and render_demo_guide.
    Conditional requirements, references and quality checks are enforced by the
    validator. Missing fact sources and quantitative evidence are warnings.
    The server never creates files, mail, chats or calendar items.
    """
    return DemoPackSpec.model_json_schema()

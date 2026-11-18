import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))


@pytest.fixture
def legal_spec():
    return json.loads((Path(__file__).parent / "fixtures" / "legal_notice_lab.json").read_text(encoding="utf-8"))


@pytest.fixture
def minimal_spec():
    return {
        "schema_version": "2.0",
        "title": "Zava practice story",
        "subtitle": "A connected fictional planning workshop",
        "audience": "Zava facilitators",
        "duration_minutes": 40,
        "skill_level": "basic",
        "products": ["Copilot"],
        "functional_area": "Planning",
        "company": {"name": "Zava", "is_fictional": True, "description": "An invented training organization"},
        "narrative": {
            "role": "Workshop facilitator", "situation": "An unfinished workshop plan",
            "trigger": "A practice review request", "deadline": "Before the next practice session",
            "leave_with": ["A draft plan", "A review checklist", "A reusable prompt"],
        },
        "through_line": {"name": "Story sheet", "location": "Practice workbook", "description": "A running decision record"},
        "files": [],
        "setup": {
            "steps": ["Open a blank practice workbook."],
            "ground_rules": ["Use only fictional content."],
            "modes": [{"name": "Chat", "description": "Discuss and review the draft."}],
        },
        "chapters": [
            {
                "id": f"chapter-{chapter}", "title": f"Chapter {chapter}", "minutes": 20,
                "format": "guided", "story_so_far": "The fictional workshop plan needs a review.",
                "builds_on": [] if chapter == 1 else ["chapter-1"],
                "you_will_add": "A checked planning decision",
                "steps": [
                    {
                        "id": f"step-{chapter}-{step}", "title": f"Practice step {step}",
                        "minutes": 10, "goal": "Create a reviewable draft.",
                        "uses": "The current Story sheet", "level": "basic",
                        "intro": "Build on the earlier draft using only fictional content.",
                        "prompts": [{
                            "label": "Refine the draft", "mode": "chat",
                            "text": "Using the fictional Zava brief and the current Story sheet, refine the workshop agenda and explain your changes. Do not invent missing facts.",
                        }],
                        "expected": {"summary": "A traceable agenda revision", "key_facts": []},
                        "carries_forward": "Add the checked decision to the Story sheet.",
                        "callouts": [], "self_check": ["Is the revision grounded?", "Can a reviewer follow it?"],
                    }
                    for step in range(1, 3)
                ],
            }
            for chapter in range(1, 3)
        ],
        "troubleshooting": [{"problem": "Editing is unavailable", "fix": "Paste the reviewed content manually."}],
        "glossary": [{"term": "Through-line", "definition": "The artifact carried across chapters."}],
        "disclaimer": "Fictional practice only. Review every output.",
    }

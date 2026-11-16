from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))


@pytest.fixture
def minimal_spec():
    return {
        "title": "Zava practice lab",
        "subtitle": "A fictional planning workshop",
        "audience": "Zava facilitators",
        "duration_minutes": 40,
        "skill_level": "basic",
        "products": ["Copilot"],
        "functional_area": "Planning",
        "company": {
            "name": "Zava", "is_fictional": True,
            "description": "An invented training organization",
        },
        "objectives": ["Draft a plan", "Review the evidence", "Refine the result"],
        "prerequisites": [],
        "resources": [],
        "ground_rules": ["Use only fictional content."],
        "scenarios": [
            {
                "id": f"scenario-{scenario}",
                "title": f"Scenario {scenario}",
                "story": {
                    "context": "Zava needs a workshop plan.",
                    "stakeholder": "Zava facilitator",
                    "time_pressure": "Before the next practice session",
                    "source_material": "An invented workshop brief",
                    "deliverable": "A draft agenda",
                },
                "labs": [
                    {
                        "id": f"lab-{scenario}-{lab}",
                        "title": f"Practice {lab}",
                        "goal": "Create a reviewable draft.",
                        "minutes": 10,
                        "difficulty": "basic",
                        "source": "Fictional workshop brief",
                        "context": "Work in a new draft, without real organization data.",
                        "exercises": [{
                            "instruction": "Draft the agenda.",
                            "prompt": "Using the fictional Zava brief, draft a workshop agenda with three stages and one review question per stage. Do not invent missing facts.",
                            "expected_outcome": "A three-stage agenda with review questions.",
                        }],
                        "callouts": [],
                        "self_check": ["Are the three stages present?", "Can each question be answered?"],
                    }
                    for lab in range(1, 3)
                ],
            }
            for scenario in range(1, 3)
        ],
        "capstone": None,
    }

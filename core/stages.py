"""Legacy-compatible stage labels; future stages register here."""

_WBS_STAGE_TITLES = {
    "Intake": "1. Concept Development", "Sandbox": "2. Plot Architecture",
    "Plot Architect": "3. Scene Scripting", "Drafting Engine": "4. Creative Draft",
    "Revision Engine": "6. Script Polish", "Rewrite Engine": "7. Script Rewrite",
}


def wbs_stage_title(stage, export_view=False):
    if stage == "Isolation Guardrail":
        return "8. Final Output" if export_view else "5. Script Lock"
    return _WBS_STAGE_TITLES.get(stage, str(stage))


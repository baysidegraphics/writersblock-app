"""Verbatim extracted WBS pure functions; no story text regeneration."""
import re
import hashlib
import json

def wbs_ir_parse_actionable_finding(text):
    """Parse the five required report fields; return None for vague findings."""
    raw = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", str(text or "").strip())
    fields = re.split(
        r"\s*\|\s*(?=(?:ISSUE|WHY|LOCATION|EVIDENCE|SUGGESTED FIX)\s*:)" , raw,
        flags=re.IGNORECASE,
    )
    values = {}
    for field in fields:
        match = re.fullmatch(r"(ISSUE|WHY|LOCATION|EVIDENCE|SUGGESTED FIX)\s*:\s*(.+)", field.strip(), re.I | re.S)
        if match:
            values[match.group(1).upper()] = match.group(2).strip()
    if len(values) != 5 or not all(values.values()):
        return None
    evidence_match = re.fullmatch(r'["“](.+?)["”]', values["EVIDENCE"])
    if not evidence_match:
        return None
    values["QUOTE"] = evidence_match.group(1).strip()
    # Vague or formulaic filler is NOT a rule, explanation, or correction.
    vague = (
        "check the stated", "review the stated", "relevant text only if",
        "check whether", "consider whether", "might violate",
        "could potentially", "refer to the", "review for compliance",
        "check compliance", "verify the requirement", "if it fails",
    )
    for key in ("ISSUE", "WHY", "SUGGESTED FIX"):
        value = values[key].casefold()
        if len(value.split()) < 5 or any(phrase in value for phrase in vague):
            return None
    # An identifying quotation alone is insufficient: the reviewer needs to
    # explain a concrete mistake. An evocative quotation is not itself wrong.
    if values["WHY"].casefold() == values["ISSUE"].casefold():
        return None
    return values



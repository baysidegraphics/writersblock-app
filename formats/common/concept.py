"""Verbatim extracted WBS pure functions; no story text regeneration."""
import re
import hashlib
import json

def wbs_concept_contains_editorial_commentary(text):
    """Reject planning notes mistakenly presented as a writer-facing concept."""
    text = str(text or "")
    editorial_patterns = (
        r"\b(?:this|the) (?:story|flash story|narrative|premise|concept|episode|screenplay|script|plot)\s+(?:explores|examines|focuses on|centers on|revolves around|will|should|aims to|is about|follows|depicts|portrays)\b",
        r"\b(?:the )?(?:central|core|main) (?:idea|theme|premise|tension|conflict) (?:is|explores|examines|centers|focuses)\b",
        r"\b(?:the )?(?:narrative|story|plot|episode|script) should\b",
        r"\b(?:from a|in a) (?:first|third)[ -]person perspective\b",
        r"\b(?:the writer|the author|the reader|the audience) (?:should|will|can|must)\b",
        r"\b(?:the ending|the climax|the resolution) (?:should|will|can)\b",
        r"\b(?:this concept|this premise|this suggestion)\b",
        r"\b(?:target audience|genre|dialogue style|production influence):\s",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in editorial_patterns)



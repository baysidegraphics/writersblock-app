"""
WritersBlock Studios format template: Standard Manuscript Only

This module contains only format-specific UI/configuration data.
It does not alter the shared left navigation, WritersBlock header, workflow stages,
or right-side Quill panel.
"""

TEMPLATE = {
    "id": 'standard_manuscript',
    "display_name": 'Standard Manuscript Only',
    "description": 'A manuscript-focused template for preparing, organizing, polishing, and outputting conventional written material without a specialized production format.',
    "uses_existing_concept_layout_as_base": True,
    "concept_fields": [{'key': 'project_title', 'label': 'Project Title', 'type': 'text', 'required': True, 'help': 'Working manuscript title.'}, {'key': 'manuscript_type', 'label': 'Manuscript Type', 'type': 'select', 'required': True, 'help': 'General manuscript category.', 'options': ['Fiction', 'Nonfiction', 'Memoir / Biography', 'Essay / Collection', 'Instructional / How-To', 'Other']}, {'key': 'source_mode', 'label': 'Starting Point', 'type': 'select', 'required': True, 'help': 'How the project begins.', 'options': ['New Manuscript', 'Use Existing Draft / Manuscript']}, {'key': 'purpose', 'label': 'Purpose / Intended Use', 'type': 'textarea', 'required': False, 'help': 'Publication, private use, submission, adaptation, archive, or other use.'}, {'key': 'target_length', 'label': 'Target Length', 'type': 'text', 'required': False, 'help': 'Optional word-count or page target.'}, {'key': 'audience', 'label': 'Intended Audience', 'type': 'textarea', 'required': False, 'help': 'Primary reader or readership.'}, {'key': 'voice_style', 'label': 'Voice / Style Direction', 'type': 'textarea', 'required': False, 'help': 'Desired authorial voice, formality, pacing, or stylistic notes.'}, {'key': 'organization', 'label': 'Organization / Section Plan', 'type': 'textarea', 'required': False, 'help': 'Chapter, section, essay, or document structure.'}, {'key': 'special_requirements', 'label': 'Special Requirements', 'type': 'textarea', 'required': False, 'help': 'Formatting, terminology, citation, continuity, or project-specific needs.'}, {'key': 'dialogue_style', 'label': 'Dialogue Style', 'type': 'select', 'required': False, 'help': 'For fiction or narrative material.', 'options': ['Story-Driven / Automatic', 'Dialogue Light', 'Balanced', 'Dialogue Forward', 'Narration Only', 'Not Applicable']}],
    "quill_instruction_module": "quill.quill_standard_manuscript",
}

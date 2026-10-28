# -*- coding: utf-8 -*-
"""
BCF Manager - BCF (Building Collaboration Format) export.

Phase 1: stub only. The database schema has BCFTopics table, but nothing
populates it. This module exists as the landing spot for Phase 2 BCF
generation logic.

Future: convert issues to BCF 3.0 MarkUp XML, with topics per issue,
viewpoints with clash location, and comments for status tracking.
"""


def export_issues_to_bcf(issues_list, output_path):
    """
    Export a list of issues to a BCF container.
    
    Phase 1: stub (raises NotImplementedError).
    
    Future implementation:
      - Create a BCF 3.0 MarkUp XML structure
      - One Topic per issue
      - Viewpoint with camera aimed at clash location
      - Save as .bcfzip (zip archive of XML/viewpoints)
    """
    raise NotImplementedError(
        "BCF export is planned for Phase 2. Phase 1 is hard-clash "
        "detection only. Results are visible via the Issue Report "
        "pushbutton."
    )


def update_issue_from_bcf_topic(issue_id, bcf_topic_dict):
    """
    Update an issue's BCF metadata (topic ID, export path, etc.)
    from a BCF Topic object.
    
    Phase 1: stub.
    """
    pass

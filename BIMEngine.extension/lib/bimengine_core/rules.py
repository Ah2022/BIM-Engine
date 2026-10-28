# -*- coding: utf-8 -*-
"""
Rule Engine - filters and deduplicates issues before persistence.

Phase 1 scope: passthrough only (no actual filtering rules yet). This
layer exists so future phases (rule-based dedup, severity scoring,
category exclusions, etc.) can land here without changing the
revit_bridge or database layers.
"""


def filter_issues(issues_list, config_dict=None):
    """
    Apply rule-based filtering to a list of issues.
    
    Phase 1: no-op passthrough - all issues pass through unchanged.
    
    Future phases: rule-based dedup (if issue (A,B) and (B,A) both exist,
    keep only one), severity scoring, dynamic category exclusion, etc.
    """
    return issues_list


def deduplicate_issues(issues_list):
    """
    Remove duplicate issues from the list (if any).
    
    Phase 1: passthrough only - rely on the octree candidate dedup
    instead. This function exists for Phase 2 when rule-based dedup
    might add more logic.
    """
    return issues_list


def should_ignore_issue(issue_dict):
    """
    Decide if an issue should be auto-ignored (e.g. known false positives,
    configuration-based category exclusions).
    
    Phase 1: always False (never auto-ignore).
    """
    return False

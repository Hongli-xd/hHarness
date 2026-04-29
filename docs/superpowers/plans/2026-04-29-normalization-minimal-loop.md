# HistRAG Normalization Minimal Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working slice of place and reign-year normalization for `linked_view`.

**Architecture:** Add a focused `histrag.normalization` package with YAML registries and a pure-Python resolver. Keep the first version local and deterministic: exact spelling lookup, dynasty/year filtering, ambiguity warnings, and year-level reign conversion.

**Tech Stack:** Python 3.10+, PyYAML, pytest, existing HistRAG package layout.

---

### Task 1: Reign-Year Resolver

**Files:**
- Create: `Harness/histrag/normalization/__init__.py`
- Create: `Harness/histrag/normalization/resolver.py`
- Create: `Harness/histrag/normalization/times/tang_reigns.yaml`
- Test: `Harness/tests/test_normalization.py`

- [x] Write failing tests for `resolve_time("元和十五年", dynasty_hint="唐")`, ambiguous `resolve_time("元和元年")`, and unknown reign handling.
- [x] Run `cd Harness && pytest tests/test_normalization.py -v` and verify failures are caused by missing normalization code.
- [x] Implement minimal YAML loading and reign lookup.
- [x] Re-run the tests and verify they pass.

### Task 2: CHGIS-Style Place Resolver

**Files:**
- Modify: `Harness/histrag/normalization/resolver.py`
- Create: `Harness/histrag/normalization/places/tang_places.yaml`
- Test: `Harness/tests/test_normalization.py`

- [x] Write failing tests for Tang Chang'an exact spelling, missing context ambiguity, and event-year filtering.
- [x] Run `cd Harness && pytest tests/test_normalization.py -v` and verify expected failures.
- [x] Implement spelling lookup over `place_instances`, `spellings`, and `present_locations`.
- [x] Re-run the tests and verify they pass.

### Task 3: Normalize Linked View Payload

**Files:**
- Modify: `Harness/histrag/normalization/resolver.py`
- Modify: `Harness/histrag/tools/linked_view_tool.py`
- Test: `Harness/tests/test_normalization.py`

- [x] Write failing tests for `normalize_linked_view_payload` preserving `place_names` consistency and adding warnings for unresolved names.
- [x] Run `cd Harness && pytest tests/test_normalization.py -v` and verify expected failures.
- [x] Implement payload normalization and call it inside `LinkedViewTool.execute`.
- [x] Run targeted tests and existing linked view tests.

### Task 4: Skills Documentation

**Files:**
- Create: `Harness/histrag/skills/place_normalization.md`
- Create: `Harness/histrag/skills/time_normalization.md`

- [x] Add concise skill docs matching the implemented resolver behavior.
- [x] Run `cd Harness && pytest tests/test_normalization.py tests/test_integration.py -v`.

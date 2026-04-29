"""Deterministic normalization for historical time and place expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).parent


@dataclass(frozen=True)
class TimeResolution:
    raw_time: str
    normalized_year: int | None = None
    dynasty: str | None = None
    reign_title: str | None = None
    reign_year: int | None = None
    emperor: str | None = None
    confidence: str = "none"
    source_refs: list[str] = field(default_factory=list)
    ambiguity_candidates: list[TimeResolution] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedLocation:
    text: str = ""
    longitude: float | None = None
    latitude: float | None = None


@dataclass(frozen=True)
class PlaceResolution:
    raw_name: str
    place_instance_id: str | None = None
    default_spelling: str | None = None
    feature_type: str | None = None
    begin_year: int | None = None
    end_year: int | None = None
    present_location: ResolvedLocation = field(default_factory=ResolvedLocation)
    confidence: str = "none"
    source_refs: list[str] = field(default_factory=list)
    ambiguity_candidates: list[PlaceResolution] = field(default_factory=list)


def resolve_time(raw_time: str, dynasty_hint: str | None = None, context_text: str = "") -> TimeResolution:
    reign_title, reign_year = _parse_reign_expression(raw_time)
    if not reign_title or reign_year is None:
        return TimeResolution(raw_time=raw_time)

    candidates = []
    for path in sorted((DATA_DIR / "times").glob("*.yaml")):
        data = _load_yaml(path)
        for reign in data.get("reigns", []):
            if reign.get("reign_title") != reign_title:
                continue
            if dynasty_hint and reign.get("dynasty") != dynasty_hint:
                continue
            mapping = reign.get("mapping", {})
            normalized_year = mapping.get(reign_year) or mapping.get(str(reign_year))
            if normalized_year is None:
                continue
            candidates.append(
                TimeResolution(
                    raw_time=raw_time,
                    normalized_year=int(normalized_year),
                    dynasty=reign.get("dynasty"),
                    reign_title=reign_title,
                    reign_year=reign_year,
                    emperor=reign.get("emperor"),
                    confidence="high",
                    source_refs=[f"registry:times/{path.name}#{reign.get('id')}"],
                )
            )

    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        return TimeResolution(
            raw_time=raw_time,
            reign_title=reign_title,
            reign_year=reign_year,
            confidence="low",
            ambiguity_candidates=candidates,
        )
    return TimeResolution(raw_time=raw_time, reign_title=reign_title, reign_year=reign_year)


def resolve_place(
    raw_name: str,
    dynasty_hint: str | None = None,
    event_year: int | None = None,
    context_text: str = "",
) -> PlaceResolution:
    data = _load_yaml(DATA_DIR / "places" / "tang_places.yaml")
    instances = {item["id"]: item for item in data.get("place_instances", [])}
    feature_types = {item["id"]: item for item in data.get("feature_types", [])}
    present_locations = {
        item["place_instance_id"]: item for item in data.get("present_locations", [])
    }

    matched_ids = {
        spelling["place_instance_id"]
        for spelling in data.get("spellings", [])
        if spelling.get("written_form") == raw_name
    }

    candidates = []
    for place_id in sorted(matched_ids):
        instance = instances.get(place_id)
        if not instance:
            continue
        if dynasty_hint and instance.get("dynasty") != dynasty_hint:
            continue
        if event_year is not None and not _year_in_range(
            event_year, instance.get("begin_year"), instance.get("end_year")
        ):
            continue
        candidates.append(_place_resolution(raw_name, instance, feature_types, present_locations))

    if len(candidates) == 1:
        return _with_confidence(candidates[0], "high")

    all_candidates = [
        _place_resolution(raw_name, instances[place_id], feature_types, present_locations)
        for place_id in sorted(matched_ids)
        if place_id in instances
    ]
    if all_candidates:
        return PlaceResolution(
            raw_name=raw_name,
            confidence="low",
            ambiguity_candidates=all_candidates,
        )
    return PlaceResolution(raw_name=raw_name)


def normalize_linked_view_payload(
    events: list[dict[str, Any]],
    places: list[dict[str, Any]],
    dynasty_hint: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    normalized_events = [dict(event) for event in events]
    place_names = {str(place.get("name", "")).strip() for place in places if place.get("name")}
    for event in normalized_events:
        place_names.update(str(name).strip() for name in event.get("place_names", []) if name)

    warnings: list[str] = []
    normalized_places: list[dict[str, Any]] = []
    existing_places = {str(place.get("name", "")).strip(): place for place in places if place.get("name")}
    for name in sorted(place_names):
        event_year = _first_event_year_for_place(normalized_events, name)
        resolution = resolve_place(name, dynasty_hint=dynasty_hint, event_year=event_year)
        if resolution.confidence == "high":
            normalized_places.append(
                {
                    "name": resolution.default_spelling or name,
                    "longitude": resolution.present_location.longitude,
                    "latitude": resolution.present_location.latitude,
                    "place_type": "cap" if resolution.feature_type == "都城" else "hist",
                    "info": (
                        f"{resolution.feature_type or '历史地名'} instance: "
                        f"{resolution.place_instance_id}; "
                        f"{resolution.present_location.text}，现代坐标为近似点。"
                    ),
                }
            )
        elif _has_coordinates(existing_places.get(name, {})):
            normalized_places.append(dict(existing_places[name]))
        else:
            warnings.append(f"Unresolved or ambiguous place: {name}")

    return normalized_events, normalized_places, warnings


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_reign_expression(raw_time: str) -> tuple[str | None, int | None]:
    text = raw_time.strip()
    if not text.endswith("年"):
        return None, None
    body = text[:-1]
    if body.endswith("元"):
        return body[:-1], 1
    index = len(body)
    while index > 0 and body[index - 1] in "一二三四五六七八九十百0123456789":
        index -= 1
    if index < len(body):
        return body[:index], _parse_chinese_int(body[index:])
    return None, None


def _parse_chinese_int(value: str) -> int | None:
    value = value.strip()
    if value == "元":
        return 1
    if value.isdigit():
        return int(value)

    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + digits.get(value[1:], 0)
    if "十" in value:
        left, right = value.split("十", 1)
        return digits.get(left, 0) * 10 + (digits.get(right, 0) if right else 0)
    return digits.get(value)


def _year_in_range(year: int, begin_year: int | None, end_year: int | None) -> bool:
    if begin_year is not None and year < int(begin_year):
        return False
    if end_year is not None and year > int(end_year):
        return False
    return True


def _place_resolution(
    raw_name: str,
    instance: dict[str, Any],
    feature_types: dict[str, dict[str, Any]],
    present_locations: dict[str, dict[str, Any]],
) -> PlaceResolution:
    location = present_locations.get(instance["id"], {})
    feature = feature_types.get(instance.get("feature_type_id", ""), {})
    return PlaceResolution(
        raw_name=raw_name,
        place_instance_id=instance["id"],
        default_spelling=instance.get("default_spelling", raw_name),
        feature_type=feature.get("name_zh"),
        begin_year=instance.get("begin_year"),
        end_year=instance.get("end_year"),
        present_location=ResolvedLocation(
            text=location.get("text_value", ""),
            longitude=_maybe_float(location.get("longitude")),
            latitude=_maybe_float(location.get("latitude")),
        ),
        confidence="medium",
        source_refs=[f"registry:places/tang_places.yaml#{instance['id']}"],
    )


def _with_confidence(resolution: PlaceResolution, confidence: str) -> PlaceResolution:
    return PlaceResolution(
        raw_name=resolution.raw_name,
        place_instance_id=resolution.place_instance_id,
        default_spelling=resolution.default_spelling,
        feature_type=resolution.feature_type,
        begin_year=resolution.begin_year,
        end_year=resolution.end_year,
        present_location=resolution.present_location,
        confidence=confidence,
        source_refs=resolution.source_refs,
        ambiguity_candidates=resolution.ambiguity_candidates,
    )


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _first_event_year_for_place(events: list[dict[str, Any]], place_name: str) -> int | None:
    for event in events:
        if place_name in event.get("place_names", []):
            year = event.get("year")
            return int(year) if year is not None else None
    return None


def _has_coordinates(place: dict[str, Any]) -> bool:
    return place.get("longitude") is not None and place.get("latitude") is not None

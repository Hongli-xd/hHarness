"""Tests for historical place and time normalization."""

from histrag.agent import ToolExecutionContext
from histrag.normalization import (
    normalize_linked_view_payload,
    resolve_place,
    resolve_time,
)
from histrag.tools.linked_view_tool import LinkedViewInput, LinkedViewTool


def test_resolve_tang_reign_year():
    result = resolve_time("元和十五年", dynasty_hint="唐")

    assert result.normalized_year == 820
    assert result.reign_title == "元和"
    assert result.reign_year == 15
    assert result.dynasty == "唐"
    assert result.confidence == "high"


def test_resolve_imported_tang_reign_years():
    kaiyuan = resolve_time("开元二十九年", dynasty_hint="唐")
    zhenguan = resolve_time("贞观二十三年", dynasty_hint="唐")

    assert kaiyuan.normalized_year == 741
    assert kaiyuan.emperor == "唐玄宗"
    assert zhenguan.normalized_year == 649
    assert zhenguan.emperor == "唐太宗"


def test_resolve_ambiguous_reign_without_dynasty():
    result = resolve_time("元和元年")

    assert result.normalized_year is None
    assert result.confidence == "low"
    assert {candidate.dynasty for candidate in result.ambiguity_candidates} >= {"东汉", "唐"}


def test_resolve_unknown_reign():
    result = resolve_time("不存在元年", dynasty_hint="唐")

    assert result.normalized_year is None
    assert result.confidence == "none"
    assert result.ambiguity_candidates == []


def test_resolve_tang_changan_place_instance():
    result = resolve_place("长安", dynasty_hint="唐", event_year=820)

    assert result.place_instance_id == "hrg:tang:changan:618-904"
    assert result.default_spelling == "长安"
    assert result.feature_type == "都城"
    assert result.present_location.text == "陕西省西安市"
    assert result.present_location.longitude == 108.94
    assert result.confidence == "high"


def test_resolve_expanded_tang_places():
    luoyang = resolve_place("洛阳", dynasty_hint="唐", event_year=820)
    yangzhou = resolve_place("扬州", dynasty_hint="唐", event_year=820)

    assert luoyang.place_instance_id == "hrg:tang:luoyang:618-907"
    assert luoyang.feature_type == "东都"
    assert luoyang.present_location.text == "河南省洛阳市"
    assert yangzhou.place_instance_id == "hrg:tang:yangzhou:618-907"
    assert yangzhou.feature_type == "州"
    assert yangzhou.present_location.text == "江苏省扬州市"


def test_resolve_changan_without_context_is_ambiguous():
    result = resolve_place("长安")

    assert result.place_instance_id is None
    assert result.confidence == "low"
    assert {candidate.place_instance_id for candidate in result.ambiguity_candidates} >= {
        "hrg:tang:changan:618-904",
        "hrg:han:changan:-202-23",
    }


def test_normalize_linked_view_payload_keeps_event_place_names_consistent():
    events = [
        {
            "year": 820,
            "title": "元和十五年政局",
            "description": "",
            "category": "pol",
            "place_names": ["长安"],
        }
    ]
    places = [{"name": "长安"}]

    normalized_events, normalized_places, warnings = normalize_linked_view_payload(
        events,
        places,
        dynasty_hint="唐",
    )

    assert warnings == []
    assert normalized_events[0]["place_names"] == ["长安"]
    assert normalized_places[0]["name"] == "长安"
    assert normalized_places[0]["longitude"] == 108.94
    assert normalized_places[0]["latitude"] == 34.26
    assert "hrg:tang:changan:618-904" in normalized_places[0]["info"]


async def test_linked_view_tool_normalizes_missing_place_coordinates(tmp_path):
    arguments = LinkedViewInput.model_validate(
        {
            "title": "元和政局",
            "events": [
                {
                    "year": 820,
                    "title": "元和十五年政局",
                    "description": "",
                    "category": "pol",
                    "place_names": ["长安"],
                }
            ],
            "places": [{"name": "长安"}],
        }
    )

    result = await LinkedViewTool().execute(
        arguments,
        ToolExecutionContext(cwd=tmp_path, metadata={"dynasty_hint": "唐"}),
    )

    assert result.is_error is False
    assert result.metadata["warnings"] == []
    assert "108.94" in result.metadata["html"]
    assert "hrg:tang:changan:618-904" in result.metadata["html"]

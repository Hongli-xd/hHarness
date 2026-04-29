"""Linked View Tool - 历史地名地图联动视图工具。

每次 RAG 回答结束后自动调用，从答案文本中提取
时间事件和历史地名，生成可嵌入父窗口的本地地图 HTML。
父窗口时间轴选中事件 → 地图高亮关联地名；
点击地图地名 → 通知父窗口跳转到关联事件。
"""

from __future__ import annotations

import html as html_lib
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..agent import BaseTool, ToolExecutionContext, ToolResult
from ..normalization import normalize_linked_view_payload


class LinkedEvent(BaseModel):
    model_config = {'extra': 'allow'}

    year: int = Field(description="事件年份（负数=公元前）")
    title: str = Field(default="未知事件", description="事件标题")
    description: str = Field(default="", description="事件描述")
    category: str = Field(default="pol", description="mil/pol/eco/nat")
    place_names: list[str] = Field(default_factory=list, description="该事件关联的地名列表")

    @field_validator('category', mode='before')
    @classmethod
    def normalize_category(cls, v):
        aliases = {
            "军事": "mil",
            "战争": "mil",
            "战役": "mil",
            "政治": "pol",
            "政务": "pol",
            "制度": "pol",
            "财政": "eco",
            "经济": "eco",
            "赋税": "eco",
            "灾异": "nat",
            "灾害": "nat",
            "自然": "nat",
            "天灾": "nat",
        }
        value = str(v or "").strip().lower()
        value = aliases.get(value, value)
        return value if value in {"mil", "pol", "eco", "nat"} else "pol"

    @field_validator('place_names', mode='before')
    @classmethod
    def normalize_place_names(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            parts = v.replace("，", ",").replace("、", ",").split(",")
            return [p.strip() for p in parts if p.strip()]
        if isinstance(v, list):
            return [str(p).strip() for p in v if str(p).strip()]
        return v


class LinkedPlace(BaseModel):
    model_config = {'extra': 'allow'}

    name: str = Field(description="地名")
    longitude: float | None = Field(default=None, description="经度")
    latitude: float | None = Field(default=None, description="纬度")
    place_type: str = Field(default="hist", description="cap/prov/hist/pass/battle/port/region")
    info: str = Field(default="", description="地名描述")

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if v is None:
            return v
        if not -180 <= v <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return v

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if v is None:
            return v
        if not -90 <= v <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator('place_type', mode='before')
    @classmethod
    def normalize_place_type(cls, v):
        aliases = {
            "都城": "cap",
            "首都": "cap",
            "省": "prov",
            "州": "prov",
            "州郡": "prov",
            "郡": "prov",
            "历史地名": "hist",
            "地名": "hist",
            "关隘": "pass",
            "关口": "pass",
            "战场": "battle",
            "战役": "battle",
            "港口": "port",
            "港": "port",
            "区域": "region",
            "地区": "region",
        }
        value = str(v or "").strip().lower()
        value = aliases.get(value, value)
        allowed = {"cap", "prov", "hist", "pass", "battle", "port", "region"}
        return value if value in allowed else "hist"


class LinkedViewInput(BaseModel):
    events: list[LinkedEvent] = Field(description="时间事件列表，每个事件可绑定地名")
    places: list[LinkedPlace] = Field(description="历史地名列表，包含经纬度")
    title: str = Field(default="历史研究视图", description="页面标题")

    @field_validator('events', 'places', mode='before')
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                return json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError("events/places must be valid JSON when passed as strings") from exc
        return v


class LinkedViewTool(BaseTool):
    """联动历史地图工具 - 自动在每次回答后生成可嵌入地图视图。

【调用时机】
由引擎在每次 AssistantTurnComplete 前自动注入，无需模型主动决定。
模型只需提供从回答中提取的事件和地名数据。

【功能】
- 可缩放交互地图，标注历史地名
- 接收父窗口时间轴 selectEvent 消息，高亮并飞到关联地名
- 点击地图地名，向父窗口发送 eventSelected 消息
- 父窗口负责渲染时间轴和处理时间轴跳转
"""

    name = "linked_view"
    description = """从回答内容中提取时间事件和历史地名，生成可与父窗口时间轴联动的地图页面。

【必须传入】
- events：从回答中提取的历史事件（年份+标题+描述+类别+关联地名）
- places：从回答中出现的历史地名（名称+经纬度+类型+描述）

【地名坐标】
提供历史时期的大致坐标即可，精度到 0.1 度，使用今天中国地名对应的现代坐标。

【事件-地名绑定】
每个事件的 place_names 填入该事件发生地或相关地的名称列表，
名称必须与 places 列表中的 name 一致，这样点击事件时地图才能高亮。

【联动边界】
本工具只生成地图视图 HTML；时间轴由父窗口渲染。
父窗口可发送 selectEvent 消息选中事件，地图会回发 eventSelected 消息。
"""
    input_model = LinkedViewInput

    def is_read_only(self, arguments: LinkedViewInput) -> bool:
        return True

    async def execute(
        self, arguments: LinkedViewInput, context: ToolExecutionContext
    ) -> ToolResult:
        if not arguments.events and not arguments.places:
            return ToolResult(output="No events or places provided.", is_error=True)

        arguments, normalization_warnings = self._normalize_arguments(arguments, context)
        warnings = normalization_warnings + self._collect_warnings(arguments)
        html = self._generate_html(arguments)

        summary = (
            f"[LinkedView generated: {len(arguments.events)} events, "
            f"{len(arguments.places)} places]\n"
            + "\n".join(f"  {e.year}: {e.title} → {e.place_names}" for e in arguments.events[:5])
            + (f"\n  ...and {len(arguments.events)-5} more" if len(arguments.events) > 5 else "")
            + (f"\n[warnings: {len(warnings)}]" if warnings else "")
        )

        return ToolResult(
            output=summary,
            metadata={
                "html": html,
                "type": "linked_view",
                "warnings": warnings,
                "events": [
                    {
                        "y": e.year,
                        "title": e.title,
                        "desc": e.description,
                        "cat": e.category,
                        "places": e.place_names,
                    }
                    for e in arguments.events
                ],
            },
        )

    def _normalize_arguments(
        self,
        arguments: LinkedViewInput,
        context: ToolExecutionContext,
    ) -> tuple[LinkedViewInput, list[str]]:
        events, places, warnings = normalize_linked_view_payload(
            [event.model_dump() for event in arguments.events],
            [place.model_dump() for place in arguments.places],
            dynasty_hint=context.metadata.get("dynasty_hint"),
        )
        payload = {
            "title": arguments.title,
            "events": events,
            "places": places,
        }
        return LinkedViewInput.model_validate(payload), warnings

    # ── HTML 生成 ──────────────────────────────────────────────

    def _collect_warnings(self, args: LinkedViewInput) -> list[str]:
        warnings: list[str] = []
        place_names = [p.name for p in args.places]
        place_name_set = set(place_names)

        duplicates = sorted({name for name in place_names if place_names.count(name) > 1})
        if duplicates:
            warnings.append(f"Duplicate place names: {', '.join(duplicates)}")

        missing = sorted(
            {
                name
                for event in args.events
                for name in event.place_names
                if name not in place_name_set
            }
        )
        if missing:
            warnings.append(f"Event place_names not found in places: {', '.join(missing)}")

        if args.events and not any(event.place_names for event in args.events):
            warnings.append("No events are bound to places.")

        return warnings

    def _generate_local_map_html(self, args: LinkedViewInput) -> str:
        def dump_js(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

        normalized_events = []
        for e in args.events:
            year = e.year
            if year < 0 and abs(year) >= 500:
                year = abs(year)
            normalized_events.append(
                {
                    "y": year,
                    "title": e.title,
                    "desc": e.description,
                    "cat": e.category,
                    "places": e.place_names,
                }
            )

        events_js = dump_js(normalized_events)

        places_js = dump_js(
            [
                {
                    "n": p.name,
                    "lo": p.longitude,
                    "la": p.latitude,
                    "t": p.place_type,
                    "i": p.info,
                }
                for p in args.places
            ],
        )

        years = [event["y"] for event in normalized_events] if normalized_events else [0]
        y_min = min(years)
        y_max = max(years)
        pad = max(20, (y_max - y_min) // 10)
        y_start = y_min - pad
        y_end = y_max + pad

        title = html_lib.escape(args.title, quote=True)

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       background: #f5f3ee; color: #333; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

/* ── 顶栏 ── */
#toolbar {{
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 7px 12px; background: #fff; border-bottom: 1px solid #e0d8c8; flex-shrink: 0;
}}
#toolbar h1 {{ font-size: 13px; font-weight: 600; color: #333; }}
.sep {{ width: 1px; height: 16px; background: #ddd; }}
.tb {{
  font-size: 11px; padding: 2px 10px; border-radius: 20px;
  border: 1px solid #ccc; background: transparent; color: #666;
  cursor: pointer; transition: all .15s;
}}
.tb:hover {{ border-color: #999; color: #333; }}
.tb.on-mil {{ background:#EEEDFE; color:#3C3489; border-color:#AFA9EC; font-weight:500; }}
.tb.on-pol {{ background:#E1F5EE; color:#085041; border-color:#5DCAA5; font-weight:500; }}
.tb.on-eco {{ background:#FAEEDA; color:#633806; border-color:#EF9F27; font-weight:500; }}
.tb.on-nat {{ background:#FAECE7; color:#712B13; border-color:#F0997B; font-weight:500; }}

/* ── 地图区 ── */
#map-panel {{
  flex: 1; position: relative; overflow: hidden;
  background: radial-gradient(circle at 50% 45%, #f8f2e5 0, #eee5d1 58%, #d8ccb0 100%);
}}
#map-svg {{ width: 100%; height: 100%; display: block; }}
.graticule {{ fill: none; stroke: rgba(128, 103, 68, .24); stroke-width: .6; }}
.country {{ fill: #e6dcc5; stroke: #aa9876; stroke-width: .55; vector-effect: non-scaling-stroke; }}
.place circle {{
  stroke: #fffaf0; stroke-width: 1.6; paint-order: stroke; cursor: pointer;
  filter: drop-shadow(0 1px 2px rgba(55, 36, 14, .25));
}}
.place text {{
  font-size: 11px; fill: #2d261b; stroke: rgba(255,250,240,.9); stroke-width: 3px;
  paint-order: stroke; pointer-events: none; font-weight: 600;
}}
.place.is-highlighted circle {{ stroke: #3b1b10; stroke-width: 2.2; }}
.place.is-highlighted text {{ font-size: 13px; fill: #2c1710; font-weight: 800; }}
#map-tooltip {{
  position: absolute; pointer-events: none; display: none;
  background: rgba(255,255,255,0.96); border: 1px solid #ccc;
  border-radius: 6px; padding: 6px 10px; font-size: 12px;
  max-width: 200px; line-height: 1.6; z-index: 100;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}}
#map-tooltip strong {{ font-size: 13px; color: #222; display: block; margin-bottom: 2px; }}
.map-error {{
  margin: 16px; padding: 18px 20px; border-radius: 8px;
  background: #fff7ed; border: 1px solid #fed7aa;
  color: #7a3b24; font-size: 13px; line-height: 1.6;
}}
</style>
</head>
<body>

<div id="toolbar">
  <h1>{title}</h1>
  <div class="sep"></div>
  <button class="tb on-mil" onclick="toggleCat('mil',this)">军事</button>
  <button class="tb on-pol" onclick="toggleCat('pol',this)">政治</button>
  <button class="tb on-eco" onclick="toggleCat('eco',this)">财政</button>
  <button class="tb on-nat" onclick="toggleCat('nat',this)">灾异</button>
</div>

<div id="map-panel">
  <svg id="map-svg" role="img" aria-label="历史地名地图"></svg>
  <div id="map-tooltip"></div>
</div>

<script src="/resources/lib/d3.min.js"
  onerror="document.getElementById('map-panel').innerHTML='<div class=&quot;map-error&quot;>地图资源加载失败：/resources/lib/d3.min.js 不可用。</div>'"></script>
<script src="/resources/lib/topojson.min.js"
  onerror="document.getElementById('map-panel').innerHTML='<div class=&quot;map-error&quot;>地图资源加载失败：/resources/lib/topojson.min.js 不可用。</div>'"></script>
<script>
// ── 数据 ────────────────────────────────────────────────────
const EVENTS = {events_js};
const PLACES = {places_js};
const Y_START = {y_start};
const Y_END   = {y_end};

const CAT = {{
  mil: {{ color:'#534AB7', label:'军事' }},
  pol: {{ color:'#0F6E56', label:'政治' }},
  eco: {{ color:'#854F0B', label:'财政' }},
  nat: {{ color:'#993C1D', label:'灾异' }},
}};

function placeColor(type, hl) {{
  if (hl) return '#e05000';
  const m = {{ cap:'#b7311f', prov:'#2f4b9a', battle:'#8b1e1e', pass:'#7b4f1e', port:'#0f6e78', region:'#566b35' }};
  return m[type] || '#667755';
}}

// ── 状态 ────────────────────────────────────────────────────
let shownCats = new Set(['mil','pol','eco','nat']);
let selIdx = -1;
let highlighted = new Set();
let countriesData = null;
let projection = null;
let mapLayer = null;
let placeLayer = null;
const TRUSTED_ORIGIN = window.location.origin;

function postToParent(payload) {{
  window.parent.postMessage(payload, TRUSTED_ORIGIN);
}}

function isValidPlace(p) {{
  return p && Number.isFinite(p.lo) && Number.isFinite(p.la)
    && p.lo >= -180 && p.lo <= 180 && p.la >= -90 && p.la <= 90;
}}

const tooltip = document.getElementById('map-tooltip');
const mapPanel = document.getElementById('map-panel');
const svg = d3.select('#map-svg');

function setTooltipContent(place) {{
  tooltip.replaceChildren();
  const name = document.createElement('strong');
  name.textContent = place.n || '';
  tooltip.appendChild(name);
  if (place.i) tooltip.appendChild(document.createTextNode(place.i));
}}

function mapDimensions() {{
  return {{
    width: Math.max(320, mapPanel.clientWidth || 640),
    height: Math.max(240, mapPanel.clientHeight || 420),
  }};
}}

function renderMap() {{
  if (!countriesData) return;
  const dims = mapDimensions();
  const width = dims.width;
  const height = dims.height;
  svg.attr('viewBox', `0 0 ${{width}} ${{height}}`);
  svg.selectAll('*').remove();

  projection = d3.geoMercator()
    .center([105, 35])
    .scale(Math.min(width * 1.05, height * 2.05))
    .translate([width / 2, height / 2]);
  const path = d3.geoPath(projection);
  const graticule = d3.geoGraticule10();

  mapLayer = svg.append('g').attr('class', 'map-layer');
  mapLayer.append('path').datum(graticule).attr('class', 'graticule').attr('d', path);
  mapLayer.selectAll('path.country')
    .data(countriesData.features)
    .join('path')
    .attr('class', 'country')
    .attr('d', path);

  placeLayer = mapLayer.append('g').attr('class', 'place-layer');
  drawPlaces();
}}

function drawPlaces() {{
  if (!placeLayer || !projection) return;
  const visiblePlaces = PLACES
    .filter(isValidPlace)
    .map(p => ({{ ...p, xy: projection([p.lo, p.la]) }}))
    .filter(p => Array.isArray(p.xy) && Number.isFinite(p.xy[0]) && Number.isFinite(p.xy[1]));

  const nodes = placeLayer.selectAll('g.place')
    .data(visiblePlaces, p => p.n)
    .join(enter => {{
      const g = enter.append('g')
        .attr('class', 'place')
        .style('cursor', 'pointer')
        .on('click', (_event, p) => onPlaceClick(p.n))
        .on('mousemove', (event, p) => {{
          tooltip.style.display = 'block';
          setTooltipContent(p);
          tooltip.style.left = (event.offsetX + 14) + 'px';
          tooltip.style.top = (event.offsetY - 36) + 'px';
        }})
        .on('mouseleave', () => {{
          tooltip.style.display = 'none';
        }});
      g.append('circle');
      g.append('text').attr('dx', 9).attr('dy', 4);
      return g;
    }});

  nodes
    .attr('transform', p => `translate(${{p.xy[0]}},${{p.xy[1]}})`)
    .classed('is-highlighted', p => highlighted.has(p.n));

  nodes.select('circle')
    .attr('r', p => highlighted.has(p.n) ? 7 : (p.t === 'cap' ? 5.8 : p.t === 'prov' ? 5 : 4.2))
    .attr('fill', p => placeColor(p.t, highlighted.has(p.n)));

  nodes.select('text').text(p => p.n);
}}

// ── 高亮地名 ───────────────────────────────────────────────
function setHighlightedPlaces(names) {{
  highlighted = new Set(names);
  drawPlaces();
}}

function focusPlace(name) {{
  const p = PLACES.find(p => p.n === name && isValidPlace(p));
  if (!p || !projection || !mapLayer) return;
  const xy = projection([p.lo, p.la]);
  if (!Array.isArray(xy)) return;
  const dims = mapDimensions();
  const zoom = 1.85;
  const tx = dims.width / 2 - xy[0] * zoom;
  const ty = dims.height / 2 - xy[1] * zoom;
  mapLayer.transition().duration(520).attr('transform', `translate(${{tx}},${{ty}}) scale(${{zoom}})`);
}}

// ── 点击地名 → 查找关联事件 ─────────────────────────────────
function onPlaceClick(name) {{
  const vis = EVENTS.filter(e => shownCats.has(e.cat));
  const idx  = vis.findIndex(e => (e.places||[]).includes(name));
  if (idx >= 0) {{
    pickEvent(EVENTS.indexOf(vis[idx]));
  }}
}}

// ── 选中事件 → 通知父窗口更新时间轴 ──────────────────────────
function isValidEventIndex(idx) {{
  return Number.isInteger(idx) && idx >= 0 && idx < EVENTS.length;
}}

function pickEvent(idx) {{
  if (!isValidEventIndex(idx)) return;
  selIdx = idx;
  const e = EVENTS[idx];
  setHighlightedPlaces(e.places || []);
  // 通知父窗口选中事件
  postToParent({{ type: 'eventSelected', index: idx, event: e }});
  // 飞到第一个相关地名
  if (e.places && e.places.length > 0) focusPlace(e.places[0]);
}}

function notifyCategoryFilterChanged() {{
  postToParent({{
    type: 'categoryFilterChanged',
    categories: Array.from(shownCats),
  }});
}}

function toggleCat(cat, btn) {{
  if (!Object.prototype.hasOwnProperty.call(CAT, cat)) return;
  if (shownCats.has(cat)) {{ shownCats.delete(cat); btn.className = 'tb'; }}
  else {{ shownCats.add(cat); btn.className = `tb on-${{cat}}`; }}
  selIdx = -1;
  setHighlightedPlaces([]);
  notifyCategoryFilterChanged();
}}

// ── 监听父窗口消息 ──────────────────────────────────────────
window.addEventListener('message', e => {{
  if (e.origin !== TRUSTED_ORIGIN) return;
  const data = e.data;
  if (data && data.type === 'selectEvent' && isValidEventIndex(data.index)) {{
    // 父窗口时间轴选中事件 → 同步高亮地图地名
    pickEvent(data.index);
  }}
}});

function showMapError(message) {{
  mapPanel.innerHTML = `<div class="map-error">${{message}}</div>`;
}}

async function initMap() {{
  try {{
    if (!window.d3 || !window.topojson) {{
      throw new Error('本地 D3/topojson 资源未加载');
    }}
    const world = await d3.json('/resources/data/countries-110m.json');
    if (!world || !world.objects || !world.objects.countries) {{
      throw new Error('countries-110m.json 格式不正确');
    }}
    countriesData = topojson.feature(world, world.objects.countries);
    renderMap();
    window.addEventListener('resize', () => renderMap());
  }} catch (err) {{
    console.error(err);
    showMapError(`地图资源加载失败：${{err.message || err}}`);
  }}
}}

initMap();
</script>
</body>
</html>"""

    def _generate_html(self, args: LinkedViewInput) -> str:
        return self._generate_local_map_html(args)

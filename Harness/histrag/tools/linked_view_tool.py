"""Linked View Tool - 历史地名地图联动视图工具。

每次 RAG 回答结束后自动调用，从答案文本中提取
时间事件和历史地名，生成可嵌入父窗口的 Cesium 地图 HTML。
父窗口时间轴选中事件 → 地图高亮关联地名；
点击地图地名 → 通知父窗口跳转到关联事件。
"""

from __future__ import annotations

import html as html_lib
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator
from ..agent import BaseTool, ToolExecutionContext, ToolResult


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
    longitude: float = Field(description="经度")
    latitude: float = Field(description="纬度")
    place_type: str = Field(default="hist", description="cap/prov/hist/pass/battle/port/region")
    info: str = Field(default="", description="地名描述")

    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return v

    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
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

        warnings = self._collect_warnings(arguments)
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

    def _generate_html(self, args: LinkedViewInput) -> str:
        def dump_js(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

        events_js = dump_js(
            [
                {
                    "y": e.year,
                    "title": e.title,
                    "desc": e.description,
                    "cat": e.category,
                    "places": e.place_names,
                }
                for e in args.events
            ],
        )

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

        years = [e.year for e in args.events] if args.events else [0]
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
<link rel="stylesheet" href="https://cesium.com/downloads/cesiumjs/releases/1.118/Build/Cesium/Widgets/widgets.css">
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
}}
#cesiumContainer {{ width: 100%; height: 100%; }}
.cesium-widget-credits,
.cesium-viewer-bottom {{ display: none !important; }}
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
  <div id="cesiumContainer"></div>
  <div id="map-tooltip"></div>
</div>

<script src="https://cesium.com/downloads/cesiumjs/releases/1.118/Build/Cesium/Cesium.js"
  onerror="document.getElementById('map-panel').innerHTML='<div class=&quot;map-error&quot;>地图资源加载失败：Cesium CDN 不可用。请检查网络，或改用本地 Cesium 静态资源。</div>'"></script>
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

// 地名类型 → Cesium 颜色
function placeColor(type, hl) {{
  if (hl) return Cesium.Color.fromCssColorString('#e05000');
  const m = {{ cap:'#cc3300', prov:'#223388', battle:'#8b0000' }};
  return Cesium.Color.fromCssColorString(m[type] || '#667755');
}}

// ── 状态 ────────────────────────────────────────────────────
let shownCats = new Set(['mil','pol','eco','nat']);
let selIdx = -1;
let highlighted = new Set();
const TRUSTED_ORIGIN = window.location.origin;

function postToParent(payload) {{
  window.parent.postMessage(payload, TRUSTED_ORIGIN);
}}

// ── Cesium 初始化 ────────────────────────────────────────────
const viewer = new Cesium.Viewer('cesiumContainer', {{
  baseLayerPicker: false,
  animation: false,
  fullscreenButton: false,
  geocoder: false,
  homeButton: false,
  infoBox: false,
  sceneModePicker: false,
  selectionIndicator: false,
  timeline: false,
  navigationHelpButton: false,
  navigationInstructionsInitiallyVisible: false,
}});

// 临时在线地形 fallback：ArcGIS Online 不稳定，后续应替换为本地 DEM terrain provider。
try {{
  const terrainProvider = new Cesium.ArcGISTiledElevationTerrainProvider({{
    url: 'https://elevation3d.arcgisonline.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer',
  }});
  viewer.scene.terrainProvider = terrainProvider;
}} catch(e) {{
  console.warn('地形加载失败，继续使用默认椭球地形:', e);
}}

// 防止渲染错误导致崩溃
viewer.scene.maximumRenderTimeChange = Infinity;
viewer.scene.requestRenderMode = false;

// 叠加国界线（容错处理）
try {{
  viewer.dataSources.add(Cesium.GeoJsonDataSource.load(
    'https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson',
    {{ stroke: Cesium.Color.fromCssColorString('#8b7355'), fill: Cesium.Color.TRANSPARENT, strokeWidth: 1 }}
  ));
}} catch(e) {{ console.warn('国界线加载失败:', e); }}

// 叠加中国省界（简化多边形，减少顶点数避免崩溃）
try {{
  Promise.all([
    Cesium.GeoJsonDataSource.load(
      'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json',
      {{ stroke: Cesium.Color.fromCssColorString('#c0392b'), fill: Cesium.Color.TRANSPARENT, strokeWidth: 0.5 }}
    )
  ]).then(results => {{
    const ds = results[0];
    // 简化每个省的 polygon，顶点数超过阈值就跳过
    ds.entities.values.forEach(entity => {{
      if (entity.polygon && entity.polygon.hierarchy) {{
        try {{
          const hierarchy = entity.polygon.hierarchy.getValue();
          if (hierarchy && hierarchy.positions && hierarchy.positions.length > 200) {{
            // 顶点过多，跳过此省
            entity.show = false;
          }}
        }} catch(e) {{}}
      }}
    }});
    viewer.dataSources.add(ds);
  }}).catch(e => {{ console.warn('省界加载失败:', e); }});
}} catch(e) {{ console.warn('省界初始化失败:', e); }}

// 初始视角：聚焦中国
viewer.camera.setView({{
  destination: Cesium.Cartesian3.fromDegrees(105, 35, 4500000),
  orientation: {{ heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 }}
}});

// ── 地名标注 ────────────────────────────────────────────────
const placeEntities = {{}};
function isValidPlace(p) {{
  return p && Number.isFinite(p.lo) && Number.isFinite(p.la)
    && p.lo >= -180 && p.lo <= 180 && p.la >= -90 && p.la <= 90;
}}

PLACES.forEach(p => {{
  if (!isValidPlace(p)) {{
    console.warn('跳过无效地名坐标:', p);
    return;
  }}
  const isHL = highlighted.has(p.n);
  const color = placeColor(p.t, isHL);
  const pinSize = p.t === 'cap' ? 12 : p.t === 'prov' ? 9 : 7;
  const entity = viewer.entities.add({{
    name: p.n,
    position: Cesium.Cartesian3.fromDegrees(p.lo, p.la, 0),
    point: {{
      pixelSize: pinSize,
      color: color,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 1.5,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    }},
    label: {{
      text: p.n,
      font: p.t === 'cap' ? 'bold 13px sans-serif' : '11px sans-serif',
      fillColor: color,
      outlineColor: Cesium.Color.WHITE,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      pixelOffset: new Cesium.Cartesian2(8, 0),
      verticalOrigin: Cesium.VerticalOrigin.CENTER,
      horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    }},
    _placeData: p,
  }});
  if (!placeEntities[p.n]) placeEntities[p.n] = [];
  placeEntities[p.n].push(entity);
}});

// ── 点击地名 → 时间轴联动 ──────────────────────────────────
const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
const tooltip = document.getElementById('map-tooltip');

function setTooltipContent(place) {{
  tooltip.replaceChildren();
  const name = document.createElement('strong');
  name.textContent = place.n || '';
  tooltip.appendChild(name);
  if (place.i) tooltip.appendChild(document.createTextNode(place.i));
}}

handler.setInputAction(movement => {{
  const picked = viewer.scene.pick(movement.position);
  if (Cesium.defined(picked) && Cesium.defined(picked.id) && picked.id._placeData) {{
    const p = picked.id._placeData;
    onPlaceClick(p.n);
  }}
}}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

handler.setInputAction(movement => {{
  const picked = viewer.scene.pick(movement.endPosition);
  if (Cesium.defined(picked) && Cesium.defined(picked.id) && picked.id._placeData) {{
    const p = picked.id._placeData;
    tooltip.style.display = 'block';
    setTooltipContent(p);
    tooltip.style.left = (movement.endPosition.x + 14) + 'px';
    tooltip.style.top  = (movement.endPosition.y - 40) + 'px';
  }} else {{
    tooltip.style.display = 'none';
  }}
}}, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

// ── 高亮地名 ───────────────────────────────────────────────
function setHighlightedPlaces(names) {{
  highlighted = new Set(names);
  PLACES.forEach(p => {{
    const entities = placeEntities[p.n] || [];
    const hl = highlighted.has(p.n);
    const color = placeColor(p.t, hl);
    entities.forEach(ent => {{
      ent.point.color = color;
      ent.point.pixelSize = hl ? 14 : (p.t==='cap' ? 12 : p.t==='prov' ? 9 : 7);
      ent.label.fillColor = color;
      ent.label.font = hl ? 'bold 14px sans-serif' : (p.t==='cap' ? 'bold 13px sans-serif' : '11px sans-serif');
    }});
  }});
}}

// ── 飞到地名 ────────────────────────────────────────────────
function focusPlace(name) {{
  const p = PLACES.find(p => p.n === name && isValidPlace(p));
  if (!p) return;
  viewer.camera.flyTo({{
    destination: Cesium.Cartesian3.fromDegrees(p.lo, p.la, 800000),
    duration: 1.2,
  }});
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
</script>
</body>
</html>"""

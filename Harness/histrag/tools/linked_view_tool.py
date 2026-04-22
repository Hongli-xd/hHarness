"""Linked View Tool - 联动时间轴+地图可视化工具。

每次 RAG 回答结束后自动调用，从答案文本中提取
时间事件和历史地名，生成左地图右时间轴的联动 HTML。
点击时间轴事件 → 地图高亮关联地名；
点击地图地名 → 时间轴跳转到关联事件。
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from ..agent import BaseTool, ToolExecutionContext, ToolResult


class LinkedEvent(BaseModel):
    year: int = Field(description="事件年份（负数=公元前）")
    title: str = Field(description="事件标题")
    description: str = Field(default="", description="事件描述")
    category: str = Field(default="pol", description="mil/pol/eco/nat")
    place_names: list[str] = Field(default_factory=list, description="该事件关联的地名列表")


class LinkedPlace(BaseModel):
    name: str = Field(description="地名")
    longitude: float = Field(description="经度")
    latitude: float = Field(description="纬度")
    place_type: str = Field(default="hist", description="cap/prov/hist/pass/battle/port/region")
    info: str = Field(default="", description="地名描述")


class LinkedViewInput(BaseModel):
    events: list[LinkedEvent] = Field(description="时间事件列表，每个事件可绑定地名")
    places: list[LinkedPlace] = Field(description="历史地名列表，包含经纬度")
    title: str = Field(default="历史研究视图", description="页面标题")


class LinkedViewTool(BaseTool):
    """联动历史视图工具 - 自动在每次回答后生成时间轴+地图联动页面。

【调用时机】
由引擎在每次 AssistantTurnComplete 前自动注入，无需模型主动决定。
模型只需提供从回答中提取的事件和地名数据。

【功能】
- 左侧：可缩放交互地图，标注历史地名
- 右侧：可筛选时间轴，标注历史事件
- 联动：点击时间轴事件 → 地图高亮关联地名
- 联动：点击地图地名 → 时间轴跳转关联事件
"""

    name = "linked_view"
    description = """从回答内容中提取时间事件和历史地名，生成联动时间轴+地图页面。

【必须传入】
- events：从回答中提取的历史事件（年份+标题+描述+类别+关联地名）
- places：从回答中出现的历史地名（名称+经纬度+类型+描述）

【地名坐标】
提供历史时期的大致坐标即可，精度到 0.1 度，使用今天中国地名对应的现代坐标。

【事件-地名绑定】
每个事件的 place_names 填入该事件发生地或相关地的名称列表，
名称必须与 places 列表中的 name 一致，这样点击事件时地图才能高亮。
"""
    input_model = LinkedViewInput

    def is_read_only(self, arguments: LinkedViewInput) -> bool:
        return True

    async def execute(
        self, arguments: LinkedViewInput, context: ToolExecutionContext
    ) -> ToolResult:
        if not arguments.events and not arguments.places:
            return ToolResult(output="No events or places provided.", is_error=True)

        html = self._generate_html(arguments)

        summary = (
            f"[LinkedView generated: {len(arguments.events)} events, "
            f"{len(arguments.places)} places]\n"
            + "\n".join(f"  {e.year}: {e.title} → {e.place_names}" for e in arguments.events[:5])
            + (f"\n  ...and {len(arguments.events)-5} more" if len(arguments.events) > 5 else "")
        )

        return ToolResult(
            output=summary,
            metadata={"html": html, "type": "linked_view"},
        )

    # ── HTML 生成 ──────────────────────────────────────────────

    def _generate_html(self, args: LinkedViewInput) -> str:
        events_js = json.dumps(
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
            ensure_ascii=False,
        )

        places_js = json.dumps(
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
            ensure_ascii=False,
        )

        years = [e.year for e in args.events] if args.events else [0]
        y_min = min(years)
        y_max = max(years)
        pad = max(20, (y_max - y_min) // 10)
        y_start = y_min - pad
        y_end = y_max + pad

        title = args.title

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

/* ── 主体：左(答案+地图) + 右时间轴 ── */
#main {{ display: flex; flex: 1; overflow: hidden; }}

/* ── 左区 ── */
#left-panel {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }}

/* ── CesiumJS 地图区 ── */
#map-panel {{
  flex: 1;
  position: relative;
  overflow: hidden;
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

/* ── 答案框（地图下方） ── */
#answer-box {{
  flex: 1;
  overflow-y: auto;
  padding: 10px 16px;
  background: #fff;
  border-top: 1px solid #e0d8c8;
  font-size: 13px; line-height: 1.7; color: #333;
}}
#answer-box .ans-title {{ font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #222; }}
#answer-box .ans-text {{ white-space: pre-wrap; }}
#tl-panel {{
  width: 200px; flex-shrink: 0; display: flex; flex-direction: column;
  overflow: hidden; border-left: 1px solid #e0d8c8; background: #fff;
}}
#tl-header {{
  padding: 8px 10px; font-size: 12px; font-weight: 600; color: #666;
  border-bottom: 1px solid #e0d8c8; flex-shrink: 0;
}}
#tl-outer {{ flex: 1; overflow-y: auto; overflow-x: hidden; padding: 10px 8px; }}
#tl-track {{ position: relative; min-height: 100%; display: flex; flex-direction: column; gap: 0; }}
#tl-axis {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background:#bbb; transform: translateX(-50%); }}
.tick {{ position: relative; display: flex; align-items: center; min-height: 40px; padding: 0 6px; }}
.tick-line {{ width: 100%; display: flex; align-items: center; gap: 4px; }}
.tick-label {{ font-size: 10px; color: #aaa; white-space: nowrap; min-width: 28px; text-align: center; }}
.ev {{
  display: flex; align-items: center; gap: 6px; cursor: pointer;
  padding: 4px 6px; border-radius: 4px; transition: background .12s;
}}
.ev:hover {{ background: #f0f0f0; }}
.ev.sel {{ background: #e8f4f0; }}
.ev-dot {{
  width: 10px; height: 10px; border-radius: 50%;
  border: 1.5px solid #fff; flex-shrink: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}}
.ev-lbl {{ font-size: 11px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ev.sel .ev-lbl {{ color: #222; font-weight: 600; }}
.ev-year {{ font-size: 10px; color: #aaa; flex-shrink: 0; }}
.ev.sel .ev-year {{ color: #666; }}
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

<div id="main">
  <div id="left-panel">
    <div id="map-panel">
      <div id="cesiumContainer"></div>
      <div id="map-tooltip"></div>
    </div>
    <div id="answer-box">
      <div class="ans-title">{title}</div>
      <div class="ans-text">点击右侧时间轴事件查看详情</div>
    </div>
  </div>
  <div id="tl-panel">
    <div id="tl-header">时间轴</div>
    <div id="tl-outer">
      <div id="tl-track">
        <div id="tl-axis"></div>
      </div>
    </div>
  </div>
</div>

<script src="https://cesium.com/downloads/cesiumjs/releases/1.118/Build/Cesium/Cesium.js"></script>
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

// ── Cesium 初始化 ────────────────────────────────────────────
Cesium.Ion.defaultAccessToken = '';  // 不使用 Ion，全部用免费源

const viewer = new Cesium.Viewer('cesiumContainer', {{
  baseLayer: Cesium.ImageryLayer.fromProviderAsync(
    Cesium.ArcGisMapServerImageryProvider.fromUrl(
      'https://services.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer'
    )
  ),
  terrainProvider: new Cesium.ArcGISTiledElevationTerrainProvider({{
    url: 'https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer'
  }}),
  animation: false,
  baseLayerPicker: false,
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

// 叠加国界线
viewer.dataSources.add(Cesium.GeoJsonDataSource.load(
  'https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson',
  {{ stroke: Cesium.Color.fromCssColorString('#8b7355'), fill: Cesium.Color.TRANSPARENT, strokeWidth: 1 }}
));

// 叠加中国省界
viewer.dataSources.add(Cesium.GeoJsonDataSource.load(
  'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json',
  {{ stroke: Cesium.Color.fromCssColorString('#c0392b'), fill: Cesium.Color.TRANSPARENT, strokeWidth: 0.5 }}
));

// 初始视角：聚焦中国
viewer.camera.setView({{
  destination: Cesium.Cartesian3.fromDegrees(105, 35, 4500000),
  orientation: {{ heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 }}
}});

// ── 地名标注 ────────────────────────────────────────────────
const placeEntities = {{}};
PLACES.forEach(p => {{
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
  placeEntities[p.n] = entity;
}});

// ── 点击地名 → 时间轴联动 ──────────────────────────────────
const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
const tooltip = document.getElementById('map-tooltip');

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
    tooltip.innerHTML = `<strong>${{p.n}}</strong>${{p.i || ''}}`;
    const mp = document.getElementById('map-panel');
    const r = mp.getBoundingClientRect();
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
    const ent = placeEntities[p.n];
    if (!ent) return;
    const hl = highlighted.has(p.n);
    const color = placeColor(p.t, hl);
    ent.point.color = color;
    ent.point.pixelSize = hl ? 14 : (p.t==='cap' ? 12 : p.t==='prov' ? 9 : 7);
    ent.label.fillColor = color;
    ent.label.font = hl ? 'bold 14px sans-serif' : (p.t==='cap' ? 'bold 13px sans-serif' : '11px sans-serif');
  }});
}}

// ── 飞到地名 ────────────────────────────────────────────────
function focusPlace(name) {{
  const p = PLACES.find(p => p.n === name);
  if (!p) return;
  viewer.camera.flyTo({{
    destination: Cesium.Cartesian3.fromDegrees(p.lo, p.la, 800000),
    duration: 1.2,
  }});
}}

// ── 点击地名 → 时间轴跳转 ────────────────────────────────────
function onPlaceClick(name) {{
  const vis = EVENTS.filter(e => shownCats.has(e.cat));
  const idx  = vis.findIndex(e => (e.places||[]).includes(name));
  if (idx >= 0) {{
    pickEvent(EVENTS.indexOf(vis[idx]));
  }}
}}

// ── 时间轴渲染 ───────────────────────────────────────────────
function renderTimeline() {{
  const track = document.getElementById('tl-track');
  let h = '';

  const span = Y_END - Y_START;
  const step = span > 500 ? 50 : span > 200 ? 20 : 10;
  const tickYears = [];
  for (let y = Y_START; y <= Y_END; y += step) tickYears.push(y);

  const vis = EVENTS.filter(e => shownCats.has(e.cat));
  vis.sort((a, b) => a.y - b.y);

  const tickEvents = {{}};
  tickYears.forEach(ty => {{ tickEvents[ty] = []; }});
  vis.forEach(e => {{
    const tick = tickYears.filter(ty => ty <= e.y).pop() || tickYears[0];
    tickEvents[tick].push(e);
  }});

  tickYears.forEach(ty => {{
    h += `<div class="tick"><div class="tick-line"><span class="tick-label">${{ty}}</span></div></div>`;
    tickEvents[ty].forEach(e => {{
      const c = CAT[e.cat] || CAT.pol;
      const sel = EVENTS.indexOf(e) === selIdx;
      h += `<div class="ev${{sel?' sel':''}}" onclick="pickEvent(${{EVENTS.indexOf(e)}})">
        <div class="ev-dot" style="background:${{c.color}}"></div>
        <span class="ev-lbl">${{e.title}}</span>
        <span class="ev-year">${{e.y}}</span>
      </div>`;
    }});
  }});

  track.innerHTML = h;
}}

// ── 选中事件 ────────────────────────────────────────────────
function pickEvent(idx) {{
  selIdx = idx;
  renderTimeline();
  const e = EVENTS[idx];
  setHighlightedPlaces(e.places || []);
  document.querySelector('#answer-box .ans-text').textContent =
    (e.desc ? e.desc + '\n\n' : '') + '相关地点：' + (e.places || []).join(', ');
  // 飞到第一个相关地名
  if (e.places && e.places.length > 0) focusPlace(e.places[0]);
}}

function toggleCat(cat, btn) {{
  if (shownCats.has(cat)) {{ shownCats.delete(cat); btn.className = 'tb'; }}
  else {{ shownCats.add(cat); btn.className = `tb on-${{cat}}`; }}
  selIdx = -1;
  setHighlightedPlaces([]);
  renderTimeline();
}}

// ── 初始化 ──────────────────────────────────────────────────
renderTimeline();
</script>
</body>
</html>"""
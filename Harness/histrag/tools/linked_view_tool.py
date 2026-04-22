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
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f3ee; color: #333; height: 100vh; display: flex; flex-direction: column; }}

/* ── 顶栏 ── */
#toolbar {{
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 7px 12px; background: #fff; border-bottom: 1px solid #e0d8c8;
  flex-shrink: 0;
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
.tb.layer-on {{ background:#e8f4f0; color:#085041; border-color:#5DCAA5; }}

/* ── 主体：左(答案+地图) + 右时间轴 ── */
#main {{ display: flex; flex: 1; overflow: hidden; gap: 0; }}

/* ── 左区：答案文本 + 地图（上下或左右） ── */
#left-panel {{
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}}
#answer-box {{
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e0d8c8;
  font-size: 13px;
  line-height: 1.7;
  color: #333;
  min-height: 120px;
}}
#answer-box .ans-title {{ font-weight: 600; font-size: 14px; margin-bottom: 6px; color: #222; }}
#answer-box .ans-text {{ white-space: pre-wrap; }}

/* ── 地图区 ── */
#map-panel {{
  flex: 1;
  position: relative;
  overflow: hidden;
  min-height: 200px;
}}
#map-svg {{ width: 100%; height: 100%; cursor: grab; display: block; }}
#map-svg.dragging {{ cursor: grabbing; }}
#map-tooltip {{
  position: absolute; pointer-events: none; display: none;
  background: rgba(255,255,255,0.96); border: 1px solid #ccc;
  border-radius: 6px; padding: 6px 10px; font-size: 12px;
  max-width: 200px; line-height: 1.6; z-index: 20;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}}
#map-tooltip strong {{ font-size: 13px; color: #222; display: block; margin-bottom: 2px; }}

/* ── 时间轴区（右侧竖排） ── */
#tl-panel {{
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid #e0d8c8;
  background: #fff;
}}
#tl-header {{
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  border-bottom: 1px solid #e0d8c8;
  flex-shrink: 0;
}}
#tl-outer {{
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 8px;
}}
#tl-track {{
  position: relative;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
}}
#tl-axis {{ position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background:#bbb; transform: translateX(-50%); }}
.tick {{ position: relative; display: flex; align-items: center; min-height: 40px; padding: 0 6px; }}
.tick-line {{ width: 100%; display: flex; align-items: center; gap: 4px; }}
.tick-major .tick-line::before {{ content: ''; width: 8px; height: 1px; background: #aaa; }}
.tick-major .tick-line::after {{ content: ''; flex: 1; height: 1px; background: #aaa; }}
.tick-minor .tick-line::before {{ content: ''; width: 5px; height: 1px; background: #ccc; }}
.tick-minor .tick-line::after {{ content: ''; flex: 1; height: 1px; background: #ccc; }}
.tick-label {{ font-size: 10px; color: #aaa; white-space: nowrap; min-width: 28px; text-align: center; }}
.ev {{
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
  transition: background .12s;
}}
.ev:hover {{ background: #f0f0f0; }}
.ev.sel {{ background: #e8f4f0; }}
.ev-dot {{
  width: 10px; height: 10px; border-radius: 50%;
  border: 1.5px solid #fff; flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}}
.ev-lbl {{ font-size: 11px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ev.sel .ev-lbl {{ color: #222; font-weight: 600; }}
.ev-year {{ font-size: 10px; color: #aaa; flex-shrink: 0; }}
.ev.sel .ev-year {{ color: #666; }}

/* ── 详情面板 ── */
#detail {{
  margin: 8px; padding: 10px 14px;
  background:#fff; border:1px solid #e0d8c8; border-radius:8px;
  min-height: 80px; flex-shrink: 0;
}}
.d-hint {{ font-size:12px; color:#bbb; line-height:2.5; }}
.d-year {{ font-size:11px; color:#aaa; margin-bottom:2px; }}
.d-title {{ font-size:14px; font-weight:600; color:#222; margin-bottom:4px; }}
.d-desc {{ font-size:12px; color:#555; line-height:1.7; margin-bottom:6px; }}
.d-places {{ display:flex; gap:4px; flex-wrap:wrap; }}
.d-place-tag {{
  font-size:10px; padding:1px 7px; border-radius:4px;
  background:#f0f0f0; color:#555; cursor:pointer;
  border:1px solid #ddd; transition:all .12s;
}}
.d-place-tag:hover {{ background:#e0e8f0; color:#333; border-color:#aaa; }}
.d-place-tag.active {{ background:#085041; color:#fff; border-color:#085041; }}
#ev-count {{ font-size:10px; color:#bbb; padding:3px 8px 6px; flex-shrink:0; }}
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
  <div class="sep"></div>
  <button class="tb layer-on" id="btn-city" onclick="toggleLayer('city',this)">地名</button>
  <button class="tb layer-on" id="btn-mtn" onclick="toggleLayer('mtn',this)">山脉</button>
</div>

<div id="main">
  <!-- 左侧：答案文本 + 地图 -->
  <div id="left-panel">
    <div id="answer-box">
      <div class="ans-title">{title}</div>
      <div class="ans-text"></div>
    </div>
    <div id="map-panel">
      <svg id="map-svg"></svg>
      <div id="map-tooltip"></div>
    </div>
  </div>

  <!-- 右侧：时间轴（竖排） -->
  <div id="tl-panel">
    <div id="tl-header">时间轴</div>
    <div id="tl-outer">
      <div id="tl-track">
        <div id="tl-axis"></div>
      </div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
// ── 数据 ─────────────────────────────────────────────────────
const EVENTS = {events_js};
const PLACES = {places_js};
const Y_START = {y_start};
const Y_END   = {y_end};

const CAT = {{
  mil: {{ color:'#534AB7', bg:'#EEEDFE', label:'军事' }},
  pol: {{ color:'#0F6E56', bg:'#E1F5EE', label:'政治' }},
  eco: {{ color:'#854F0B', bg:'#FAEEDA', label:'财政' }},
  nat: {{ color:'#993C1D', bg:'#FAECE7', label:'灾异' }},
}};

const MOUNTAINS = [
  {{name:'天山',       pts:[[68,40],[76,42],[84,43],[92,42],[88,42],[80,42],[72,40]]}},
  {{name:'昆仑山',     pts:[[74,36],[82,36],[90,36],[98,35],[90,35],[82,35],[74,35]]}},
  {{name:'秦岭',       pts:[[104,33],[107,34],[110,34],[113,33],[110,33],[107,33],[104,33]]}},
  {{name:'喜马拉雅山', pts:[[80,28],[86,28],[92,27],[96,28],[92,29],[86,29],[80,29]]}},
  {{name:'大兴安岭',   pts:[[118,48],[120,50],[122,52],[120,50],[118,47]]}},
];

// ── 状态 ──────────────────────────────────────────────────────
let shownCats = new Set(['mil','pol','eco','nat']);
let selIdx    = -1;
let highlighted = new Set(); // 当前高亮的地名
const layerState = {{ city: true, mtn: true }};

// ── 地图初始化 (D3) ───────────────────────────────────────────
let svg, g, proj, zoom;
let mapW = 600, mapH = 400;

function initMap() {{
  const mapPanel = document.getElementById('map-panel');
  if (!mapPanel) return;
  mapW = mapPanel.offsetWidth  || 600;
  mapH = mapPanel.offsetHeight || 400;
  if (mapW < 10 || mapH < 10) mapW = 600, mapH = 400;

  svg  = d3.select('#map-svg').attr('viewBox', `0 0 ${{mapW}} ${{mapH}}`);
  g    = svg.append('g');

  proj = d3.geoMercator().center([105, 35]).scale(mapW * 0.7).translate([mapW/2, mapH/2]);
  const path = d3.geoPath().projection(proj);

  zoom = d3.zoom().scaleExtent([0.4, 16])
    .on('zoom', e => {{ g.attr('transform', e.transform); scaleMarkers(e.transform.k); }});
  svg.call(zoom)
    .on('mousedown.zoom', () => svg.classed('dragging', true))
    .on('mouseup.zoom mouseleave.zoom', () => svg.classed('dragging', false));

  // 背景
  svg.insert('rect','g').attr('width',mapW).attr('height',mapH).attr('fill','#b8d8ea');
  g.append('rect').attr('id','el-land')
    .attr('x',-2000).attr('y',-2000).attr('width',6000).attr('height',6000)
    .attr('fill','#e8dfc0').attr('opacity',0);

  drawMap();
}}

// 等 DOM + 布局完成后再初始化
if (document.readyState === 'complete') {{
  requestAnimationFrame(() => requestAnimationFrame(initMap));
}} else {{
  window.addEventListener('load', () => requestAnimationFrame(() => requestAnimationFrame(initMap)));
}}

// 尝试加载世界地图
(async () => {{
  await new Promise(r => setTimeout(r, 100)); // 等 initMap 完成
  if (!g) return;
  try {{
    const topojs = await import('https://cdn.skypack.dev/topojson-client@3');
    const world = await d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
    g.insert('path','.layer-city')
      .datum(topojs.feature(world, world.objects.land))
      .attr('fill','#e8dfc0').attr('stroke','#a09060').attr('stroke-width',0.4)
      .attr('d', path);
    g.insert('path','.layer-city')
      .datum(topojs.mesh(world, world.objects.countries, (a,b)=>a!==b))
      .attr('fill','none').attr('stroke','#a09060').attr('stroke-width',0.5)
      .attr('d', path);
  }} catch(e) {{
    // 降级：只显示简单底色
    g.insert('rect','g').attr('x',-2000).attr('y',-2000)
     .attr('width',6000).attr('height',6000).attr('fill','#e8dfc0');
  }}
}})();
  try {{
    const topojs = await import('https://cdn.skypack.dev/topojson-client@3');
    const world = await d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
    g.insert('path','.layer-city')
      .datum(topojs.feature(world, world.objects.land))
      .attr('fill','#e8dfc0').attr('stroke','#a09060').attr('stroke-width',0.4)
      .attr('d', path);
    g.insert('path','.layer-city')
      .datum(topojs.mesh(world, world.objects.countries, (a,b)=>a!==b))
      .attr('fill','none').attr('stroke','#a09060').attr('stroke-width',0.5)
      .attr('d', path);
  }} catch(e) {{
    // 降级：只显示简单底色
    if (g) {{
      g.insert('rect','g').attr('x',-2000).attr('y',-2000)
       .attr('width',6000).attr('height',6000).attr('fill','#e8dfc0');
    }}
  }}
  if (g) drawMap();
}})();

function drawMap() {{
  const tip = document.getElementById('map-tooltip');

  // 山脉层
  const mtnG = g.append('g').attr('id','layer-mtn');
  const mtnLG = g.append('g').attr('id','layer-mtn-label');
  MOUNTAINS.forEach(m => {{
    const pts = m.pts.map(([lo,la]) => proj([lo,la]));
    const d = pts.map((p,i) => `${{i?'L':'M'}}${{p[0].toFixed(1)}},${{p[1].toFixed(1)}}`).join(' ')+'Z';
    mtnG.append('path').attr('d',d).attr('fill','#c8b898').attr('stroke','#a08868')
      .attr('stroke-width',1).attr('opacity',0.5);
    const cx = d3.mean(m.pts, d=>d[0]);
    const cy = d3.mean(m.pts, d=>d[1]);
    const [x,y] = proj([cx,cy]);
    mtnLG.append('text').attr('x',x).attr('y',y).attr('text-anchor','middle')
      .attr('font-size',8).attr('font-style','italic').attr('fill','#776655')
      .attr('paint-order','stroke').attr('stroke','#e8dfc0').attr('stroke-width',2.5)
      .text(m.name);
  }});

  // 地名层
  const cityG = g.append('g').attr('id','layer-city');
  PLACES.forEach((p, pi) => {{
    const [x,y] = proj([p.lo, p.la]);
    if (x<-100||x>mapW+100||y<-100||y>mapH+100) return;

    const gr = cityG.append('g')
      .attr('class','place')
      .attr('data-name', p.n)
      .attr('transform', `translate(${{x.toFixed(1)}},${{y.toFixed(1)}})`)
      .style('cursor','pointer')
      .on('mouseover', ev => {{
        tip.style.display = 'block';
        tip.innerHTML = `<strong>${{p.n}}</strong>${{p.i||''}}`;
      }})
      .on('mousemove', ev => {{
        const mp = document.getElementById('map-panel');
        const r = mp.getBoundingClientRect();
        tip.style.left = (ev.clientX - r.left + 14) + 'px';
        tip.style.top  = (ev.clientY - r.top  - 44) + 'px';
      }})
      .on('mouseout', () => tip.style.display = 'none')
      .on('click', () => onPlaceClick(p.n));

    const r = p.t==='cap' ? 4 : p.t==='prov' ? 3 : 2.5;
    gr.append('circle').attr('class','place-dot').attr('r', r)
      .attr('fill', placeColor(p.t, false))
      .attr('stroke','#fff').attr('stroke-width',0.8);

    gr.append('text').attr('class','place-label')
      .attr('x',5).attr('y',4)
      .attr('font-size', p.t==='cap'?10:8.5)
      .attr('font-weight', p.t==='cap'?'bold':'normal')
      .attr('fill', placeColor(p.t, false))
      .attr('paint-order','stroke').attr('stroke','#e8dfc0').attr('stroke-width',2.5)
      .text(p.n);
  }});
}}

function placeColor(type, hl) {{
  if (hl) return '#e05000';
  return type==='cap'?'#cc3300':type==='prov'?'#223388':type==='battle'?'#8b0000':'#667755';
}}

function scaleMarkers(k) {{
  g.selectAll('.place').each(function() {{
    const t = d3.select(this).attr('transform');
    const m = t.match(/translate\(([^,]+),([^)]+)\)/);
    if (!m) return;
    d3.select(this).attr('transform',
      `translate(${{m[1]}},${{m[2]}}) scale(${{(1/k).toFixed(4)}})`);
  }});
  g.select('#layer-mtn-label').selectAll('text')
    .attr('transform', `scale(${{(1/k).toFixed(4)}})`);
}}

function toggleLayer(name, btn) {{
  layerState[name] = !layerState[name];
  btn.classList.toggle('layer-on', layerState[name]);
  g.select(`#layer-${{name}}`).attr('display', layerState[name] ? null : 'none');
  if (name==='mtn') g.select('#layer-mtn-label').attr('display', layerState[name] ? null : 'none');
}}

// ── 高亮地图地名 ──────────────────────────────────────────────
function setHighlightedPlaces(names) {{
  highlighted = new Set(names);
  g.selectAll('.place').each(function() {{
    const name = this.getAttribute('data-name');
    const hl   = highlighted.has(name);
    const p    = PLACES.find(p => p.n === name);
    if (!p) return;
    d3.select(this).select('.place-dot')
      .attr('r', hl ? 6 : (p.t==='cap'?4:p.t==='prov'?3:2.5))
      .attr('fill', placeColor(p.t, hl));
    d3.select(this).select('.place-label')
      .attr('fill', placeColor(p.t, hl))
      .attr('font-weight', hl ? 'bold' : (p.t==='cap'?'bold':'normal'));
  }});
}}

// ── 点击地名 → 时间轴跳转 ─────────────────────────────────────
function onPlaceClick(name) {{
  // 找第一个包含该地名的事件
  const vis = EVENTS.filter(e => shownCats.has(e.cat));
  const idx  = vis.findIndex(e => (e.places||[]).includes(name));
  if (idx >= 0) {{
    const globalIdx = EVENTS.indexOf(vis[idx]);
    pickEvent(globalIdx);
  }}
}}

// ── 时间轴（竖排） ───────────────────────────────────────────
function renderTimeline() {{
  const track = document.getElementById('tl-track');
  const axis = document.getElementById('tl-axis');
  let h = '';

  // Build sorted year ticks
  const step = (Y_END - Y_START) > 500 ? 50 : (Y_END - Y_START) > 200 ? 20 : 10;
  const tickYears = [];
  for (let y = Y_START; y <= Y_END; y += step) {{
    tickYears.push(y);
  }}

  // Interleave events with year ticks
  const vis = EVENTS.filter(e => shownCats.has(e.cat));
  vis.sort((a, b) => a.y - b.y);

  // Build tick→events map
  const tickEvents = {{}};
  tickYears.forEach(ty => {{ tickEvents[ty] = []; }});
  let lastTick = tickYears[0];
  vis.forEach(e => {{
    // find nearest tick below
    const tick = tickYears.filter(ty => ty <= e.y).pop() || tickYears[0];
    tickEvents[tick].push(e);
  }});

  tickYears.forEach((ty, ti) => {{
    // Tick row with year label on left
    h += `<div class="tick">
      <div class="tick-line">
        <span class="tick-label">${{ty}}</span>
      </div>
    </div>`;
    // Events at this tick
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

function pickEvent(idx) {{
  selIdx = idx;
  renderTimeline();
  const e = EVENTS[idx];
  setHighlightedPlaces(e.places || []);
  // Update answer box text (detail panel removed)
  document.querySelector('#answer-box .ans-text').textContent =
    (e.desc ? e.desc + '\n\n' : '') + '相关地点：' + (e.places || []).join(', ');
}}

function focusPlace(name) {{
  const p = PLACES.find(p => p.n === name);
  if (!p) return;
  const [x, y] = proj([p.lo, p.la]);
  const scale = 4;
  svg.transition().duration(600).call(
    zoom.transform,
    d3.zoomIdentity.translate(W/2 - scale*x, H/2 - scale*y).scale(scale)
  );
}}

function toggleCat(cat, btn) {{
  if (shownCats.has(cat)) {{ shownCats.delete(cat); btn.className='tb'; }}
  else {{ shownCats.add(cat); btn.className=`tb on-${{cat}}`; }}
  selIdx = -1;
  setHighlightedPlaces([]);
  renderTimeline();
}}

// ── 初始化 ───────────────────────────────────────────────────
renderTimeline();
</script>
</body>
</html>"""
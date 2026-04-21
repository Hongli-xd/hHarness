"""Map Location Tool - renders historical places on an interactive map."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult


# Resources directory relative to this file
_RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"


class Place(BaseModel):
    """A historical place/location."""
    name: str = Field(description="Place name")
    longitude: float = Field(description="Longitude (east positive)")
    latitude: float = Field(description="Latitude (north positive)")
    place_type: str = Field(
        default="hist",
        description="Type: cap (capital), prov (provincial), hist (historical city), "
                   "pass (pass), battle (battlefield), port (port), region (region)",
    )
    info: str | None = Field(default=None, description="Description/info tooltip")
    connections: list[str] = Field(default_factory=list, description="Names of connected places")


class MapLocationInput(BaseModel):
    """Input schema for the Map Location Tool."""
    places: list[Place] = Field(description="List of places to display on the map")
    title: str = Field(default="历史地图", description="Map title")
    highlight_places: list[str] = Field(
        default_factory=list,
        description="Place names to highlight (show as selected)",
    )


class MapLocationTool(BaseTool):
    """历史地图可视化工具。

在可缩放的SVG地图上渲染历史地名，
包含河流、山脉、城市等图层，
以及地名之间的关联线。

【功能】
- 生成可交互的HTML历史地图
- 支持平移和缩放（鼠标滚轮+拖拽）
- 主题切换（自然/羊皮纸/暗色）
- 图层开关（河流、湖泊、山脉、城市）
- 悬停显示地名信息
- 关联地之间的连线
"""

    name = "map_location"
    description = """在交互式地图上展示历史地名。

【输入】
地名列表，包含名称、经纬度坐标、类型、信息

【输出】
完整的HTML文件，展示带有地名标记的交互式地图

【使用场景】
- 用户要求"把地点标在地图上"
- "描绘历史地点"
- "在地图上查看"
- 可视化历史地名之间的地理关系

【地图功能】
- 平移和缩放（滚轮缩放+拖拽平移）
- 主题切换（自然色/羊皮纸/暗色）
- 图层开关（河流、湖泊、山脉、城市）
- 悬停显示地名详细信息
- 关联地之间的连线
"""
    input_model = MapLocationInput

    def get_schema_overrides(self) -> dict[str, Any]:
        """返回中文Schema描述"""
        return {
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "places": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "地名名称"},
                                "longitude": {"type": "number", "description": "经度（东经为正）"},
                                "latitude": {"type": "number", "description": "纬度（北纬为正）"},
                                "place_type": {
                                    "type": "string",
                                    "enum": ["cap", "prov", "hist", "pass", "battle", "port", "region"],
                                    "description": "地点类型：\n- cap：首都/直辖市\n- prov：省会/首府\n- hist：历史城市\n- pass：关隘/山口\n- battle：战场\n- port：港口\n- region：区域"
                                },
                                "info": {"type": "string", "description": "地名描述/信息提示"},
                                "connections": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "关联地名列表，会在地图上画连线"
                                }
                            },
                            "required": ["name", "longitude", "latitude", "place_type"]
                        },
                        "description": "地点列表，每个地点包含：\n- name：地名\n- longitude：经度\n- latitude：纬度\n- place_type：类型\n- info：描述（可选）\n- connections：关联地名列表（可选）"
                    },
                    "title": {
                        "type": "string",
                        "default": "历史地图",
                        "description": "地图标题"
                    },
                    "highlight_places": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要高亮显示的地名列表"
                    }
                },
                "required": ["places"]
            }
        }

    def is_read_only(self, arguments: MapLocationInput) -> bool:
        return True

    async def execute(
        self, arguments: MapLocationInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Generate the map HTML."""
        places = arguments.places
        if not places:
            return ToolResult(output="No places provided for map.", is_error=True)

        places_json = self._build_places_json(places)
        highlight_set = arguments.highlight_places

        html = self._generate_html(
            title=arguments.title,
            places_json=places_json,
            highlight_set=highlight_set,
        )

        return ToolResult(
            output=f"[Map generated with {len(places)} places]\n\n"
            f"Map HTML ({len(html)} bytes) ready at: map.html\n\n"
            f"Places:\n" + "\n".join(f"  {p.name}: [{p.longitude},{p.latitude}] ({p.place_type})" for p in places[:10])
            + (f"\n  ... and {len(places) - 10} more" if len(places) > 10 else ""),
            metadata={"html": html, "place_count": len(places)},
        )

    def _build_places_json(self, places: list[Place]) -> str:
        import json
        items = []
        for p in places:
            items.append({
                "n": p.name,
                "lo": p.longitude,
                "la": p.latitude,
                "t": p.place_type,
                "mz": 1,
                "i": p.info or "",
            })
        return json.dumps(items, ensure_ascii=False)

    def _generate_html(
        self,
        title: str,
        places_json: str,
        highlight_set: list[str],
    ) -> str:
        # Try to load the original map.html as template to preserve all geo data
        template_path = Path(__file__).parent.parent.parent.parent / "map" / "map.html"
        try:
            with open(template_path, encoding="utf-8") as f:
                tmpl = f.read()
        except Exception:
            # Fallback: build HTML from scratch
            return self._fallback_html(title, places_json, highlight_set)

        import json, re

        # Replace asset paths with URL paths relative to the HTTP server root
        # Resources are at: Harness/histrag/resources/
        # When serving from project root, URL path is: /Harness/histrag/resources/
        res_url = "/Harness/histrag/resources"
        tmpl = tmpl.replace("./assets/lib/", f"{res_url}/lib/")
        tmpl = tmpl.replace("./assets/data/", f"{res_url}/data/")

        # Replace PLACES array with our dynamic data
        # The original has: const PLACES = [ ... ];
        places_block = "const PLACES = " + places_json + ";"

        def replace_places(m):
            return places_block

        tmpl = re.sub(
            r"const PLACES = \[.*?\];",
            replace_places,
            tmpl,
            flags=re.DOTALL,
        )

        # Inject HIGHLIGHT set right after the PLACES block
        hl_js = "const HIGHLIGHT = new Set(" + json.dumps(list(highlight_set) if highlight_set else []) + ");"
        places_end = tmpl.find("];", tmpl.find("const PLACES")) + 2
        tmpl = tmpl[:places_end] + "\n" + hl_js + "\n" + tmpl[places_end:]
        # Replace title
        tmpl = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", tmpl)
        # Replace h1 title
        tmpl = re.sub(r"<h1>.*?</h1>", f"<h1>{title}</h1>", tmpl)
        return tmpl

    def _build_css(self) -> str:
        return """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f3ee; }
#app { display: flex; flex-direction: column; height: 100vh; }
#toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 12px; background: #fff; border-bottom: 1px solid #e0d8c8; }
#toolbar h1 { font-size: 14px; font-weight: 600; color: #333; margin-right: 4px; }
.sep { width: 1px; height: 18px; background: #ddd; }
.tb { font-size: 11px; padding: 3px 12px; border-radius: 20px; border: 1px solid #ccc; background: transparent; color: #666; cursor: pointer; transition: all .15s; }
.tb:hover { border-color: #999; color: #333; }
.tb.on { background: #085041; color: #fff; border-color: #085041; }
.tb.layer-on { background: #e8f4f0; color: #085041; border-color: #5DCAA5; }
#status { font-size: 11px; color: #999; }
#zoom-hint { font-size: 11px; color: #bbb; margin-left: auto; }
#map-wrap { flex: 1; position: relative; overflow: hidden; }
#map-svg { display: block; width: 100%; height: 100%; cursor: grab; }
#map-svg.dragging { cursor: grabbing; }
#tooltip { position: absolute; pointer-events: none; background: rgba(255,255,255,0.96); border: 1px solid #ccc; border-radius: 6px; padding: 6px 10px; font-size: 12px; display: none; max-width: 220px; line-height: 1.6; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
#tooltip strong { font-size: 13px; color: #222; display: block; margin-bottom: 2px; }
#legend { position: absolute; bottom: 12px; left: 12px; background: rgba(255,255,255,0.9); border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; font-size: 11px; color: #555; line-height: 2; }
.leg-row { display: flex; align-items: center; gap: 6px; }
.leg-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.leg-line { width: 16px; height: 2px; flex-shrink: 0; }"""

    def _build_body(self, title: str) -> str:
        return '''<body>
<div id="app">
  <div id="toolbar">
    <h1>''' + title + '''</h1>
    <div class="sep"></div>
    <button class="tb on" onclick="setTheme('natural',this)">自然</button>
    <button class="tb" onclick="setTheme('parchment',this)">羊皮纸</button>
    <button class="tb" onclick="setTheme('dark',this)">暗色</button>
    <div class="sep"></div>
    <button class="tb layer-on" id="btn-river" onclick="toggleLayer('river',this)">河流</button>
    <button class="tb layer-on" id="btn-lake" onclick="toggleLayer('lake',this)">湖泊</button>
    <button class="tb layer-on" id="btn-mtn" onclick="toggleLayer('mtn',this)">山脉</button>
    <button class="tb layer-on" id="btn-city" onclick="toggleLayer('city',this)">城市</button>
    <span id="status"></span>
    <span id="zoom-hint">滚轮缩放 · 拖动平移 · 悬停查看信息</span>
  </div>
  <div id="map-wrap">
    <svg id="map-svg"></svg>
    <div id="tooltip"></div>
    <div id="legend">
      <div class="leg-row"><div class="leg-dot" style="background:#cc3300"></div> 首都 / 直辖市</div>
      <div class="leg-row"><div class="leg-dot" style="background:#2255aa"></div> 省会 / 首府</div>
      <div class="leg-row"><div class="leg-dot" style="background:#667755"></div> 历史城市</div>
      <div class="leg-row"><div class="leg-line" style="background:#5599cc"></div> 河流</div>
    </div>
  </div>
</div>'''

    def _fallback_html(
        self,
        title: str,
        places_json: str,
        highlight_set: list[str],
    ) -> str:
        import json

        res_url = "/Harness/histrag/resources"
        hl_set = json.dumps(list(highlight_set) if highlight_set else [])

        d3_src = res_url + "/lib/d3.min.js" if os.path.exists(_RESOURCES_DIR / "lib" / "d3.min.js") else "https://d3js.org/d3.v7.min.js"
        topo_src = res_url + "/lib/topojson.min.js" if os.path.exists(_RESOURCES_DIR / "lib" / "topojson.min.js") else "https://cdn.jsdelivr.net/npm/topojson-client@3"

        # Build using string concatenation to avoid f-string / brace escaping issues
        css = self._build_css()
        body = self._build_body(title)
        js = self._build_js(places_json, hl_set)

        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"zh\">\n"
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "<title>" + title + "</title>\n"
            "<style>\n" + css + "</style>\n"
            "</head>\n"
            + body + "\n"
            '<script src="' + d3_src + '"></script>\n'
            '<script src="' + topo_src + '"></script>\n'
            "<script>\n" + js + "</script>\n"
            "</body>\n"
            "</html>"
        )

    def _build_js(self, places_json: str, hl_set: str) -> str:
        # JS with only SINGLE braces for actual JS code (CSS uses double braces in source)
        return """const THEMES = {
  natural: {
    sphere:'#b8d8ea', land:'#e8dfc0', border:'#a09060', grid:'#aaccdd',
    river:'#5599cc', lake:'#7ab8d4', lakeStroke:'#4488aa',
    mtnFill:'#c8b898', mtnStroke:'#a08868',
    cap:'#cc3300', prov:'#223388', hist:'#667755',
    region:'#445533', mtn:'#776655', sea:'#336688',
  },
  parchment: {
    sphere:'#c4b070', land:'#f0e4b4', border:'#806030', grid:'#a08040',
    river:'#7799aa', lake:'#8899aa', lakeStroke:'#667788',
    mtnFill:'#c8b070', mtnStroke:'#906030',
    cap:'#801000', prov:'#1a2860', hist:'#3a5020',
    region:'#3a4010', mtn:'#604020', sea:'#5a4010',
  },
  dark: {
    sphere:'#0d1a2a', land:'#252e3c', border:'#3a4a5a', grid:'#162030',
    river:'#2a6a9a', lake:'#1a4a6a', lakeStroke:'#2a6a8a',
    mtnFill:'#1e2a38', mtnStroke:'#3a4a58',
    cap:'#ff9966', prov:'#66aadd', hist:'#88aa77',
    region:'#88aa66', mtn:'#aa9977', sea:'#4499bb',
  },
};
let T = THEMES.natural;

const HIGHLIGHT = new Set(""" + hl_set + """);

const MOUNTAINS = [
  {name:'天山', pts:[[68,40],[72,41],[76,42],[80,43],[84,43],[88,43],[92,42],[88,42],[84,42],[80,42],[76,41],[72,40]]},
  {name:'昆仑山', pts:[[74,36],[78,36],[82,36],[86,36],[90,36],[94,36],[98,35],[94,35],[90,35],[86,35],[82,35],[78,35],[74,35]]},
  {name:'秦岭', pts:[[104,33],[107,34],[110,34],[113,33],[110,33],[107,33],[104,33]]},
  {name:'阿尔泰山', pts:[[84,47],[87,48],[90,49],[93,49],[90,48],[87,47],[84,47]]},
  {name:'大兴安岭', pts:[[118,48],[120,50],[122,52],[124,52],[122,50],[120,48],[118,47]]},
  {name:'帕米尔高原', pts:[[70,36],[73,37],[76,38],[76,37],[73,36],[70,35]]},
];

const FALLBACK_RIVERS = [
  {n:'黄河', w:1.4, pts:[[96,35],[100,34],[104,36],[108,35],[110,33],[114,34],[116,35],[117,36],[119,37]]},
  {n:'长江', w:1.4, pts:[[92,30],[98,30],[102,28],[106,29],[110,30],[114,30],[117,30],[120,31],[121,31]]},
  {n:'黑龙江',w:1.0, pts:[[118,52],[115,50],[110,50],[106,52],[102,54]]},
];

const PLACES_DATA = """ + places_json + """;

const wrap = document.getElementById('map-wrap');
const W = wrap.offsetWidth || 900;
const H = wrap.offsetHeight || 580;

const svg = d3.select('#map-svg').attr('viewBox', '0 0 ' + W + ' ' + H);
const defs = svg.append('defs');
const g = svg.append('g');

const proj = d3.geoMercator().center([90, 35]).scale(W * 0.85).translate([W/2, H/2]);
const path = d3.geoPath().projection(proj);

const zoomBehavior = d3.zoom().scaleExtent([0.4, 16])
  .on('zoom', function(e) { g.attr('transform', e.transform); updateVisibility(e.transform.k); });
svg.call(zoomBehavior)
  .on('mousedown.zoom', function() { svg.classed('dragging', true); })
  .on('mouseup.zoom mouseleave.zoom', function() { svg.classed('dragging', false); });

const layerState = { river: true, lake: true, mtn: true, city: true };

function toggleLayer(name, btn) {
  layerState[name] = !layerState[name];
  btn.classList.toggle('layer-on', layerState[name]);
  g.select('#layer-' + name).attr('display', layerState[name] ? null : 'none');
  if (name === 'mtn') g.select('#layer-mtn-label').attr('display', layerState[name] ? null : 'none');
}

async function init() {
  var tip = document.getElementById('tooltip');

  g.append('path').attr('id','el-sphere').datum({type:'Sphere'}).attr('fill', T.sphere).attr('d', path);
  g.append('path').attr('id','el-grid').datum(d3.geoGraticule().step([10,10])()).attr('fill','none').attr('stroke', T.grid).attr('stroke-width', 0.3).attr('d', path);
  g.append('rect').attr('id','el-land').attr('x',0).attr('y',0).attr('width',W).attr('height',H).attr('fill', T.land);

  var riverG = g.append('g').attr('id','layer-river');
  FALLBACK_RIVERS.forEach(function(r) {
    var line = d3.line()(r.pts.map(function(ll) { return proj(ll); }));
    riverG.append('path').attr('d',line).attr('fill','none').attr('stroke', T.river).attr('stroke-width', r.w).attr('stroke-opacity', 0.75);
  });

  var mtnG = g.append('g').attr('id','layer-mtn');
  MOUNTAINS.forEach(function(m) {
    var pts = m.pts.map(function(ll) { return proj(ll); });
    var d = pts.map(function(p,i) { return (i?'L':'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') + 'Z';
    mtnG.append('path').attr('d',d).attr('fill',T.mtnFill).attr('stroke',T.mtnStroke).attr('stroke-width',1.2).attr('opacity',0.55);
    mtnG.append('path').attr('d',d).attr('fill','none').attr('stroke','#fff').attr('stroke-width',0.5).attr('opacity',0.28);
  });

  var mtnLabelG = g.append('g').attr('id','layer-mtn-label');
  MOUNTAINS.forEach(function(m) {
    var cx = d3.mean(m.pts, function(d) { return d[0]; });
    var cy = d3.mean(m.pts, function(d) { return d[1]; });
    var xy = proj([cx,cy]);
    mtnLabelG.append('text').attr('x',xy[0]).attr('y',xy[1]).attr('text-anchor','middle').attr('font-size',8).attr('font-style','italic').attr('fill', T.mtn).attr('paint-order','stroke').attr('stroke', T.sphere).attr('stroke-width',2.5).text(m.name);
  });

  var cityG = g.append('g').attr('id','layer-city');
  PLACES_DATA.forEach(function(p) {
    var xy = proj([p.lo, p.la]);
    if (xy[0]<-80||xy[0]>W+80||xy[1]<-80||xy[1]>H+80) return;

    var hasPoint = ['cap','prov','hist'].indexOf(p.t) >= 0;
    var isCenter = ['sea','region'].indexOf(p.t) >= 0;
    var isHighlight = HIGHLIGHT.has(p.n);

    var gr = cityG.append('g').attr('class', 'place mz1')
      .attr('transform', 'translate(' + xy[0].toFixed(1) + ',' + xy[1].toFixed(1) + ')')
      .style('cursor', p.i ? 'pointer' : 'default');
    if (p.i) {
      gr.on('mouseover', function(ev) { tip.style.display = 'block'; tip.innerHTML = '<strong>' + p.n + '</strong>' + p.i; })
        .on('mousemove', function(ev) { var r = wrap.getBoundingClientRect(); tip.style.left = (ev.clientX - r.left + 14) + 'px'; tip.style.top = (ev.clientY - r.top - 44) + 'px'; })
        .on('mouseout', function() { tip.style.display = 'none'; });
    }

    if (hasPoint) {
      var r = p.t === 'cap' ? 3.5 : 2.2;
      var fc = isHighlight ? '#ff6600' : p.t === 'cap' ? T.cap : p.t === 'hist' ? T.hist : T.prov;
      gr.append('circle').attr('r', r * (isHighlight ? 1.4 : 1)).attr('fill', fc).attr('stroke', '#fff').attr('stroke-width', isHighlight ? 1.5 : 0.7);
    }

    var col = p.t === 'cap' ? T.cap : p.t === 'prov' ? T.prov : p.t === 'hist' ? T.hist : p.t === 'sea' ? T.sea : p.t === 'region' ? T.region : T.mtn;
    var fs = p.t === 'cap' ? 11 : p.t === 'prov' ? 9.5 : p.t === 'hist' ? 8.5 : p.t === 'region' ? 9 : 8;
    var anchor = isCenter ? 'middle' : 'start';
    var offset = isCenter ? 0 : 4;
    gr.append('text').attr('x', offset).attr('y', isCenter ? 0 : 3.5).attr('text-anchor', anchor).attr('font-size', fs).attr('font-weight', p.t === 'cap' ? 'bold' : 'normal').attr('font-style', isCenter ? 'italic' : 'normal').attr('fill', isHighlight ? '#ff6600' : col).attr('paint-order', 'stroke').attr('stroke', T.sphere).attr('stroke-width', 2.5).text(p.n);
  });

  updateVisibility(1);
}

function updateVisibility(k) {
  var lv = k >= 3.5 ? 3 : k >= 1.8 ? 2 : 1;
  g.selectAll('.place').each(function() {
    var cls = this.className ? this.className.baseVal : '';
    var mz = parseInt(cls.match(/mz(\d)/) ? cls.match(/mz(\d)/)[1] : 1);
    var t = d3.select(this).attr('transform');
    var m = t.match(/translate\(([^,]+),([^\)]+)\)/);
    var base = m ? 'translate(' + m[1] + ',' + m[2] + ')' : t;
    d3.select(this).attr('display', mz <= lv ? null : 'none').attr('transform', base + ' scale(' + (1/k).toFixed(4) + ')');
  });
  g.select('#layer-mtn-label').selectAll('text').attr('transform', 'scale(' + (1/k).toFixed(4) + ')');
  g.select('#layer-mtn-label').attr('transform', null);
}

function applyTheme() {
  g.select('#el-sphere').attr('fill', T.sphere);
  g.select('#el-grid').attr('stroke', T.grid);
  g.select('#el-land').attr('fill', T.land);
  svg.style('background', T.sphere);
}

function setTheme(name, btn) {
  document.querySelectorAll('[onclick^="setTheme"]').forEach(function(b) { b.classList.remove('on'); });
  btn.classList.add('on');
  T = THEMES[name];
  applyTheme();
}

init().catch(function(e) { document.getElementById('status').textContent = 'Error: ' + e.message; });
window.addEventListener('resize', function() { location.reload(); });
"""

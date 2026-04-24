"""Linked View Tool — 3D 历史地图可视化工具。

使用 Three.js 实现真正的 3D 效果：
- 省份 ExtrudeGeometry 挤出，带厚度与倒角
- 逐省纬度海拔配色（西藏深、沿海浅）
- 粒子底座 + 双环旋转边框
- 飞线动画连接事件地点（带行进光点）
- GSAP 省份 hover 弹起动画
- DOM 标签投影叠加（CSS3D 效果）
- 事件面板 + 4 种主题色切换

⚠️  Three.js 和 GSAP 从本地 /resources/lib/ 加载（离线可用）。
    首次运行前请执行：
    cd Harness/histrag/resources && bash setup.sh
"""

from __future__ import annotations

import json
from pydantic import BaseModel, Field, field_validator
from ..agent import BaseTool, ToolExecutionContext, ToolResult


class LinkedEvent(BaseModel):
    model_config = {'extra': 'allow'}
    year: int = Field(description="事件年份（负数=公元前）")
    title: str = Field(default="未知事件", description="事件标题")
    description: str = Field(default="", description="事件描述")
    category: str = Field(default="pol", description="mil/pol/eco/nat")
    place_names: list[str] = Field(default_factory=list, description="该事件关联的地名列表")


class LinkedPlace(BaseModel):
    model_config = {'extra': 'allow'}
    name: str = Field(description="地名")
    longitude: float = Field(description="经度")
    latitude: float = Field(description="纬度")
    place_type: str = Field(default="hist", description="cap/prov/hist/pass/battle/port/region")
    info: str = Field(default="", description="地名描述")


class LinkedViewInput(BaseModel):
    events: list[LinkedEvent] = Field(description="时间事件列表")
    places: list[LinkedPlace] = Field(description="历史地名列表，包含经纬度")
    title: str = Field(default="历史研究视图", description="页面标题")

    @field_validator('events', 'places', mode='before')
    @classmethod
    def parse_json_string(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v


class LinkedViewTool(BaseTool):
    """3D 联动历史视图工具。"""

    name = "linked_view"
    description = """从回答内容中提取时间事件和历史地名，生成 3D 联动地图页面。
【必须传入】
- events：历史事件（年份+标题+描述+类别+关联地名）
- places：历史地名（名称+经纬度+类型+描述）
地名坐标使用今天中国地名对应的现代坐标，精度 0.1 度即可。
"""
    input_model = LinkedViewInput

    def is_read_only(self, arguments: LinkedViewInput) -> bool:
        return True

    async def execute(self, arguments: LinkedViewInput, context: ToolExecutionContext) -> ToolResult:
        if not arguments.events and not arguments.places:
            return ToolResult(output="No events or places provided.", is_error=True)

        html = self._generate_html(arguments)
        summary = (
            f"[LinkedView 3D: {len(arguments.events)} events, {len(arguments.places)} places]\n"
            + "\n".join(f"  {e.year}: {e.title}" for e in arguments.events[:5])
            + (f"\n  ...and {len(arguments.events)-5} more" if len(arguments.events) > 5 else "")
        )
        return ToolResult(
            output=summary,
            metadata={
                "html": html,
                "type": "linked_view",
                "events": [
                    {"y": e.year, "title": e.title, "desc": e.description,
                     "cat": e.category, "places": e.place_names}
                    for e in arguments.events
                ],
            },
        )

    def _generate_html(self, args: LinkedViewInput) -> str:
        events_js = json.dumps(
            [{"y": e.year, "title": e.title, "desc": e.description,
              "cat": e.category, "places": e.place_names}
             for e in args.events],
            ensure_ascii=False,
        )
        places_js = json.dumps(
            [{"n": p.name, "lo": p.longitude, "la": p.latitude,
              "t": p.place_type, "i": p.info}
             for p in args.places],
            ensure_ascii=False,
        )
        title = args.title

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:100%;height:100%;overflow:hidden;background:#030d18;font-family:'Noto Serif SC',sans-serif}}
#toolbar{{
  position:absolute;top:0;left:0;right:0;height:44px;z-index:100;
  display:flex;align-items:center;gap:8px;padding:0 16px;
  background:linear-gradient(to bottom,rgba(3,13,24,0.95),rgba(3,13,24,0));
  pointer-events:none;
}}
#toolbar>*{{pointer-events:all}}
#map-title{{font-size:13px;font-weight:600;letter-spacing:2px;color:#a0d4ff;
  text-shadow:0 0 12px rgba(100,200,255,0.6);margin-right:8px}}
.sep{{width:1px;height:16px;background:rgba(100,180,255,0.2)}}
.tb{{font-size:10px;padding:2px 10px;border-radius:12px;
  border:1px solid rgba(100,180,255,0.25);background:rgba(100,180,255,0.06);
  color:rgba(160,210,255,0.7);cursor:pointer;transition:all .15s;font-family:inherit}}
.tb:hover{{border-color:rgba(100,200,255,0.6);color:#a0d4ff}}
.tb.on-mil{{background:rgba(83,74,183,0.25);color:#AFA9EC;border-color:rgba(83,74,183,0.5)}}
.tb.on-pol{{background:rgba(15,110,86,0.25);color:#5DCAA5;border-color:rgba(15,110,86,0.5)}}
.tb.on-eco{{background:rgba(133,79,11,0.25);color:#EF9F27;border-color:rgba(133,79,11,0.5)}}
.tb.on-nat{{background:rgba(153,60,29,0.25);color:#F0997B;border-color:rgba(153,60,29,0.5)}}
#theme-sel{{margin-left:auto;font-size:10px;padding:2px 8px;border-radius:10px;
  border:1px solid rgba(100,180,255,0.25);background:rgba(3,13,24,0.6);
  color:rgba(160,210,255,0.8);cursor:pointer;font-family:inherit}}
#three-canvas{{position:absolute;inset:0;z-index:1;display:block;width:100%;height:100%}}
#label-container{{position:absolute;inset:0;z-index:10;pointer-events:none;overflow:hidden}}
.place-label{{position:absolute;pointer-events:all;cursor:pointer;
  transform:translate(-50%,-100%);text-align:center;transition:opacity .2s}}
.place-label .dot{{width:8px;height:8px;border-radius:50%;margin:0 auto 3px;
  border:1.5px solid rgba(255,255,255,0.5);
  box-shadow:0 0 6px currentColor,0 0 14px currentColor}}
.place-label .lname{{font-size:10px;color:#a8d8ff;white-space:nowrap;font-family:serif;
  text-shadow:0 0 7px rgba(80,180,255,0.9),0 1px 2px rgba(0,0,0,1)}}
.place-label.cap .dot{{width:10px;height:10px;color:#ff6040}}
.place-label.cap .lname{{font-size:11px;font-weight:600;color:#ffc8a0}}
.place-label.battle .dot{{border-radius:2px;transform:rotate(45deg);color:#ff4040}}
.place-label.hl .dot{{box-shadow:0 0 10px currentColor,0 0 22px currentColor,0 0 38px currentColor}}
.place-label.hl .lname{{color:#fff;text-shadow:0 0 10px rgba(255,210,120,1),0 1px 3px rgba(0,0,0,1)}}
#tt{{position:absolute;display:none;z-index:200;pointer-events:none;
  background:rgba(5,18,35,0.95);border:1px solid rgba(100,180,255,0.3);
  border-radius:6px;padding:8px 12px;font-size:11px;max-width:200px;line-height:1.7;
  box-shadow:0 4px 20px rgba(0,100,200,0.3)}}
#tt strong{{font-size:12px;color:#a0d4ff;display:block;margin-bottom:2px}}
#tt span{{color:rgba(160,200,240,0.7)}}
#ev-panel{{position:absolute;bottom:40px;left:50%;transform:translateX(-50%);
  z-index:100;display:none;
  background:rgba(5,18,35,0.92);border:1px solid rgba(100,180,255,0.25);
  border-radius:8px;padding:10px 16px;min-width:280px;max-width:420px;
  box-shadow:0 8px 32px rgba(0,80,160,0.4)}}
#ev-panel.show{{display:block}}
#ev-year{{font-size:11px;letter-spacing:1px;margin-bottom:3px}}
#ev-title{{font-size:14px;font-weight:600;color:#c0e8ff;margin-bottom:6px;letter-spacing:0.5px}}
#ev-desc{{font-size:11px;color:rgba(160,200,240,0.75);line-height:1.7;
  border-left:2px solid rgba(100,180,255,0.3);padding-left:8px}}
#ev-close{{position:absolute;top:8px;right:10px;color:rgba(100,160,220,0.5);
  cursor:pointer;font-size:14px;background:none;border:none}}
#ev-close:hover{{color:#a0d4ff}}
#ev-bar{{position:absolute;bottom:0;left:0;right:0;height:34px;z-index:100;
  display:flex;align-items:center;gap:5px;padding:0 10px;overflow-x:auto;
  background:linear-gradient(to top,rgba(3,13,24,0.9),transparent);
  scrollbar-width:thin}}
#ev-bar::-webkit-scrollbar{{height:3px}}
#ev-bar::-webkit-scrollbar-thumb{{background:rgba(80,160,255,0.2);border-radius:2px}}
.evbtn{{flex-shrink:0;display:flex;align-items:center;gap:4px;padding:2px 8px;
  border-radius:10px;border:1px solid rgba(80,160,255,0.18);
  background:rgba(80,160,255,0.06);font-size:10px;
  color:rgba(140,200,255,0.75);cursor:pointer;white-space:nowrap;
  font-family:inherit;transition:all .12s}}
.evbtn:hover{{border-color:rgba(80,200,255,0.5);color:#90d0ff}}
.evbtn.active{{border-color:rgba(80,200,255,0.6);background:rgba(80,200,255,0.12);color:#a0e0ff}}
#loading{{position:absolute;inset:0;z-index:300;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;
  background:#030d18}}
#loading.done{{display:none}}
.ld-spin{{width:38px;height:38px;border-radius:50%;
  border:2px solid rgba(80,160,255,0.12);border-top:2px solid rgba(80,160,255,0.8);
  animation:sp .8s linear infinite}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}
.ld-txt{{font-size:11px;color:rgba(80,160,255,0.55);letter-spacing:2px}}
#map-error{{position:absolute;inset:0;z-index:300;display:none;
  flex-direction:column;align-items:center;justify-content:center;gap:12px;
  background:#030d18;text-align:center;padding:0 24px}}
#map-error.show{{display:flex}}
#map-error .ei{{font-size:30px;opacity:0.25;color:#60a0d0}}
#map-error .em{{font-size:12px;color:rgba(100,180,255,0.7);line-height:1.8;max-width:340px}}
#map-error .efix{{font-size:11px;color:rgba(100,160,220,0.5);margin-top:4px;
  font-family:monospace;background:rgba(255,255,255,0.04);
  padding:6px 12px;border-radius:4px;border:1px solid rgba(100,180,255,0.12)}}
#map-error button{{padding:6px 20px;background:transparent;
  border:1px solid rgba(100,180,255,0.35);border-radius:4px;
  font-size:11px;color:rgba(100,200,255,0.8);cursor:pointer;font-family:inherit;
  margin-top:4px}}
</style>
</head>
<body>
<div id="toolbar">
  <span id="map-title">{title}</span>
  <div class="sep"></div>
  <button class="tb on-mil" onclick="toggleCat('mil',this)">军事</button>
  <button class="tb on-pol" onclick="toggleCat('pol',this)">政治</button>
  <button class="tb on-eco" onclick="toggleCat('eco',this)">财政</button>
  <button class="tb on-nat" onclick="toggleCat('nat',this)">灾异</button>
  <div class="sep"></div>
  <select id="theme-sel" onchange="setTheme(this.value)">
    <option value="ocean">深海蓝</option>
    <option value="ink">水墨黑</option>
    <option value="parchment">羊皮金</option>
    <option value="jade">翡翠绿</option>
  </select>
</div>
<canvas id="three-canvas"></canvas>
<div id="label-container"></div>
<div id="tt"></div>
<div id="ev-panel">
  <div id="ev-year"></div>
  <div id="ev-title"></div>
  <div id="ev-desc"></div>
  <button id="ev-close" onclick="closeEvPanel()">×</button>
</div>
<div id="ev-bar"></div>
<div id="loading">
  <div class="ld-spin"></div>
  <div class="ld-txt" id="ld-txt">初始化 3D 引擎…</div>
</div>
<div id="map-error">
  <div class="ei">⊘</div>
  <div class="em" id="err-msg">Three.js 本地库未找到</div>
  <div class="efix" id="err-fix">cd Harness/histrag/resources &amp;&amp; bash setup.sh</div>
  <button onclick="location.reload()">重新加载</button>
</div>

<!--
  Three.js 和 GSAP 从本地 /resources/lib/ 加载（FastAPI StaticFiles 服务）
  如未找到，页面会显示具体修复命令
  CDN fallback 仅在本地文件不存在时自动尝试
-->
<script>
// 动态加载脚本，本地优先，CDN 备用
function loadScript(localPath, cdnUrl) {{
  return new Promise((resolve, reject) => {{
    const s = document.createElement('script');
    s.src = localPath;
    s.onload = resolve;
    s.onerror = () => {{
      // 本地失败，尝试 CDN
      const s2 = document.createElement('script');
      s2.src = cdnUrl;
      s2.onload = resolve;
      s2.onerror = () => reject(new Error('无法加载: ' + localPath + '\\n也无法从 CDN 加载: ' + cdnUrl));
      document.head.appendChild(s2);
    }};
    document.head.appendChild(s);
  }});
}}

async function initLibs() {{
  try {{
    await loadScript(
      '/resources/lib/three.min.js',
      'https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js'
    );
    await loadScript(
      '/resources/lib/gsap.min.js',
      'https://cdn.jsdelivr.net/npm/gsap@3.12.2/dist/gsap.min.js'
    );
    // 库加载成功，启动主程序
    initApp();
  }} catch(e) {{
    document.getElementById('loading').classList.add('done');
    document.getElementById('err-msg').textContent = e.message.split('\\n')[0];
    document.getElementById('err-fix').textContent =
      '修复：cd Harness/histrag/resources && bash setup.sh';
    document.getElementById('map-error').classList.add('show');
    window.parent.postMessage({{type:'mapError',message:e.message}},'*');
  }}
}}

function initApp() {{

// ── Data ─────────────────────────────────────────────────────
const EVENTS = {events_js};
const PLACES = {places_js};

const CC = {{mil:'#6655dd',pol:'#1aaa77',eco:'#cc8800',nat:'#bb4422'}};
const CATL = {{mil:'军事',pol:'政治',eco:'财政',nat:'灾异'}};

// ── Themes ───────────────────────────────────────────────────
const THEMES = {{
  ocean:     {{bg:0x030d18,base:0x0a2540,top:0x0e3c68,side:0x051828,edge:0x1a70c0,
               grid:0x0a2840,pc:0x2080ff,amb:0x061828,dir:0x3a88ff,fog:0x030d18}},
  ink:       {{bg:0x080808,base:0x181818,top:0x252525,side:0x0c0c0c,edge:0x555555,
               grid:0x1c1c1c,pc:0x888888,amb:0x141414,dir:0xbbbbbb,fog:0x080808}},
  parchment: {{bg:0x120a02,base:0x2e1e06,top:0x4a3010,side:0x1c1204,edge:0xb88010,
               grid:0x281a04,pc:0xcc9010,amb:0x201004,dir:0xffcc55,fog:0x120a02}},
  jade:      {{bg:0x020e08,base:0x062018,top:0x0c3020,side:0x031008,edge:0x289050,
               grid:0x062018,pc:0x38c070,amb:0x031408,dir:0x50d080,fog:0x020e08}},
}};
let CT = 'ocean';
let shown = new Set(['mil','pol','eco','nat']);
let hlSet = new Set();

// ── Three.js init ────────────────────────────────────────────
const canvas = document.getElementById('three-canvas');
let W = window.innerWidth, H = window.innerHeight;

const renderer = new THREE.WebGLRenderer({{canvas, antialias:true}});
renderer.setSize(W, H);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.background = new THREE.Color(THEMES[CT].bg);
scene.fog = new THREE.FogExp2(THEMES[CT].fog, 0.013);

const camera = new THREE.PerspectiveCamera(42, W/H, 0.1, 500);
let sph = {{th:0.25, ph:0.35, r:30}};
function sc2cam() {{
  camera.position.set(
    sph.r*Math.sin(sph.ph)*Math.sin(sph.th),
    sph.r*Math.cos(sph.ph),
    sph.r*Math.sin(sph.ph)*Math.cos(sph.th)
  );
  camera.lookAt(0, 0, 0);
}}
sc2cam();

const ambL = new THREE.AmbientLight(THEMES[CT].amb, 3);
scene.add(ambL);
const dirL = new THREE.DirectionalLight(THEMES[CT].dir, 3.5);
dirL.position.set(-12, 22, 10);
dirL.castShadow = true;
dirL.shadow.mapSize.set(1024, 1024);
const dc = dirL.shadow.camera;
dc.left = dc.bottom = -28; dc.right = dc.top = 28;
scene.add(dirL);
const fillL = new THREE.DirectionalLight(0x102030, 1.0);
fillL.position.set(10, 4, -8);
scene.add(fillL);

// ── Orbit controls ───────────────────────────────────────────
let drag = false, pm = {{x:0,y:0}};
canvas.addEventListener('mousedown', e => {{ drag=true; pm={{x:e.clientX,y:e.clientY}}; }});
window.addEventListener('mouseup', () => drag=false);
canvas.addEventListener('mousemove', e => {{
  if(!drag) return;
  sph.th -= (e.clientX-pm.x)*0.007;
  sph.ph  = Math.max(0.28, Math.min(1.38, sph.ph+(e.clientY-pm.y)*0.006));
  pm = {{x:e.clientX, y:e.clientY}};
  sc2cam();
}});
canvas.addEventListener('wheel', e => {{
  sph.r = Math.max(10, Math.min(55, sph.r+e.deltaY*0.04));
  sc2cam(); e.preventDefault();
}}, {{passive:false}});
let lt = null;
canvas.addEventListener('touchstart', e => {{ lt={{x:e.touches[0].clientX,y:e.touches[0].clientY}}; }});
canvas.addEventListener('touchmove', e => {{
  if(!lt) return;
  sph.th -= (e.touches[0].clientX-lt.x)*0.009;
  sph.ph  = Math.max(0.28, Math.min(1.38, sph.ph+(e.touches[0].clientY-lt.y)*0.007));
  lt = {{x:e.touches[0].clientX, y:e.touches[0].clientY}};
  sc2cam(); e.preventDefault();
}}, {{passive:false}});

// ── Coordinate mapping ───────────────────────────────────────
const MS=0.22, LO=-104, LA=-35;
function ll2xz(lo, la) {{ return [(lo+LO)*MS, (la+LA)*MS]; }}
function ll2xz_line(lo, la) {{ return [(lo+LO)*MS, -(la+LA)*MS]; }}

// ── Ground layer ─────────────────────────────────────────────
function buildGround() {{
  const t = THEMES[CT];
  const gh = new THREE.GridHelper(55, 38, t.grid, t.grid);
  gh.position.y = -0.5; gh.material.opacity=0.22; gh.material.transparent=true;
  scene.add(gh);
  const dm = new THREE.MeshBasicMaterial({{color:t.edge,transparent:true,opacity:0.05,side:THREE.DoubleSide}});
  const d  = new THREE.Mesh(new THREE.CircleGeometry(18,64), dm);
  d.rotation.x = -Math.PI/2; d.position.y = -0.46; scene.add(d);
  const pa = new Float32Array(800*3);
  for(let i=0;i<800;i++) {{
    pa[i*3]=(Math.random()-.5)*70; pa[i*3+1]=Math.random()*2.5-.5; pa[i*3+2]=(Math.random()-.5)*70;
  }}
  const pg = new THREE.BufferGeometry();
  pg.setAttribute('position', new THREE.BufferAttribute(pa,3));
  scene.add(new THREE.Points(pg, new THREE.PointsMaterial({{color:t.pc,size:0.055,transparent:true,opacity:0.45,sizeAttenuation:true}})));
  for(let ri=0;ri<2;ri++) {{
    const r = new THREE.Mesh(
      new THREE.RingGeometry(17+ri*1.8, 17.22+ri*1.8, 72),
      new THREE.MeshBasicMaterial({{color:t.edge,transparent:true,opacity:0.28+ri*0.12,side:THREE.DoubleSide}})
    );
    r.rotation.x = -Math.PI/2; r.position.y = -0.44;
    r.userData.rd = ri?-1:1; r.userData.ring = true;
    scene.add(r);
  }}
}}

// ── Province extrude ─────────────────────────────────────────
function buildProv(rings, depth, ct, cs) {{
  if(!rings||!rings[0]||rings[0].length<3) return null;
  
  // ↓ 新增：过滤掉跨度异常的多边形（南海九段线等）
  const lons = rings[0].map(p=>p[0]);
  const lats = rings[0].map(p=>p[1]);
  const lonSpan = Math.max(...lons) - Math.min(...lons);
  const latSpan = Math.max(...lats) - Math.min(...lats);
  if(lonSpan > 30 || latSpan > 20) return null;  // 跨度超过30°/20°的跳过

  const shape = new THREE.Shape();
  const [x0,z0] = ll2xz(rings[0][0][0], rings[0][0][1]);
  shape.moveTo(x0,z0);
  for(let i=1;i<rings[0].length;i++) {{
    const [x,z] = ll2xz(rings[0][i][0], rings[0][i][1]);
    shape.lineTo(x,z);
  }}
  shape.closePath();
  for(let h=1;h<rings.length;h++) {{
    const hole = new THREE.Path();
    const [hx,hz] = ll2xz(rings[h][0][0], rings[h][0][1]);
    hole.moveTo(hx,hz);
    for(let i=1;i<rings[h].length;i++) {{
      const [x,z] = ll2xz(rings[h][i][0], rings[h][i][1]);
      hole.lineTo(x,z);
    }}
    hole.closePath(); shape.holes.push(hole);
  }}
  const geo = new THREE.ExtrudeGeometry(shape,
    {{depth, bevelEnabled:true, bevelThickness:0.03, bevelSize:0.015, bevelSegments:1}});
  geo.rotateX(-Math.PI/2);
  const m = new THREE.Mesh(geo, [
    new THREE.MeshLambertMaterial({{color:ct}}),
    new THREE.MeshLambertMaterial({{color:cs}}),
  ]);
  m.castShadow = true; m.receiveShadow = true;
  return m;
}}

function buildEdge(rings, y, col, opa=0.65) {{
  const pts = [];
  for(const ring of rings) {{
    for(let i=0;i<ring.length;i++) {{ const [x,z]=ll2xz_line(ring[i][0],ring[i][1]); pts.push(new THREE.Vector3(x,y,z)); }}
    const [x0,z0]=ll2xz_line(ring[0][0],ring[0][1]); pts.push(new THREE.Vector3(x0,y,z0));
    pts.push(new THREE.Vector3(NaN,NaN,NaN));
  }}
  while(pts.length && isNaN(pts[pts.length-1].x)) pts.pop();
  if(!pts.length) return null;
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({{color:col, transparent:true, opacity:opa}})
  );
}}

const mapGrp = new THREE.Group(); scene.add(mapGrp);
let provMeshes = [];

function elevColor(lat, t) {{
  const base = new THREE.Color(t.base), top = new THREE.Color(t.top);
  return base.clone().lerp(top, Math.max(0,Math.min(1,(lat-18)/35))*0.65+0.35);
}}

function makeFallbackProvinces() {{
  const P = [
    ['黑龙江',125,48,135,54],['吉林',122,42,131,47],['辽宁',119,39,125,43],
    ['内蒙古',97,40,126,52],['河北',113,36,120,42],['山西',110,34,114,40],
    ['陕西',107,31,111,39],['甘肃',92,32,108,43],['宁夏',104,35,107,39],
    ['青海',89,31,103,40],['西藏',78,27,99,37],['新疆',73,35,91,49],
    ['山东',114,34,122,38],['河南',110,31,116,36],['湖北',108,29,116,33],
    ['湖南',108,24,114,30],['江西',113,24,118,30],['安徽',115,29,119,34],
    ['江苏',116,30,121,35],['浙江',118,27,122,31],['福建',115,23,120,28],
    ['广东',109,20,117,25],['广西',104,20,112,26],['云南',97,21,106,29],
    ['贵州',103,24,109,29],['四川',97,26,108,34],['重庆',105,28,110,32],
    ['海南',109,18,111,20],['台湾',120,21,122,25],['北京',115,39,117,41],
    ['天津',116,38,118,40],['上海',120,30,122,32],
  ];
  return {{features: P.map(([name,x0,y0,x1,y1])=>{{
    const c=[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]];
    return {{type:'Feature',properties:{{name}},geometry:{{type:'Polygon',coordinates:[c]}}}};
  }})}};
}}

async function loadMap() {{
  const t = THEMES[CT];
  setLd('加载省份数据…');
  let data = null;
  try {{
    const r = await fetch('https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json');
    if(!r.ok) throw new Error(r.status);
    data = await r.json();
  }} catch(e) {{
    setLd('使用内置省份轮廓…');
    data = makeFallbackProvinces();
  }}
  if(!data||!data.features||!data.features.length) data = makeFallbackProvinces();

  setLd('构建 3D 地形…');
  const features = data.features;
  let built = 0;
  for(const feat of features) {{
    const geom = feat.geometry; if(!geom) continue;
    const name = (feat.properties&&(feat.properties.name||feat.properties.NAME))||'';
    let sumLa=0, cnt=0;
    const polys = geom.type==='MultiPolygon' ? geom.coordinates : [geom.coordinates];
    polys.forEach(p=>{{ for(const ring of p) for(const pt of ring) {{sumLa+=pt[1];cnt++;}} }});
    const avgLat = cnt>0 ? sumLa/cnt : 35;
    const tc = elevColor(avgLat, t);
    const sc = tc.clone().multiplyScalar(0.62);
    const depth = 0.32+Math.random()*0.12;
    polys.forEach(rings => {{
      const mesh = buildProv(rings, depth, tc.getHex(), sc.getHex());
      if(!mesh) return;
      mesh.userData = {{name, depth, baseTop:tc.clone(), baseSide:sc.clone()}};
      mapGrp.add(mesh); provMeshes.push(mesh);
      const el = buildEdge(rings, depth+0.05, t.edge, 0.7);
      if(el) mapGrp.add(el);
    }});
    built++;
    if(built%5===0) {{ setLd(`构建省份 ${{built}}/${{features.length}}…`); await tick(); }}
  }}
  buildLabels();
  buildEvBar();
  document.getElementById('loading').classList.add('done');
}}

function tick() {{ return new Promise(r=>setTimeout(r,0)); }}
function setLd(t) {{ document.getElementById('ld-txt').textContent=t; }}

// ── Labels ───────────────────────────────────────────────────
let lblEls = [];
function buildLabels() {{
  const con = document.getElementById('label-container');
  con.innerHTML = ''; lblEls = [];
  PLACES.forEach((p,i) => {{
    const el = document.createElement('div');
    el.className = `place-label ${{p.t}}`; el.dataset.i = i;
    const dot = document.createElement('div'); dot.className='dot';
    const cc = p.t==='cap'?'#ff7050':p.t==='battle'?'#ff4040':'#50a8ff';
    dot.style.background=cc; dot.style.color=cc;
    const nm = document.createElement('div'); nm.className='lname'; nm.textContent=p.n;
    el.appendChild(dot); el.appendChild(nm);
    el.addEventListener('mouseenter', ev=>showTT(ev,p));
    el.addEventListener('mouseleave', ()=>{{document.getElementById('tt').style.display='none';}});
    el.addEventListener('click', ()=>onPC(p.n));
    con.appendChild(el); lblEls.push({{el,p}});
  }});
}}

function proj3d(x,y,z) {{
  const v = new THREE.Vector3(x,y,z).project(camera);
  return {{sx:(v.x*.5+.5)*W, sy:(-v.y*.5+.5)*H, vis:v.z<1}};
}}
function updateLabels() {{
  lblEls.forEach(({{'el':el,p}}) => {{
    const [x,z]=ll2xz(p.lo,p.la), s=proj3d(x,0.5,z);
    if(s.vis) {{ el.style.display='block'; el.style.left=s.sx+'px'; el.style.top=(s.sy-2)+'px'; }}
    else el.style.display='none';
  }});
}}

// ── Fly lines ─────────────────────────────────────────────────
const flyGrp = new THREE.Group(); scene.add(flyGrp);
function buildFly(p1,p2) {{
  const [x1,z1]=ll2xz(p1.lo,p1.la), [x2,z2]=ll2xz(p2.lo,p2.la);
  const mid = new THREE.Vector3((x1+x2)/2, 2.8+Math.random()*1.8, (z1+z2)/2);
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(x1,.5,z1), mid, new THREE.Vector3(x2,.5,z2)
  );
  const line = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)),
    new THREE.LineBasicMaterial({{color:0x60b8ff,transparent:true,opacity:.65}})
  );
  const dot = new THREE.Mesh(
    new THREE.SphereGeometry(.1,6,6),
    new THREE.MeshBasicMaterial({{color:0xa0d8ff,transparent:true,opacity:.9}})
  );
  line.userData = {{curve, dot, t:Math.random()}};
  scene.add(dot); return line;
}}

// ── Highlight ─────────────────────────────────────────────────
function setHL(names) {{
  hlSet = new Set(names);
  lblEls.forEach(({{'el':el,p}}) => el.classList.toggle('hl', hlSet.has(p.n)));
  flyGrp.children.forEach(l=>{{ if(l.userData.dot) scene.remove(l.userData.dot); }});
  flyGrp.clear();
  const hp = PLACES.filter(p=>hlSet.has(p.n));
  for(let i=0;i<hp.length-1;i++) flyGrp.add(buildFly(hp[i],hp[i+1]));
  if(names.length) {{
    const p = PLACES.find(x=>x.n===names[0]);
    if(p) {{
      const [x]=ll2xz(p.lo,p.la);
      gsap.to(sph,{{th:Math.atan2(x,sph.r*Math.sin(sph.ph))+.15,
        duration:1.1,ease:'power2.inOut',onUpdate:sc2cam}});
    }}
  }}
}}

// ── Tooltip ───────────────────────────────────────────────────
function showTT(ev,p) {{
  const tt=document.getElementById('tt'); tt.style.display='block';
  tt.innerHTML=`<strong>${{p.n}}</strong>${{p.i?`<span>${{p.i}}</span>`:''}}`;
  let tx=ev.clientX+12, ty=ev.clientY-40;
  if(tx+205>W) tx-=220; if(ty<0) ty=4;
  tt.style.left=tx+'px'; tt.style.top=ty+'px';
}}

// ── Event panel ───────────────────────────────────────────────
function showEvPanel(idx) {{
  const e = EVENTS[idx];
  const yr = e.y<0?'前'+Math.abs(e.y):e.y;
  const eyEl = document.getElementById('ev-year');
  eyEl.textContent = `${{yr}}年 · ${{CATL[e.cat]||e.cat}}`;
  eyEl.style.color  = CC[e.cat]||'#5DCAA5';
  document.getElementById('ev-title').textContent = e.title;
  document.getElementById('ev-desc').textContent  = e.desc||'';
  document.getElementById('ev-panel').classList.add('show');
  document.querySelectorAll('.evbtn').forEach((b,i)=>b.classList.toggle('active',i===idx));
  setHL(e.places||[]);
}}
function closeEvPanel() {{
  document.getElementById('ev-panel').classList.remove('show');
  hlSet.clear(); lblEls.forEach(({{'el':el}})=>el.classList.remove('hl'));
  flyGrp.children.forEach(l=>{{if(l.userData.dot)scene.remove(l.userData.dot);}});
  flyGrp.clear();
  document.querySelectorAll('.evbtn').forEach(b=>b.classList.remove('active'));
}}
function onPC(name) {{
  const idx = EVENTS.findIndex(e=>shown.has(e.cat)&&(e.places||[]).includes(name));
  if(idx>=0) showEvPanel(idx);
}}

// ── Event bar ─────────────────────────────────────────────────
function buildEvBar() {{
  const bar = document.getElementById('ev-bar'); bar.innerHTML='';
  EVENTS.forEach((e,i)=>{{
    const b = document.createElement('button'); b.className='evbtn';
    const dot=document.createElement('span');
    dot.style.cssText=`width:6px;height:6px;border-radius:50%;background:${{CC[e.cat]}};flex-shrink:0;display:inline-block;margin-right:4px`;
    b.appendChild(dot);
    b.appendChild(document.createTextNode(`${{e.y<0?'前'+Math.abs(e.y):e.y}} ${{e.title}}`));
    b.onclick=()=>showEvPanel(i); bar.appendChild(b);
  }});
}}

// ── Category filter ───────────────────────────────────────────
function toggleCat(cat,btn) {{
  shown.has(cat)?(shown.delete(cat),btn.className='tb'):(shown.add(cat),btn.className=`tb on-${{cat}}`);
}}

// ── Theme switch ──────────────────────────────────────────────
function setTheme(name) {{
  CT=name; const t=THEMES[name];
  scene.background.set(t.bg); scene.fog.color.set(t.fog);
  ambL.color.set(t.amb); dirL.color.set(t.dir);
  provMeshes.forEach(m=>{{
    const nt=new THREE.Color(t.top), nb=new THREE.Color(t.base);
    const lum=c=>(c.r*.3+c.g*.59+c.b*.11);
    const lumT=Math.max(0.1,lum(new THREE.Color(THEMES.ocean.top)));
    const lumB=Math.max(0.1,lum(new THREE.Color(THEMES.ocean.base)));
    const rT=Math.max(0.05,lum(m.userData.baseTop))/lumT;
    const rB=Math.max(0.05,lum(m.userData.baseSide))/lumB;
    m.userData.baseTop  = nt.clone().multiplyScalar(rT*1.1);
    m.userData.baseSide = nb.clone().multiplyScalar(rB);
    m.material[0].color.set(m.userData.baseTop);
    m.material[1].color.set(m.userData.baseSide);
  }});
}}

// ── Hover ─────────────────────────────────────────────────────
const rc=new THREE.Raycaster(), mu=new THREE.Vector2();
let hov=null, fr=0;
canvas.addEventListener('mousemove', e=>{{
  mu.x=(e.clientX/W)*2-1; mu.y=-(e.clientY/H)*2+1;
}});
function checkHov() {{
  rc.setFromCamera(mu,camera);
  const hits=rc.intersectObjects(provMeshes);
  if(hits.length) {{
    const m=hits[0].object;
    if(m!==hov) {{ if(hov)unhov(hov); hov=m; doHov(m); }}
  }} else {{ if(hov) {{ unhov(hov); hov=null; }} }}
}}
function doHov(m) {{
  gsap.to(m.position,{{y:.18,duration:.22,ease:'power2.out'}});
  m.material[0].color.set(m.userData.baseTop.clone().multiplyScalar(1.55));
  m.material[1].color.set(m.userData.baseSide.clone().multiplyScalar(1.3));
  canvas.style.cursor='pointer';
}}
function unhov(m) {{
  gsap.to(m.position,{{y:0,duration:.22,ease:'power2.out'}});
  m.material[0].color.set(m.userData.baseTop);
  m.material[1].color.set(m.userData.baseSide);
  canvas.style.cursor='grab';
}}

// ── Messages from parent ──────────────────────────────────────
window.addEventListener('message', ev=>{{
  if(!ev.data) return;
  const d=ev.data;
  if(d.type==='selectEvent'&&typeof d.index==='number') showEvPanel(d.index);
  if(d.type==='setMapStyle') {{
    const m={{parchment:'parchment',dark:'ink',celadon:'jade',plain:'jade',
              vermilion:'parchment',ocean:'ocean',ink:'ink',jade:'jade'}};
    const nm=m[d.style]||'ocean';
    setTheme(nm); document.getElementById('theme-sel').value=nm;
  }}
  if(d.type==='flyToPlace') {{
    const p=PLACES.find(x=>x.n===d.name);
    if(p) {{
      const [x]=ll2xz(p.lo,p.la);
      gsap.to(sph,{{th:Math.atan2(x,sph.r*Math.sin(sph.ph))+.15,
        duration:1.1,ease:'power2.inOut',onUpdate:sc2cam}});
    }}
  }}
}});

// ── Render loop ───────────────────────────────────────────────
function animate() {{
  requestAnimationFrame(animate); fr++;
  scene.children.forEach(c=>{{ if(c.userData.ring) c.rotation.z+=.0025*c.userData.rd; }});
  flyGrp.children.forEach(l=>{{
    if(!l.userData.curve||!l.userData.dot) return;
    l.userData.t=(l.userData.t+.005)%1;
    l.userData.dot.position.copy(l.userData.curve.getPoint(l.userData.t));
  }});
  if(fr%3===0) checkHov();
  updateLabels();
  renderer.render(scene,camera);
}}

window.addEventListener('resize',()=>{{
  W=window.innerWidth; H=window.innerHeight;
  camera.aspect=W/H; camera.updateProjectionMatrix();
  renderer.setSize(W,H);
}});

buildGround(); loadMap(); animate();

}} // end initApp

initLibs();
// 此脚本由 initApp() 调用，Three.js 和 GSAP 已确保加载完毕
</script>
</body>
</html>"""
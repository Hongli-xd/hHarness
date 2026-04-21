"""Timeline Tool - generates interactive historical timeline visualization."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..agent import BaseTool, ToolExecutionContext, ToolResult


class TimelineEvent(BaseModel):
    """A single historical event on the timeline."""
    year: int = Field(description="Year of the event (negative for BCE)")
    title: str = Field(description="Event title")
    description: str | None = Field(default=None, description="Event description")
    category: str = Field(description="Category: mil (military), pol (political), eco (economic), nat (disaster)")
    confidence: str = Field(default="high", description="Confidence: high, mid, low")


class TimelineInput(BaseModel):
    """Input schema for the Timeline Tool."""
    events: list[TimelineEvent] = Field(description="List of historical events to display")
    title: str = Field(default="历史时间轴", description="Timeline title")
    year_start: int | None = Field(default=None, description="Start year (auto-computed if not provided)")
    year_end: int | None = Field(default=None, description="End year (auto-computed if not provided)")
    highlight_years: list[int] = Field(default_factory=list, description="Years to highlight")


class TimelineTool(BaseTool):
    """历史时间轴可视化工具。

从历史事件列表生成可交互的HTML时间轴，
按类别（军事、政治、经济、灾异）组织，
并标注朝代分期。

【功能】
- 生成可缩放、可点击的HTML时间轴
- 按类别筛选显示（军事/政治/财政/灾异）
- 点击事件查看详情
- 朝代分期标注
- 置信度指示器
"""

    name = "timeline"
    description = """生成可交互的历史时间轴可视化图表。

【输入】
历史事件列表，包含年份、标题、描述、类别

【输出】
完整的HTML文件，展示可缩放、可点击的时间轴

【使用场景】
- 用户要求"梳理时间轴"
- "按时间顺序整理"
- 生成历史事件的年表可视化
- 需要展示历史事件的发展脉络

【时间轴功能】
- 类别筛选：军事(mil)、政治(pol)、财政(eco)、灾异(nat)
- 点击事件节点查看详情
- 朝代分界线标注
- 置信度指示（高/中/低）
"""
    input_model = TimelineInput

    def get_schema_overrides(self) -> dict[str, Any]:
        """返回中文Schema描述"""
        return {
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "events": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "year": {"type": "integer", "description": "事件年份（负数表示公元前）"},
                                "title": {"type": "string", "description": "事件标题"},
                                "description": {"type": "string", "description": "事件详细描述"},
                                "category": {
                                    "type": "string",
                                    "enum": ["mil", "pol", "eco", "nat"],
                                    "description": "事件类别：\n- mil：军事（如战争、战役）\n- pol：政治（如改革、政变）\n- eco：财政/经济（如税制、贸易）\n- nat：灾异（如蝗灾、地震）"
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": ["high", "mid", "low"],
                                    "description": "置信度：high（高）、mid（中）、low（低）"
                                }
                            },
                            "required": ["year", "title", "category"]
                        },
                        "description": "历史事件列表，每个事件包含：\n- year：年份（负数=公元前）\n- title：事件标题\n- description：详细描述（可选）\n- category：类别（必填）\n- confidence：置信度（默认high）"
                    },
                    "title": {
                        "type": "string",
                        "default": "历史时间轴",
                        "description": "时间轴标题"
                    },
                    "year_start": {
                        "type": "integer",
                        "description": "起始年份（不填则自动从事件中计算）"
                    },
                    "year_end": {
                        "type": "integer",
                        "description": "结束年份（不填则自动从事件中计算）"
                    },
                    "highlight_years": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "需要高亮标注的年份列表"
                    }
                },
                "required": ["events"]
            }
        }

    def is_read_only(self, arguments: TimelineInput) -> bool:
        return True

    async def execute(
        self, arguments: TimelineInput, context: ToolExecutionContext
    ) -> ToolResult:
        """Generate the timeline HTML."""
        events = arguments.events
        if not events:
            return ToolResult(output="No events provided for timeline.", is_error=True)

        year_start = arguments.year_start or min(e.year for e in events)
        year_end = arguments.year_end or max(e.year for e in events)

        events_json = self._build_events_json(events)
        dynasties = self._detect_dynasties(year_start, year_end)

        import json
        dyn_json = json.dumps(dynasties, ensure_ascii=False)

        pad = max(20, (year_end - year_start) // 20)
        y_start = year_start - pad
        y_end = year_end + pad

        html = self._generate_html(
            title=arguments.title,
            events_json=events_json,
            dyn_json=dyn_json,
            y_start=y_start,
            y_end=y_end,
        )

        return ToolResult(
            output=(
                f"[Timeline generated with {len(events)} events, years {year_start}-{year_end}]\n\n"
                f"Timeline HTML ({len(html)} bytes) ready at: timeline.html\n\n"
                f"Events:\n"
                + "\n".join(f"  {e.year}: {e.title} [{e.category}]" for e in events[:10])
                + (f"\n  ... and {len(events) - 10} more" if len(events) > 10 else "")
            ),
            metadata={"html": html, "event_count": len(events), "year_range": [year_start, year_end]},
        )

    def _build_events_json(self, events: list[TimelineEvent]) -> str:
        import json
        items = []
        for e in events:
            items.append({
                "y": e.year,
                "cat": e.category,
                "conf": e.confidence,
                "title": e.title,
                "desc": e.description or "",
            })
        return json.dumps(items, ensure_ascii=False)

    def _generate_html(
        self,
        title: str,
        events_json: str,
        dyn_json: str,
        y_start: int,
        y_end: int,
    ) -> str:
        css = self._build_css()
        js = self._build_js(events_json, dyn_json, y_start, y_end)
        body = self._build_body(title)

        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"zh\">\n"
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n"
            f"<style>\n{css}</style>\n"
            "</head>\n"
            f"<body>\n{body}\n"
            f"<script>\n{js}</script>\n"
            "</body>\n"
            "</html>"
        )

    def _build_css(self) -> str:
        return """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f3ee; color: #333; }
#toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 8px 12px; background: #fff; border-bottom: 1px solid #e0d8c8; position: sticky; top: 0; z-index: 20; }
#toolbar h1 { font-size: 14px; font-weight: 600; color: #333; margin-right: 4px; }
.sep { width: 1px; height: 18px; background: #ddd; }
.tb { font-size: 11px; padding: 3px 12px; border-radius: 20px; border: 1px solid #ccc; background: transparent; color: #666; cursor: pointer; transition: all .15s; }
.tb:hover { border-color: #999; color: #333; }
.tb.on-mil { background: #EEEDFE; color: #3C3489; border-color: #AFA9EC; font-weight: 500; }
.tb.on-pol { background: #E1F5EE; color: #085041; border-color: #5DCAA5; font-weight: 500; }
.tb.on-eco { background: #FAEEDA; color: #633806; border-color: #EF9F27; font-weight: 500; }
.tb.on-nat { background: #FAECE7; color: #712B13; border-color: #F0997B; font-weight: 500; }
#range-label { font-size: 11px; color: #999; margin-left: auto; }
#tl-outer { padding: 16px 12px 0; overflow-x: auto; -webkit-overflow-scrolling: touch; }
#tl-track { position: relative; height: 134px; min-width: 800px; }
#tl-axis { position: absolute; left: 0; right: 0; top: 72px; height: 1px; background: #bbb; }
.tick { position: absolute; top: 72px; display: flex; flex-direction: column; align-items: center; transform: translateX(-50%); }
.tick-line-major { width: 1px; height: 8px; background: #aaa; }
.tick-line-minor { width: 1px; height: 4px; background: #ddd; }
.tick-label { font-size: 10px; color: #aaa; margin-top: 3px; white-space: nowrap; }
.ev { position: absolute; top: 72px; transform: translate(-50%, -50%); cursor: pointer; z-index: 5; }
.ev-dot { width: 11px; height: 11px; border-radius: 50%; border: 1.5px solid #fff; transition: transform .15s, box-shadow .15s; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.ev:hover .ev-dot { transform: scale(1.45); box-shadow: 0 2px 6px rgba(0,0,0,0.25); }
.ev.sel .ev-dot { transform: scale(1.6); box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
.ev-stem { position: absolute; left: 50%; width: 1px; background: #ccc; transform: translateX(-50%); }
.ev-stem.up { bottom: 5px; }
.ev-stem.dn { top: 5px; }
.ev-lbl { position: absolute; left: 50%; white-space: nowrap; font-size: 10px; color: #666; transform: translateX(-50%); pointer-events: none; line-height: 1.3; text-shadow: 0 0 3px #f5f3ee, 0 0 3px #f5f3ee; }
.ev-lbl.up { bottom: calc(100% + 5px); }
.ev-lbl.dn { top: calc(100% + 5px); }
.ev.sel .ev-lbl { color: #222; font-weight: 600; }
#detail { margin: 12px; padding: 12px 16px; background: #fff; border: 1px solid #e0d8c8; border-radius: 10px; min-height: 72px; }
.d-hint { font-size: 12px; color: #bbb; line-height: 2.5; }
.d-year { font-size: 11px; color: #aaa; margin-bottom: 3px; }
.d-title { font-size: 15px; font-weight: 600; color: #222; margin-bottom: 5px; }
.d-desc { font-size: 13px; color: #555; line-height: 1.7; margin-bottom: 8px; }
.d-tags { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
#ev-count { font-size: 11px; color: #bbb; padding: 4px 12px 8px; }
"""

    def _build_body(self, title: str) -> str:
        return (
            '<div id="toolbar">\n'
            f"  <h1>{title}</h1>\n"
            '  <div class="sep"></div>\n'
            '  <button class="tb on-mil" data-cat="mil" onclick="toggleCat(\'mil\',this)">军事</button>\n'
            '  <button class="tb on-pol" data-cat="pol" onclick="toggleCat(\'pol\',this)">政治</button>\n'
            '  <button class="tb on-eco" data-cat="eco" onclick="toggleCat(\'eco\',this)">财政</button>\n'
            '  <button class="tb on-nat" data-cat="nat" onclick="toggleCat(\'nat\',this)">灾异</button>\n'
            '  <div class="sep"></div>\n'
            '  <button class="tb" onclick="resetZoom()">复位</button>\n'
            '  <span id="range-label"></span>\n'
            '</div>\n'
            '<div id="tl-outer"><div id="tl-track"></div></div>\n'
            '<div id="ev-count"></div>\n'
            '<div id="detail" class="empty"><div class="d-hint">← 点击事件节点查看详情</div></div>'
        )

    def _build_js(self, events_json: str, dyn_json: str, y_start: int, y_end: int) -> str:
        return (
            f"const EVENTS = {events_json};\n"
            f"const DYNASTIES = {dyn_json};\n"
            f"const Y_START = {y_start};\n"
            f"const Y_END = {y_end};\n"
            "let shown = new Set(['mil','pol','eco','nat']);\n"
            "let selIdx = -1;\n"
            "\n"
            "const CAT = {\n"
            "  mil: { color:'#534AB7', bg:'#EEEDFE', label:'军事' },\n"
            "  pol: { color:'#0F6E56', bg:'#E1F5EE', label:'政治' },\n"
            "  eco: { color:'#854F0B', bg:'#FAEEDA', label:'财政' },\n"
            "  nat: { color:'#993C1D', bg:'#FAECE7', label:'灾异' },\n"
            "};\n"
            "const CONF = {\n"
            "  high: { bg:'#E1F5EE', color:'#085041', label:'高置信度' },\n"
            "  mid:  { bg:'#FAEEDA', color:'#633806', label:'中置信度' },\n"
            "  low:  { bg:'#FCEBEB', color:'#791F1F', label:'低置信度' },\n"
            "};\n"
            "\n"
            "function pct(y) {\n"
            "  return ((y - Y_START) / (Y_END - Y_START) * 100).toFixed(4) + '%';\n"
            "}\n"
            "\n"
            "function render() {\n"
            "  const track = document.getElementById('tl-track');\n"
            "  let h = '<div id=\"tl-axis\"></div>';\n"
            "  for (let y = Y_START; y <= Y_END; y += 10) {\n"
            "    const isMajor = y % 50 === 0;\n"
            "    h += '<div class=\"tick\" style=\"left:' + pct(y) + '\">' +\n"
            "      '<div class=\"' + (isMajor ? 'tick-line-major' : 'tick-line-minor') + '\"></div>' +\n"
            "      (isMajor ? '<div class=\"tick-label\">' + y + '</div>' : '') +\n"
            "      '</div>';\n"
            "  }\n"
            "  DYNASTIES.forEach(d => {\n"
            "    h += '<div style=\"position:absolute;left:' + pct(d.y) + ';top:0;bottom:0;width:1px;background:rgba(0,0,0,0.12);z-index:1\">' +\n"
            "      '<span style=\"position:absolute;top:0;left:3px;font-size:9px;color:#aaa\">' + d.label + '</span></div>';\n"
            "  });\n"
            "  const vis = EVENTS.filter(e => shown.has(e.cat));\n"
            "  vis.forEach((e, i) => {\n"
            "    const up = i % 2 === 0;\n"
            "    const idx = EVENTS.indexOf(e);\n"
            "    const isSel = idx === selIdx;\n"
            "    const c = CAT[e.cat];\n"
            "    const stemH = 28;\n"
            "    h += '<div class=\"ev' + (isSel ? ' sel' : '') + '\" style=\"left:' + pct(e.y) + '\" onclick=\"pick(' + idx + ')\">' +\n"
            "      '<div class=\"ev-dot\" style=\"background:' + c.color + ';opacity:' + (isSel ? 1 : 0.82) + '\"></div>' +\n"
            "      '<div class=\"ev-stem ' + (up ? 'up' : 'dn') + '\" style=\"height:' + stemH + 'px\"></div>' +\n"
            "      '<div class=\"ev-lbl ' + (up ? 'up' : 'dn') + '\">' + e.title + '</div></div>';\n"
            "  });\n"
            "  track.innerHTML = h;\n"
            "  document.getElementById('ev-count').textContent = '显示 ' + vis.length + ' 个事件（' + EVENTS.length + '）';\n"
            "  document.getElementById('range-label').textContent = Y_START + '—' + Y_END;\n"
            "}\n"
            "\n"
            "function pick(idx) {\n"
            "  selIdx = idx;\n"
            "  render();\n"
            "  const e = EVENTS[idx];\n"
            "  const c = CAT[e.cat];\n"
            "  const conf = CONF[e.conf] || CONF.high;\n"
            "  const detail = document.getElementById('detail');\n"
            "  detail.classList.remove('empty');\n"
            "  detail.innerHTML = '<div class=\"d-year\">' + e.y + ' 年</div>' +\n"
            "    '<div class=\"d-title\">' + e.title + '</div>' +\n"
            "    '<div class=\"d-desc\">' + e.desc + '</div>' +\n"
            "    '<div class=\"d-tags\">' +\n"
            "    '<span class=\"tag\" style=\"background:' + c.bg + ';color:' + c.color + '\">' + c.label + '</span>' +\n"
            "    '<span class=\"tag\" style=\"background:' + conf.bg + ';color:' + conf.color + '\">' + conf.label + '</span></div>';\n"
            "}\n"
            "\n"
            "function toggleCat(cat, btn) {\n"
            "  if (shown.has(cat)) { shown.delete(cat); btn.className = 'tb'; }\n"
            "  else { shown.add(cat); btn.className = 'tb on-' + cat; }\n"
            "  selIdx = -1;\n"
            "  render();\n"
            "  const detail = document.getElementById('detail');\n"
            "  detail.classList.add('empty');\n"
            "  detail.innerHTML = '<div class=\"d-hint\">← 点击事件节点查看详情</div>';\n"
            "}\n"
            "\n"
            "function resetZoom() { selIdx = -1; render(); }\n"
            "render();\n"
        )

    def _detect_dynasties(self, year_start: int, year_end: int) -> list[dict]:
        """Detect dynasty markers based on year range."""
        dynasties = []
        if year_start <= 1368 <= year_end:
            dynasties.append({"y": 1368, "label": "明"})
        if year_start <= 1644 <= year_end:
            dynasties.append({"y": 1644, "label": "清"})
        if year_start <= 1912 <= year_end:
            dynasties.append({"y": 1912, "label": "民国"})
        return dynasties

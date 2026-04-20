#!/bin/bash
# 一键下载所有依赖，完成本地部署

set -e
echo ">>> 创建目录结构..."
mkdir -p assets/lib assets/data

echo ">>> 下载 JS 库..."
curl -sSL -o assets/lib/d3.min.js \
  https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js

curl -sSL -o assets/lib/topojson.min.js \
  https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js

echo ">>> 下载地理数据..."
curl -sSL -o assets/data/countries-110m.json \
  https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json

curl -sSL -o assets/data/rivers.geojson \
  https://cdn.jsdelivr.net/npm/natural-earth-geojson@1.1.1/ne_50m_rivers_lake_centerlines.geojson

curl -sSL -o assets/data/lakes.geojson \
  https://cdn.jsdelivr.net/npm/natural-earth-geojson@1.1.1/ne_50m_lakes.geojson

echo ""
echo "✓ 完成！启动本地服务器："
echo "  python -m http.server 8080"
echo ""
echo "  地图:     http://localhost:8080/map.html"
echo "  时间轴:   http://localhost:8080/timeline.html"

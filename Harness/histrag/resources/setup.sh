#!/bin/bash
# 下载地图和时间轴工具所需的地理资源数据

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSET_DIR="$SCRIPT_DIR"

echo ">>> 创建目录结构..."
mkdir -p "$ASSET_DIR/lib" "$ASSET_DIR/data"

echo ">>> 下载 JS 库..."
curl -sSL -o "$ASSET_DIR/lib/d3.min.js" \
  https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js

curl -sSL -o "$ASSET_DIR/lib/topojson.min.js" \
  https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js

echo ">>> 下载地理数据..."
curl -sSL -o "$ASSET_DIR/data/countries-110m.json" \
  https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json

curl -sSL -o "$ASSET_DIR/data/lakes.geojson" \
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_lakes.geojson || true

echo ""
echo "✓ 资源下载完成！"
echo "  资源目录: $ASSET_DIR"
ls -la "$ASSET_DIR/lib/"
ls -la "$ASSET_DIR/data/"

#!/bin/bash
# HistRAG 资源自动下载脚本
# 下载 3D 地图（Three.js r128、GSAP 3）和 2D fallback（D3、topojson）所需的所有本地库
# 
# 使用方式：
#   cd hHarness-main/Harness/histrag/resources
#   bash setup.sh
#
# 也可由 integration.py 在服务器首次启动时自动调用。

set -e
# ↓ 加这两行，强制使用代理
export https_proxy="${https_proxy:-http://127.0.0.1:7890}"
export http_proxy="${http_proxy:-http://127.0.0.1:7890}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$SCRIPT_DIR/lib"
DATA_DIR="$SCRIPT_DIR/data"

echo "==================================================="
echo "  HistRAG 资源下载"
echo "==================================================="
echo ""

mkdir -p "$LIB_DIR" "$DATA_DIR"

# ── 辅助函数：下载并验证文件 ────────────────────────────────
download() {
  local name="$1"
  local url="$2"
  local dest="$3"
  local min_size="${4:-10000}"   # 最小合法文件大小（bytes）

  if [ -f "$dest" ] && [ "$(wc -c < "$dest")" -ge "$min_size" ]; then
    echo "  ✓ $name 已存在，跳过"
    return 0
  fi

  printf "  ⬇  下载 %s ... " "$name"
  if curl -sSL --insecure --connect-timeout 30 --max-time 120 -o "$dest" "$url"; then
    local size
    size=$(wc -c < "$dest")
    if [ "$size" -ge "$min_size" ]; then
      echo "✓ (${size} bytes)"
    else
      echo "✗ 文件过小 (${size} bytes)，可能下载失败"
      rm -f "$dest"
      return 1
    fi
  else
    echo "✗ 下载失败"
    return 1
  fi
}

# ── 1. Three.js r128（3D 地图核心，~600KB）────────────────────
echo ">>> JS 库（3D 渲染）"
download "Three.js r128" \
  "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js" \
  "$LIB_DIR/three.min.js" \
  400000 || \
download "Three.js r128 (备用CDN)" \
  "https://unpkg.com/three@0.128.0/build/three.min.js" \
  "$LIB_DIR/three.min.js" \
  400000 || \
echo "  ⚠️  Three.js 下载失败，3D 地图将在有网环境下从 CDN 加载"

# ── 2. GSAP 3（动画库，~70KB）────────────────────────────────
download "GSAP 3.12" \
  "https://cdn.jsdelivr.net/npm/gsap@3.12.2/dist/gsap.min.js" \
  "$LIB_DIR/gsap.min.js" \
  50000 || \
download "GSAP 3.12 (备用CDN)" \
  "https://unpkg.com/gsap@3.12.2/dist/gsap.min.js" \
  "$LIB_DIR/gsap.min.js" \
  50000 || \
echo "  ⚠️  GSAP 下载失败，动画将在有网环境下从 CDN 加载"

echo ""
echo ">>> JS 库（2D fallback）"

# ── 3. D3 v7（2D 地图 fallback）──────────────────────────────
download "D3 v7" \
  "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js" \
  "$LIB_DIR/d3.min.js" \
  200000 || \
echo "  ⚠️  D3 下载失败"

# ── 4. topojson（2D 地图 fallback）───────────────────────────
download "topojson-client" \
  "https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js" \
  "$LIB_DIR/topojson.min.js" \
  5000 || \
echo "  ⚠️  topojson 下载失败"

echo ""
echo ">>> 地理数据"

# ── 5. 世界地图 110m（countries-110m.json）────────────────────
download "world-atlas countries-110m" \
  "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json" \
  "$DATA_DIR/countries-110m.json" \
  80000 || \
echo "  ⚠️  countries-110m.json 下载失败"

# ── 6. 湖泊数据（可选）───────────────────────────────────────
download "lakes.geojson" \
  "https://cdn.jsdelivr.net/npm/natural-earth-geojson@1.1.1/ne_50m_lakes.geojson" \
  "$DATA_DIR/lakes.geojson" \
  10000 || \
echo "  ℹ  lakes.geojson 下载失败，地图不显示湖泊（不影响主功能）"

# ── 7. rivers.geojson 占位（原始项目中为空）──────────────────
if [ ! -f "$DATA_DIR/rivers.geojson" ]; then
  echo '{"type":"FeatureCollection","features":[]}' > "$DATA_DIR/rivers.geojson"
  echo "  ✓ rivers.geojson 创建（占位）"
fi

# ── 完成 ─────────────────────────────────────────────────────
echo ""
echo "==================================================="
echo "  下载完成"
echo "==================================================="
echo ""
echo "  lib 目录："
ls -lh "$LIB_DIR/" 2>/dev/null || echo "  （空）"
echo ""
echo "  data 目录："
ls -lh "$DATA_DIR/" 2>/dev/null || echo "  （空）"
echo ""

# 验证关键文件
CRITICAL_OK=true
for f in three.min.js gsap.min.js; do
  size=$(wc -c < "$LIB_DIR/$f" 2>/dev/null || echo 0)
  if [ "$size" -lt 10000 ]; then
    echo "  ❌ $f 缺失或损坏"
    CRITICAL_OK=false
  fi
done

if [ "$CRITICAL_OK" = true ]; then
  echo "  ✅ 关键文件验证通过，3D 地图可离线运行"
else
  echo "  ⚠️  部分关键文件缺失，3D 地图将尝试从 CDN 加载"
  echo "     请检查网络连接后重试：bash setup.sh"
fi
echo ""
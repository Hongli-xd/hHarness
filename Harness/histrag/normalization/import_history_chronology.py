"""Import reign-year mappings from the HistoryChronology SQLite database."""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

PINYIN_SLUGS = {
    "唐": "tang",
    "东汉": "eastern-han",
    "高祖": "gaozu",
    "太宗": "taizong",
    "高宗": "gaozong",
    "中宗": "zhongzong",
    "睿宗": "ruizong",
    "玄宗": "xuanzong",
    "肃宗": "suzong",
    "代宗": "daizong",
    "德宗": "dezong",
    "顺宗": "shunzong",
    "宪宗": "xianzong",
    "穆宗": "muzong",
    "敬宗": "jingzong",
    "文宗": "wenzong",
    "武宗": "wuzong",
    "宣宗": "xuanzong2",
    "懿宗": "yizong",
    "僖宗": "xizong",
    "昭宗": "zhaozong",
    "哀帝": "aidi",
    "章帝": "zhangdi",
    "开元": "kaiyuan",
    "元和": "yuanhe",
    "贞观": "zhenguan",
    "永徽": "yonghui",
    "显庆": "xianqing",
    "龙朔": "longshuo",
    "麟德": "linde",
    "乾封": "qianfeng",
    "总章": "zongzhang",
    "咸亨": "xianheng",
    "上元": "shangyuan",
    "仪凤": "yifeng",
    "调露": "tiaolu",
    "永隆": "yonglong",
    "开耀": "kaiyao",
    "永淳": "yongchun",
    "弘道": "hongdao",
    "嗣圣": "sisheng",
    "文明": "wenming",
    "神龙": "shenlong",
    "景龙": "jinglong",
    "唐隆": "tanglong",
    "景云": "jingyun",
    "太极": "taiji",
    "延和": "yanhe",
    "先天": "xiantian",
    "天宝": "tianbao",
    "至德": "至德",
    "乾元": "qianyuan",
    "宝应": "baoying",
    "广德": "guangde",
    "永泰": "yongtai",
    "大历": "dali",
    "建中": "jianzhong",
    "兴元": "xingyuan",
    "长庆": "changqing",
    "宝历": "baoli",
    "大和（太和）": "dahe-taihe",
    "开成": "kaicheng",
    "会昌": "huichang",
    "大中": "dazhong",
    "咸通": "xiantong",
    "乾符": "qianfu",
    "广明": "guangming",
    "中和": "zhonghe",
    "光启": "guangqi",
    "文德": "wende",
    "龙纪": "longji",
    "大顺": "dashun",
    "景福": "jingfu",
    "乾宁": "qianning",
    "光化": "guanghua",
    "天复": "tianfu",
    "天佑": "tianyou",
    "武德": "wude",
}

TRADITIONAL_TO_SIMPLIFIED = {
    "憲": "宪",
    "貞": "贞",
    "觀": "观",
    "顯": "显",
    "慶": "庆",
    "龍": "龙",
    "儀": "仪",
    "鳳": "凤",
    "調": "调",
    "開": "开",
    "聖": "圣",
    "純": "纯",
    "劉": "刘",
    "淵": "渊",
    "總": "总",
    "則": "则",
    "載": "载",
    "雲": "云",
    "極": "极",
    "寶": "宝",
    "肅": "肃",
    "廣": "广",
    "應": "应",
    "曆": "历",
    "歷": "历",
    "興": "兴",
    "順": "顺",
    "長": "长",
    "會": "会",
    "啓": "启",
    "紀": "纪",
    "寧": "宁",
    "復": "复",
    "祐": "佑",
    "楊": "杨",
    "曌": "曌",
}


def export_reigns(db_path: str | Path, dynasty: str = "唐") -> dict[str, Any]:
    rows = _read_rows(Path(db_path), dynasty)
    grouped: dict[tuple[str, str, str, str, str], dict[int, int]] = defaultdict(dict)

    for row in rows:
        if row["年份"] is None or row["公元"] is None:
            continue
        reign_title = _normalize_text(row["年号"])
        reign_year = int(row["年份"])
        year = int(row["公元"])
        key = (
            _normalize_text(row["时期"]),
            _normalize_text(row["政权"]),
            _normalize_text(row["帝号"]),
            _normalize_text(row["帝名"]),
            reign_title,
        )
        grouped[key][reign_year] = year

    reigns = []
    for (period, polity, emperor_title, emperor_name, reign_title), mapping in sorted(
        grouped.items(), key=lambda item: min(item[1].values())
    ):
        dynasty_value = period or polity or dynasty
        reigns.append(
            {
                "id": _reign_id(polity or dynasty_value, emperor_title, reign_title),
                "dynasty": dynasty_value,
                "polity": polity,
                "emperor": f"{polity}{emperor_title}" if polity and emperor_title else emperor_title,
                "emperor_name": emperor_name,
                "reign_title": reign_title,
                "start_year": min(mapping.values()),
                "end_year": max(mapping.values()),
                "mapping": dict(sorted(mapping.items())),
                "source": "HistoryChronology",
            }
        )

    return {"source": "HistoryChronology", "dynasty": dynasty, "reigns": reigns}


def write_reigns_yaml(db_path: str | Path, output_path: str | Path, dynasty: str = "唐") -> None:
    data = export_reigns(db_path, dynasty=dynasty)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export HistoryChronology reign rows to YAML.")
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--dynasty", default="唐")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    write_reigns_yaml(args.db_path, args.output, dynasty=args.dynasty)


def _read_rows(db_path: Path, dynasty: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return list(
            conn.execute(
                """
                select "公元", "干支", "时期", "政权", "帝号", "帝名", "年号", "年份"
                from history_chronology
                where "政权" = ?
                  and "年号" is not null
                  and trim("年号") != ''
                order by "公元", "年份"
                """,
                (dynasty,),
            )
        )


def _reign_id(polity: str, emperor_title: str, reign_title: str) -> str:
    polity_slug = _slug(polity)
    emperor_slug = _slug(emperor_title)
    reign_slug = _slug(reign_title)
    return f"reign:{polity_slug}:{emperor_slug}:{reign_slug}"


def _slug(value: str) -> str:
    normalized = _normalize_text(value)
    if normalized in PINYIN_SLUGS:
        return PINYIN_SLUGS[normalized]
    ascii_value = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return ascii_value or normalized


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    for traditional, simplified in TRADITIONAL_TO_SIMPLIFIED.items():
        text = text.replace(traditional, simplified)
    return text


if __name__ == "__main__":
    main()

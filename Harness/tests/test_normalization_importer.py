"""Tests for importing reign data from HistoryChronology."""

import sqlite3

from histrag.normalization.import_history_chronology import export_reigns


def test_export_reigns_groups_history_chronology_rows(tmp_path):
    db_path = tmp_path / "History_Chronology.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            create table history_chronology (
                "公元" integer,
                "干支" text,
                "时期" text,
                "政权" text,
                "帝号" text,
                "帝名" text,
                "年号" text,
                "年份" real
            )
            """
        )
        conn.executemany(
            'insert into history_chronology values (?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (713, "癸丑", "唐", "唐", "玄宗", "李隆基", "开元", 1.0),
                (714, "甲寅", "唐", "唐", "玄宗", "李隆基", "开元", 2.0),
                (806, "丙戌", "唐", "唐", "宪宗", "李纯", "元和", 1.0),
                (618, "戊寅", "唐", "隋", "恭帝", "杨侑", "义宁", 2.0),
                (907, "丁卯", "唐", "唐", "", "", "天祐", None),
                (84, "甲申", "东汉", "东汉", "章帝", "刘炟", "元和", 1.0),
            ],
        )

    exported = export_reigns(db_path, dynasty="唐")

    assert exported["source"] == "HistoryChronology"
    assert [reign["reign_title"] for reign in exported["reigns"]] == ["开元", "元和"]
    kaiyuan = exported["reigns"][0]
    assert kaiyuan["id"] == "reign:tang:xuanzong:kaiyuan"
    assert kaiyuan["dynasty"] == "唐"
    assert kaiyuan["emperor"] == "唐玄宗"
    assert kaiyuan["start_year"] == 713
    assert kaiyuan["end_year"] == 714
    assert kaiyuan["mapping"] == {1: 713, 2: 714}

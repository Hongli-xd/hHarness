#!/usr/bin/env python3
"""Import the bundled LightRAG Neo4j Cypher export into Neo4j.

The checked-in export was produced by LightRAG/scripts/export_neo4j.py, but that
exporter writes non-standard Cypher maps and omits entity_id from node records.
This importer restores the useful part of the export: entity ids from relationship
endpoints and all relationship properties.
"""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


EDGE_RE = re.compile(
    r"\(a\{entity_id: '(?P<src>.*)'\}\)"
    r"-\[r:(?P<rel_type>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?: \{(?P<props>.*?)\})?\]->"
    r"\(b\{entity_id: '(?P<tgt>.*)'\}\)"
)
PROP_KEY_RE = re.compile(r"\br\.([A-Za-z_][A-Za-z0-9_]*)\s*=")


def parse_props(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    pythonish = PROP_KEY_RE.sub(r"'\1':", raw)
    pythonish = re.sub(r"\bnull\b", "None", pythonish)
    pythonish = re.sub(r"\btrue\b", "True", pythonish)
    pythonish = re.sub(r"\bfalse\b", "False", pythonish)
    return ast.literal_eval("{" + pythonish + "}")


def iter_edges(path: Path):
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if ")-[r:" not in line:
            continue
        line = line.strip().rstrip(",")
        match = EDGE_RE.search(line)
        if not match:
            raise ValueError(f"Could not parse edge at line {line_no}: {line[:200]}")
        yield {
            "src": match.group("src"),
            "tgt": match.group("tgt"),
            "rel_type": match.group("rel_type"),
            "props": parse_props(match.group("props")),
        }


def chunked(items: list[dict[str, Any]], size: int):
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_file", type=Path)
    parser.add_argument("--uri", default="bolt://localhost:7687")
    parser.add_argument("--username", default="neo4j")
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--workspace", default="base")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--clear-workspace",
        action="store_true",
        help="Delete existing nodes with the workspace label before import.",
    )
    args = parser.parse_args()

    edges = list(iter_edges(args.export_file))
    nodes = sorted({edge["src"] for edge in edges} | {edge["tgt"] for edge in edges})
    print(f"Parsed {len(nodes)} entities and {len(edges)} relationships")

    driver = GraphDatabase.driver(args.uri, auth=(args.username, args.password))
    rel_types = sorted({edge["rel_type"] for edge in edges})

    with driver.session(database=args.database) as session:
        if args.clear_workspace:
            print(f"Clearing existing :{args.workspace} graph")
            session.run(f"MATCH (n:`{args.workspace}`) DETACH DELETE n").consume()

        session.run(
            f"CREATE INDEX IF NOT EXISTS FOR (n:`{args.workspace}`) ON (n.entity_id)"
        ).consume()

        for batch in chunked([{"entity_id": node} for node in nodes], args.batch_size):
            session.run(
                f"""
                UNWIND $rows AS row
                MERGE (n:`{args.workspace}` {{entity_id: row.entity_id}})
                """,
                rows=batch,
            ).consume()

        for rel_type in rel_types:
            rows = [edge for edge in edges if edge["rel_type"] == rel_type]
            for batch in chunked(rows, args.batch_size):
                session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (src:`{args.workspace}` {{entity_id: row.src}})
                    MATCH (tgt:`{args.workspace}` {{entity_id: row.tgt}})
                    MERGE (src)-[r:`{rel_type}`]->(tgt)
                    SET r += row.props
                    """,
                    rows=batch,
                ).consume()

        entity_count = session.run(
            f"MATCH (n:`{args.workspace}`) RETURN count(n) AS count"
        ).single()["count"]
        rel_count = session.run(
            f"MATCH (:`{args.workspace}`)-[r]->(:`{args.workspace}`) RETURN count(r) AS count"
        ).single()["count"]

    driver.close()
    print(f"Imported {entity_count} entities and {rel_count} relationships")


if __name__ == "__main__":
    main()

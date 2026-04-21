"""
Neo4j Database Export Tool

导出 Neo4j 数据库为 CYPHER 格式文件，可直接导入到其他 Neo4j 数据库。

使用方式:
    python export_neo4j.py                    # 导出默认 workspace
    python export_neo4j.py --workspace custom # 导出指定 workspace
    python export_neo4j.py --output mygraph   # 指定输出文件名
"""

import os
import asyncio
import argparse
import configparser
from datetime import datetime

from dotenv import load_dotenv
import pipmaster as pm

if not pm.is_installed("neo4j"):
    pm.install("neo4j")

from neo4j import AsyncGraphDatabase

load_dotenv(dotenv_path=".env", override=False)

config = configparser.ConfigParser()
config.read("config.ini", "utf-8")


async def get_neo4j_connection():
    """建立 Neo4j 连接"""
    URI = os.environ.get("NEO4J_URI", config.get("neo4j", "uri", fallback=None))
    USERNAME = os.environ.get("NEO4J_USERNAME", config.get("neo4j", "username", fallback=None))
    PASSWORD = os.environ.get("NEO4J_PASSWORD", config.get("neo4j", "password", fallback=None))
    DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

    if not URI:
        raise ValueError(
            "Neo4j URI not configured. Please set:\n"
            "  - NEO4J_URI environment variable, or\n"
            "  - uri in config.ini [neo4j] section\n"
            "Example: bolt://localhost:7687"
        )
    if not USERNAME:
        raise ValueError(
            "Neo4j username not configured. Please set:\n"
            "  - NEO4J_USERNAME environment variable, or\n"
            "  - username in config.ini [neo4j] section"
        )
    if not PASSWORD:
        raise ValueError(
            "Neo4j password not configured. Please set:\n"
            "  - NEO4J_PASSWORD environment variable, or\n"
            "  - password in config.ini [neo4j] section"
        )

    driver = AsyncGraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    return driver, DATABASE


def escape_cypher_value(value) -> str:
    """转义 Cypher 值"""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # 转义单引号和反斜杠
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    elif isinstance(value, list):
        items = ", ".join(escape_cypher_value(item) for item in value)
        return f"[{items}]"
    elif isinstance(value, dict):
        props = ", ".join(f"{k}: {escape_cypher_value(v)}" for k, v in value.items())
        return f"{{{props}}}"
    else:
        return f"'{str(value)}'"


async def export_workspace(driver, database, workspace_label, output_file):
    """导出指定 workspace 的所有数据到 CYPHER 文件"""

    cypher_statements = []

    # 文件头注释
    cypher_statements.append(
        f""":begin
# Neo4j Database Export
# Workspace: {workspace_label}
# Exported at: {datetime.now().isoformat()}
# Format: CYPHER for Neo4j

"""
    )

    async with driver.session(database=database) as session:
        # 1. 导出所有节点
        cypher_statements.append(":begin\nCREATE\n")
        node_lines = []

        query = f"MATCH (n:`{workspace_label}`) RETURN n"
        result = await session.run(query)

        node_count = 0
        async for record in result:
            node = record["n"]
            labels = [l for l in node.labels if l != workspace_label]
            if not labels:
                labels = [workspace_label]
            props = {k: v for k, v in dict(node).items() if k != "entity_id"}

            if props:
                props_str = ", ".join(
                    f"n.{k} = {escape_cypher_value(v)}" for k, v in props.items()
                )
                line = f"  (n{':'.join(labels)} {{{props_str}}})"
            else:
                line = f"  (n{':'.join(labels)})"

            node_lines.append(line)
            node_count += 1

        await result.consume()

        if node_lines:
            cypher_statements.append(",\n".join(node_lines) + "\n")
            cypher_statements.append(":commit\n\n")

        print(f"Exported {node_count} nodes")

        # 2. 导出所有关系
        cypher_statements.append(":begin\nCREATE\n")
        edge_lines = []

        query = f"""
        MATCH (a:`{workspace_label}`)-[r]-(b:`{workspace_label}`)
        RETURN a.entity_id AS source, b.entity_id AS target, properties(r) AS props, type(r) AS rel_type
        """
        result = await session.run(query)

        edge_count = 0
        async for record in result:
            source = record["source"]
            target = record["target"]
            rel_type = record["rel_type"] or "DIRECTED"
            props = record["props"] or {}

            if props:
                props_str = ", ".join(
                    f"r.{k} = {escape_cypher_value(v)}" for k, v in props.items()
                )
                line = f"  (a{{entity_id: '{source}'}})-[r:{rel_type} {{{props_str}}}]->(b{{entity_id: '{target}'}})"
            else:
                line = f"  (a{{entity_id: '{source}'}})-[r:{rel_type}]->(b{{entity_id: '{target}'}})"

            edge_lines.append(line)
            edge_count += 1

        await result.consume()

        if edge_lines:
            cypher_statements.append(",\n".join(edge_lines) + "\n")
            cypher_statements.append(":commit\n\n")

        print(f"Exported {edge_count} edges")

    # 写入文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(cypher_statements)

    print(f"\nExport completed: {output_file}")
    return output_file


async def main():
    parser = argparse.ArgumentParser(description="Export Neo4j workspace to CYPHER file")
    parser.add_argument(
        "--workspace",
        type=str,
        default=os.environ.get("NEO4J_WORKSPACE", "base"),
        help="Workspace label to export (default: from NEO4J_WORKSPACE env or 'base')",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (default: neo4j_export_{workspace}_{timestamp}.cypher)",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="Database name (default: from NEO4J_DATABASE env or 'neo4j')",
    )

    args = parser.parse_args()

    workspace = args.workspace.strip() if args.workspace else "base"
    if not workspace or workspace in (".", "./", ".\\"):
        workspace = "base"
    safe_workspace = workspace.replace("/", "_").replace("\\", "_").replace("..", "_").strip("_") or "base"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.output or f"neo4j_export_{safe_workspace}_{timestamp}.cypher"

    database = args.database or os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = None
    try:
        driver, db = await get_neo4j_connection()
        print(f"Connecting to Neo4j database: {db}")
        print(f"Exporting workspace: {workspace}")

        await export_workspace(driver, db, workspace, output_file)

        # 计算文件大小
        size = os.path.getsize(output_file)
        print(f"File size: {size / 1024:.2f} KB")

        print("\n" + "=" * 50)
        print("IMPORT INSTRUCTIONS")
        print("=" * 50)
        print(f"""
To import this file into Neo4j:
1. Open Neo4j Desktop or Neo4j Browser
2. Run: :play <path/to/{output_file}>
3. Or use cypher-shell:
   cypher-shell -u <username> -p <password> < {output_file}
        """)

    finally:
        if driver:
            await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

"""MCP server for InfluxDB v1 — read-only query and schema exploration."""

import os
import re
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("influxdb")

INFLUXDB_URL = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_USERNAME = os.environ.get("INFLUXDB_USERNAME")
INFLUXDB_PASSWORD = os.environ.get("INFLUXDB_PASSWORD")

WRITE_PATTERN = re.compile(
    r"\b(CREATE|DROP|DELETE|ALTER|GRANT|REVOKE|KILL|INSERT|INTO)\b",
    re.IGNORECASE,
)


async def _influx_request(
    method: str,
    path: str,
    params: Optional[dict] = None,
) -> httpx.Response:
    """Make an HTTP request to InfluxDB, adding auth params if configured."""
    if params is None:
        params = {}
    if INFLUXDB_USERNAME:
        params["u"] = INFLUXDB_USERNAME
    if INFLUXDB_PASSWORD:
        params["p"] = INFLUXDB_PASSWORD

    url = f"{INFLUXDB_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, params=params, timeout=30.0)
        return resp


async def _influx_query(
    q: str,
    db: Optional[str] = None,
    epoch: Optional[str] = None,
) -> dict:
    """Execute an InfluxQL query and return the parsed JSON response."""
    params: dict[str, str] = {"q": q}
    if db:
        params["db"] = db
    if epoch:
        params["epoch"] = epoch

    resp = await _influx_request("GET", "/query", params)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    results = data.get("results", [])
    for r in results:
        if "error" in r:
            raise RuntimeError(r["error"])

    return data


def _format_series(data: dict) -> str:
    """Convert InfluxDB JSON response into a readable text table."""
    results = data.get("results", [])
    if not results:
        return "No results."

    parts: list[str] = []
    for i, result in enumerate(results):
        series_list = result.get("series", [])
        if not series_list:
            if len(results) == 1:
                return "Query returned no data."
            parts.append(f"Statement {i}: no data.")
            continue

        for series in series_list:
            name = series.get("name", "")
            columns = series.get("columns", [])
            values = series.get("values", [])
            tags = series.get("tags", {})

            header = f"-- {name}" if name else ""
            if tags:
                tag_str = ", ".join(f"{k}={v}" for k, v in tags.items())
                header += f" [{tag_str}]" if header else f"-- [{tag_str}]"
            if header:
                parts.append(header)

            if not columns:
                continue

            col_widths = [len(str(c)) for c in columns]
            for row in values:
                for j, val in enumerate(row):
                    col_widths[j] = max(col_widths[j], len(str(val)))

            fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
            parts.append(fmt.format(*[str(c) for c in columns]))
            parts.append(fmt.format(*["-" * w for w in col_widths]))
            for row in values:
                parts.append(fmt.format(*[str(v) for v in row]))
            parts.append("")

    return "\n".join(parts).rstrip()


def _extract_values(data: dict, column: str = "name") -> list[str]:
    """Extract a flat list of values from a single column in the response."""
    items: list[str] = []
    for result in data.get("results", []):
        for series in result.get("series", []):
            columns = series.get("columns", [])
            if column not in columns:
                continue
            idx = columns.index(column)
            for row in series.get("values", []):
                items.append(str(row[idx]))
    return items


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def ping() -> str:
    """Check connectivity to the InfluxDB instance. Returns the server version."""
    resp = await _influx_request("GET", "/ping")
    version = resp.headers.get("X-Influxdb-Version", "unknown")
    return f"OK — InfluxDB {version} at {INFLUXDB_URL}"


@mcp.tool()
async def list_databases() -> str:
    """List all databases on the InfluxDB instance."""
    data = await _influx_query("SHOW DATABASES")
    dbs = _extract_values(data, "name")
    if not dbs:
        return "No databases found."
    return "\n".join(dbs)


@mcp.tool()
async def list_measurements(database: str) -> str:
    """List all measurements in a database.

    Args:
        database: Name of the InfluxDB database.
    """
    data = await _influx_query("SHOW MEASUREMENTS", db=database)
    measurements = _extract_values(data, "name")
    if not measurements:
        return f"No measurements found in '{database}'."
    return "\n".join(measurements)


@mcp.tool()
async def list_tag_keys(database: str, measurement: Optional[str] = None) -> str:
    """List tag keys in a database, optionally filtered by measurement.

    Args:
        database: Name of the InfluxDB database.
        measurement: Optional measurement name to filter by.
    """
    q = "SHOW TAG KEYS"
    if measurement:
        q += f' FROM "{measurement}"'
    data = await _influx_query(q, db=database)
    keys = _extract_values(data, "tagKey")
    if not keys:
        return "No tag keys found."
    return "\n".join(sorted(set(keys)))


@mcp.tool()
async def list_field_keys(database: str, measurement: Optional[str] = None) -> str:
    """List field keys and their types in a database, optionally filtered by measurement.

    Args:
        database: Name of the InfluxDB database.
        measurement: Optional measurement name to filter by.
    """
    q = "SHOW FIELD KEYS"
    if measurement:
        q += f' FROM "{measurement}"'
    data = await _influx_query(q, db=database)
    return _format_series(data)


@mcp.tool()
async def list_tag_values(
    database: str, tag_key: str, measurement: Optional[str] = None
) -> str:
    """List values for a specific tag key.

    Args:
        database: Name of the InfluxDB database.
        tag_key: The tag key whose values you want to list.
        measurement: Optional measurement name to filter by.
    """
    q = ""
    if measurement:
        q = f'SHOW TAG VALUES FROM "{measurement}" WITH KEY = "{tag_key}"'
    else:
        q = f'SHOW TAG VALUES WITH KEY = "{tag_key}"'
    data = await _influx_query(q, db=database)
    return _format_series(data)


@mcp.tool()
async def query(database: str, influxql: str, epoch: str = "ms") -> str:
    """Execute a read-only InfluxQL query against a database.

    Only SELECT and SHOW statements are allowed. Write operations are blocked.

    Args:
        database: Name of the InfluxDB database to query.
        influxql: The InfluxQL query to execute (e.g. SELECT * FROM cpu LIMIT 10).
        epoch: Timestamp precision in the response (ns, u, ms, s, m, h). Default: ms.
    """
    if WRITE_PATTERN.search(influxql):
        return (
            "Error: write/admin operations are not allowed. "
            "Only SELECT and SHOW queries are permitted."
        )
    data = await _influx_query(influxql, db=database, epoch=epoch)
    return _format_series(data)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

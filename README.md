# mcflux

Read-only MCP server for **InfluxDB v1**. Lets Claude (Desktop or Code) query and explore your time-series data through the Model Context Protocol.

## Tools

| Tool | Description |
|------|-------------|
| `ping` | Check connectivity and return the InfluxDB version |
| `list_databases` | List all databases |
| `list_measurements` | List measurements in a database |
| `list_tag_keys` | List tag keys, optionally filtered by measurement |
| `list_field_keys` | List field keys and their types |
| `list_tag_values` | List values for a specific tag key |
| `query` | Execute a read-only InfluxQL query (SELECT/SHOW only) |

Write operations (`CREATE`, `DROP`, `DELETE`, `INSERT`, etc.) are blocked at the server level.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- An InfluxDB v1 instance

## Installation

### Claude Desktop (extension)

Download the latest `.mcpb` from [Releases](https://github.com/dmayan-ss/mcpflux/releases), then:

1. Open Claude Desktop
2. Go to **Settings > Extensions > Advanced settings**
3. Click **Install Extension** and select the `.mcpb` file
4. Fill in your InfluxDB URL, username, and password in the configuration form

### Claude Desktop (manual)

Add to `claude_desktop_config.json`:

- **Windows**: `%AppData%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "influxdb": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcflux", "run", "server.py"],
      "env": {
        "INFLUXDB_URL": "http://localhost:8086",
        "INFLUXDB_USERNAME": "myuser",
        "INFLUXDB_PASSWORD": "mypass"
      }
    }
  }
}
```

### Claude Code

Add to `.claude/settings.json` or your project settings:

```json
{
  "mcpServers": {
    "influxdb": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcflux", "run", "server.py"],
      "env": {
        "INFLUXDB_URL": "http://localhost:8086",
        "INFLUXDB_USERNAME": "myuser",
        "INFLUXDB_PASSWORD": "mypass"
      }
    }
  }
}
```

## Configuration

| Environment variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `INFLUXDB_URL` | No | `http://localhost:8086` | InfluxDB HTTP API URL |
| `INFLUXDB_USERNAME` | No | *(none)* | Username for basic auth |
| `INFLUXDB_PASSWORD` | No | *(none)* | Password for basic auth |

Omit `INFLUXDB_USERNAME` and `INFLUXDB_PASSWORD` if your instance does not require authentication.

## Building the .mcpb bundle

```bash
npm install -g @anthropic-ai/mcpb
mcpb pack .
```

This produces a `mcflux.mcpb` file that can be installed as a Claude Desktop extension.

## License

[MIT](LICENSE)

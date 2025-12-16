# Weather Demo MCP Server (Python)

This repo is a minimal **Model Context Protocol (MCP)** server you can point VS Code (or other MCP clients) at.

It exposes a single MCP **tool**:

- `get_weather(zip_code)` → current weather for a US ZIP code

No API keys are required (uses Zippopotam.us + Open-Meteo).

## What MCP is (quick mental model)

MCP is a protocol where an **AI client** (VS Code, an agent runner, etc.) connects to an **MCP server** and discovers:

- **Tools**: functions the model can call (like `get_weather`)
- **Resources**: addressable data (like `file://...` or `db://...` style URIs)
- **Prompts**: templated prompts the client can insert

The client communicates with the server over a transport (commonly **stdio** for local processes, or HTTP/SSE for remote servers). The MCP messages flow over the transport; for stdio servers, **stdout is reserved for protocol traffic**, so you should log to **stderr**.

## Project layout

- `server.py` – the MCP server using the Python MCP SDK (`FastMCP`)
- `.vscode/mcp.json` – workspace configuration for VS Code to launch the server
- `requirements.txt` – dependencies

## Setup (Windows / PowerShell)

From the workspace root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
```

## Run it manually (optional)

This starts the MCP server over stdio (it will wait for a client):

```powershell
.\.venv\Scripts\Activate.ps1
python .\server.py
```

If you run it directly, you won’t see much besides logs; the server is meant to be launched by an MCP client.

## Use with VS Code

This repo includes `.vscode/mcp.json`, which tells VS Code how to start the server:

```jsonc
{
  "servers": {
    "weather-demo": {
      "type": "stdio",
      "command": "python",
      "args": ["${workspaceFolder}/server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

In VS Code:

1. Open this folder.
2. Open Copilot Chat and switch to **Agent** mode.
3. Start the server using one of:
   - Command Palette → **MCP: List Servers** → start `weather-demo`
   - Or open `.vscode/mcp.json` and use the start/restart actions
4. In the tools picker, enable the MCP tools for `weather-demo`.
5. Ask: “What’s the weather for 02139?”

### Troubleshooting tips

- If tools don’t show up after you rename/change them, run **MCP: Reset Cached Tools**.
- If the server fails to start, open **MCP: List Servers** and view **Output** for logs.
- Avoid printing to stdout from your server outside of the MCP runtime; log to stderr.

## Notes on the demo weather implementation

- ZIP → lat/lon: `https://api.zippopotam.us/us/{zip}`
- Weather: Open-Meteo `forecast` endpoint with `current=...`

The tool returns a JSON object including location, units, and current observations.

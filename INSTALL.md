# Install

## 1. Prerequisites

- LibreOffice with `soffice` on `PATH`
- The Python UNO bindings for the system Python (`import uno` must work)
- Python 3.10 or newer

The package name for the UNO bindings varies by distribution. Look for
`python3-uno` (Debian/Ubuntu) or the equivalent package for your system. On
some distributions the bindings ship with LibreOffice itself.

Verify:

```bash
soffice --version
python3 -c "import uno; print('uno ok')"
```

If `import uno` fails, install the bindings before continuing. The bundled
virtualenv cannot supply `uno` on its own.

## 2. Set up the virtualenv

The venv must see the system packages:

```bash
cd /home/martin/libreoffice-impress-mcp
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

Check both imports:

```bash
.venv/bin/python -c "import uno; import mcp; print('ok')"
```

## 3. Run the server

```bash
./run.sh
```

It speaks MCP over stdio, so it is normally started by the MCP client rather
than by hand. Running it directly should simply wait for JSON-RPC input.

## 4. Configure your MCP client

The server is a standard stdio MCP server. Point your client at the launcher:

- transport: `stdio`
- command: `/home/martin/libreoffice-impress-mcp/run.sh`
- arguments: none
- optional environment: `IMPRESS_MCP_PORT`, `IMPRESS_MCP_HOST`,
  `IMPRESS_MCP_PROFILE`, `IMPRESS_MCP_HEADLESS`, `IMPRESS_MCP_AUTOLAUNCH`

Many clients accept a JSON block shaped like this:

```json
{
  "mcpServers": {
    "libreoffice-impress": {
      "command": "/home/martin/libreoffice-impress-mcp/run.sh",
      "env": {
        "IMPRESS_MCP_PORT": "2002"
      }
    }
  }
}
```

Field names vary between clients. If your client wants an interpreter and a
script instead of a launcher, use:

```json
{
  "command": "/home/martin/libreoffice-impress-mcp/.venv/bin/python",
  "args": ["/home/martin/libreoffice-impress-mcp/server.py"]
}
```

Restart your MCP client after changing its configuration; most clients load
server definitions only at startup.

## 5. First use

1. Call `impress_launch`. This starts LibreOffice with a dedicated profile and
   a UNO socket on port 2002. It does not attach to an already running
   LibreOffice, because a normal instance has no control socket.
2. Call `impress_new_presentation` or `impress_open`.
3. Use the other `impress_*` tools.

Startup with `headless: true` avoids opening a window. The window is needed
only if you want to watch the changes live.

## Troubleshooting

### `ModuleNotFoundError: No module named 'uno'`

The venv was created without `--system-site-packages`, or the system Python
does not have the UNO bindings. Recreate the venv as shown above and verify
`python3 -c "import uno"` outside the venv.

### `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`

The installed MCP SDK is version 2 or newer. This project uses
`mcp.server.mcpserver.MCPServer`. Keep `requirements.txt` pinned to
`mcp>=2,<3` or update the imports when migrating.

### `Could not reach LibreOffice Impress`

Start it with `impress_launch` or `impress_connect(auto_launch=true)`. A
LibreOffice window started normally does not listen on the UNO socket. Close
it if you want the MCP-managed instance to be the only one.

### `No Impress presentation is open`

Call `impress_new_presentation` or `impress_open` before slide tools.

### Port already in use

Use another port consistently in both the launch and the client:

```bash
IMPRESS_MCP_PORT=2003 ./run.sh
```

The server passes its port to the `soffice` launch command, so one setting is
enough.

### Tools do not appear in the MCP client

Restart the client. Check that `run.sh` is executable and that the path in the
client configuration is absolute.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `IMPRESS_MCP_HOST` | `localhost` | UNO socket host |
| `IMPRESS_MCP_PORT` | `2002` | UNO socket port |
| `IMPRESS_MCP_PROFILE` | `~/.cache/libreoffice-impress-mcp/profile` | Dedicated LibreOffice profile |
| `IMPRESS_MCP_HEADLESS` | `0` | Set to `1` to launch without a window |
| `IMPRESS_MCP_AUTOLAUNCH` | `0` | Set to `1` to auto-launch from any tool call |

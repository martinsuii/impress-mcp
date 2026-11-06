# AGENTS.md

Guidance for coding agents working on this repository.

## What this project is

An MCP server that controls a live LibreOffice Impress instance over the UNO
API. It is not an offline presentation generator: every operation acts on a
running `soffice` process through a local UNO socket.

## Layout

- `server.py` — MCP tool definitions and input validation. Uses the MCP v2
  `MCPServer` class (not `FastMCP`, which was renamed in MCP 2.x).
- `impress_uno.py` — `ImpressClient`, all UNO connection and document logic.
- `run.sh` — starts `server.py` with the bundled virtualenv.
- `requirements.txt` — Python dependencies (currently only `mcp`).
- `README.md` — user-facing overview.
- `INSTALL.md` — setup, configuration, and troubleshooting.

## Environment

The venv must be created with `--system-site-packages` so it can import the
system `uno` module:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

Do not add dependencies casually. Standard library, `mcp`, and `uno` cover the
current feature set.

## Commands

```bash
./run.sh                                  # run the MCP server (stdio)
.venv/bin/python -m py_compile server.py impress_uno.py
```

There is no automated test suite yet. For manual verification, launch a
throwaway headless instance on a non-default port and exercise
`ImpressClient` directly:

```python
import os
os.environ["IMPRESS_MCP_PORT"] = "2011"
from impress_uno import ImpressClient

client = ImpressClient()
client.launch(headless=True)
client.new_presentation()
client.add_slide(title="Test", body=["one", "two"])
client.save("/tmp/test.pptx", "pptx")
client.close()
```

Always use a dedicated port and profile for tests, and terminate the test
`soffice` process afterwards.

## Conventions

- Tool names are `impress_<verb>` and live in `server.py`.
- Tool wrappers call `_safe(...)` so errors reach the model as
  `{"ok": false, "error": "..."}` instead of crashing the server.
- Slide numbers in the public API are 1-based. Internally use 0-based indexes.
- Public distances are centimetres; UNO uses 1/100 mm, converted by `_cm`.
- Colours accept `#RRGGBB`, `[r, g, b]`, or common names.
- Output must remain JSON-serialisable. Never return raw UNO objects.
- Never print to stdout: the server uses stdio transport and stdout is the
  protocol channel.

## UNO quirks worth knowing

- `document.duplicate(page)` inserts the copy directly after the source page.
- DrawPages has no reorder or replace API. Reordering uses the
  `.uno:MovePageFirst/Up/Down/Last` dispatcher commands on the current page.
- `com.sun.star.presentation.OutlineTextShape` cannot be created and the
  default body placeholder does not report that service. Treat any non-title
  `TextShape` as the body placeholder when one is needed.
- Visible launches use a dedicated profile
  (`~/.cache/libreoffice-impress-mcp/profile`). A normal LibreOffice instance
  started without the UNO socket cannot be attached to.
- `ZOrder = 0` sends a shape behind the others; this is how slide backgrounds
  are drawn.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `IMPRESS_MCP_HOST` | `localhost` | UNO socket host |
| `IMPRESS_MCP_PORT` | `2002` | UNO socket port |
| `IMPRESS_MCP_PROFILE` | `~/.cache/libreoffice-impress-mcp/profile` | Dedicated LibreOffice profile |
| `IMPRESS_MCP_HEADLESS` | `0` | Set to `1` to launch without a window |
| `IMPRESS_MCP_AUTOLAUNCH` | `0` | Set to `1` to auto-launch from any tool call |

## Safety

The tools modify a live document. Do not delete slides, overwrite files, or
close a presentation unless the user asked for that action. Do not commit
secrets or machine-specific absolute paths that are not required.

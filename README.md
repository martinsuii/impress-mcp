# LibreOffice Impress MCP

An MCP server that drives a live LibreOffice Impress window over the UNO API.
It can create slides, add text/images/shapes, reorder slides, set speaker notes,
and export to PPTX, ODP, or PDF.

## Quick install

To install this, just tell your coding agent:

> Install this: https://github.com/martinsuii/impress-mcp/blob/master/INSTALL.md

## Requirements

- LibreOffice (`soffice`) installed
- Python UNO bindings available to the system Python (`import uno` must work)
- Python 3.10+

## Setup

Create a virtualenv with access to system packages so it can import `uno`:

```bash
cd ~/libreoffice-impress-mcp
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

The server speaks MCP over stdio.

## Configure your MCP client

The server is a standard stdio MCP server. Configure your client with:

- transport: `stdio`
- command: `$HOME/libreoffice-impress-mcp/run.sh`
- arguments: none

Many clients use a configuration shape like this:

```json
{
  "mcpServers": {
    "libreoffice-impress": {
      "command": "$HOME/libreoffice-impress-mcp/run.sh",
      "env": {
        "IMPRESS_MCP_PORT": "2002"
      }
    }
  }
}
```

Replace `$HOME` with an absolute path if your client does not expand
environment variables. If your client prefers an interpreter and a script:

```json
{
  "command": "$HOME/libreoffice-impress-mcp/.venv/bin/python",
  "args": ["$HOME/libreoffice-impress-mcp/server.py"]
}
```

See [INSTALL.md](INSTALL.md) for full setup and troubleshooting.

## Usage

1. `impress_launch` starts a visible LibreOffice with a dedicated profile and a
   UNO socket on port 2002. It will not disturb an already running LibreOffice.
2. `impress_new_presentation` or `impress_open` selects the presentation to edit.
3. Use the other `impress_*` tools. Slide numbers are 1-based, distances are in
   centimetres, and colours accept `#RRGGBB`, `[r, g, b]`, or names.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `IMPRESS_MCP_HOST` | `localhost` | UNO socket host |
| `IMPRESS_MCP_PORT` | `2002` | UNO socket port |
| `IMPRESS_MCP_PROFILE` | `~/.cache/libreoffice-impress-mcp/profile` | Dedicated LibreOffice profile |
| `IMPRESS_MCP_HEADLESS` | `0` | Set to `1` to launch without a window |
| `IMPRESS_MCP_AUTOLAUNCH` | `0` | Set to `1` to auto-launch from any tool call |

## Tools

| Tool | Purpose |
| --- | --- |
| `impress_status` | Connection state and open presentations |
| `impress_connect` / `impress_launch` | Attach to or start LibreOffice |
| `impress_open` / `impress_new_presentation` | Pick the document to edit |
| `impress_save` / `impress_export_pdf` / `impress_close` | Persist and close |
| `impress_get_info` / `impress_list_slides` / `impress_get_slide` | Inspect |
| `impress_add_slide` / `impress_set_slide_text` | Create and edit slides |
| `impress_add_text` / `impress_add_bullets` | Text content |
| `impress_add_image` / `impress_add_shape` | Visual content |
| `impress_set_slide_background` / `impress_set_slide_size` | Styling |
| `impress_set_notes` | Speaker notes |
| `impress_duplicate_slide` / `impress_move_slide` / `impress_delete_slide` | Arrange |

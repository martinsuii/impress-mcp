# LibreOffice Impress MCP

An MCP server that drives a live LibreOffice Impress window over the UNO API.
It can create slides, add text/images/shapes, reorder slides, set speaker notes,
and export to PPTX, ODP, or PDF.

## Requirements

- LibreOffice (`soffice`) installed
- `python3-uno` available to the system Python
- Python 3.10+

## Setup

The bundled `.venv` was created with system site packages so it can import
`uno`. To recreate it:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

The server speaks MCP over stdio.

## Add to opencode

```json
{
  "mcp": {
    "libreoffice-impress": {
      "type": "local",
      "command": ["/home/martin/libreoffice-impress-mcp/run.sh"],
      "environment": {
        "IMPRESS_MCP_PORT": "2002"
      },
      "enabled": true
    }
  }
}
```

## Usage

1. `impress_launch` starts a visible LibreOffice with a dedicated profile and a
   UNO socket on port 2002. It will not disturb an already running LibreOffice.
2. `impress_new_presentation` or `impress_open` selects the presentation to edit.
3. Use the other `impress_*` tools. Slide numbers are 1-based, distances are in
   centimetres, and colours accept `#RRGGBB`, `[r, g, b]`, or names.

Set `IMPRESS_MCP_HEADLESS=1` to launch without a window. Set
`IMPRESS_MCP_AUTOLAUNCH=1` to auto-start LibreOffice from any tool call. Other
environment variables: `IMPRESS_MCP_HOST`, `IMPRESS_MCP_PORT`,
`IMPRESS_MCP_PROFILE`.

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

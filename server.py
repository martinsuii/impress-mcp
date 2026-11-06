from __future__ import annotations

from typing import Any, Sequence

from mcp.server.mcpserver import MCPServer

from impress_uno import ImpressClient

client = ImpressClient()

server = MCPServer(
    "libreoffice-impress",
    title="LibreOffice Impress",
    instructions=(
        "Control a live LibreOffice Impress presentation over UNO. "
        "Call impress_launch first if LibreOffice is not running. "
        "Slide numbers are 1-based. Distances are in centimetres. "
        "Colours accept '#RRGGBB', RGB lists, or names such as 'red'."
    ),
)


def _safe(function: Any, **kwargs: Any) -> Any:
    try:
        return function(**kwargs)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@server.tool()
def impress_status() -> dict[str, Any]:
    """Show whether the MCP is connected to LibreOffice and list open presentations."""
    return _safe(client.status)


@server.tool()
def impress_connect(auto_launch: bool = False, headless: bool = False) -> dict[str, Any]:
    """Connect to a running LibreOffice instance.

    Set auto_launch to true to start LibreOffice automatically. headless=true
    starts it without a window (changes are not visible until you open the file).
    """
    return _safe(client.connect, auto_launch=auto_launch, headless=headless)


@server.tool()
def impress_launch(headless: bool = False) -> dict[str, Any]:
    """Start LibreOffice with the UNO control socket enabled.

    Starts a visible Impress window by default, using a dedicated profile so it
    does not disturb an already running LibreOffice.
    """
    return _safe(client.launch, headless=headless)


@server.tool()
def impress_open(path: str) -> dict[str, Any]:
    """Open an existing presentation file (.odp, .pptx, .ppt, .fodp)."""
    return _safe(client.open, path=path)


@server.tool()
def impress_new_presentation() -> dict[str, Any]:
    """Create a new, empty Impress presentation."""
    return _safe(client.new_presentation)


@server.tool()
def impress_save(path: str | None = None, format: str | None = None) -> dict[str, Any]:
    """Save the active presentation.

    format may be pptx, odp, otp or pdf and defaults to the path extension.
    If path is omitted the current document URL is used.
    """
    return _safe(client.save, path=path, format=format)


@server.tool()
def impress_export_pdf(path: str) -> dict[str, Any]:
    """Export the active presentation to PDF without changing the document."""
    return _safe(client.export_pdf, path=path)


@server.tool()
def impress_close(save: bool = False) -> dict[str, Any]:
    """Close the active presentation, optionally saving it first."""
    return _safe(client.close, save=save)


@server.tool()
def impress_get_info() -> dict[str, Any]:
    """Get the active presentation's file, slide count, and slide size."""
    return _safe(client.get_info)


@server.tool()
def impress_list_slides() -> list[dict[str, Any]] | dict[str, Any]:
    """List all slides with their names, shape counts, and text contents."""
    return _safe(client.list_slides)


@server.tool()
def impress_get_slide(slide: int) -> dict[str, Any]:
    """Get detailed shape information for one slide (1-based number)."""
    return _safe(client.get_slide, slide=slide)


@server.tool()
def impress_add_slide(
    title: str | None = None,
    body: str | Sequence[str] | None = None,
    background: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Append a new slide, optionally with a title, bullet body, and background colour."""
    return _safe(
        client.add_slide, title=title, body=body, background=background, name=name
    )


@server.tool()
def impress_set_slide_text(
    slide: int,
    title: str | None = None,
    body: str | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Replace the title and/or bullet text of an existing slide (1-based)."""
    return _safe(client.set_slide_text, slide=slide, title=title, body=body)


@server.tool()
def impress_add_text(
    slide: int,
    text: str,
    x: float = 1.5,
    y: float = 1.5,
    width: float | None = None,
    height: float | None = None,
    font_size: float = 24,
    bold: bool = False,
    color: str | None = None,
    align: str = "left",
    font_name: str | None = None,
) -> dict[str, Any]:
    """Add a text box to a slide. x, y, width and height are in centimetres."""
    return _safe(
        client.add_text,
        slide=slide,
        text=text,
        x=x,
        y=y,
        width=width,
        height=height,
        font_size=font_size,
        bold=bold,
        color=color,
        align=align,
        font_name=font_name,
    )


@server.tool()
def impress_add_bullets(
    slide: int,
    items: Sequence[str],
    x: float = 1.5,
    y: float = 3.5,
    width: float | None = None,
    height: float | None = None,
    font_size: float = 24,
    color: str | None = None,
    bullet: str = "•",
) -> dict[str, Any]:
    """Add a bullet list as a text box. Coordinates are in centimetres."""
    return _safe(
        client.add_bullets,
        slide=slide,
        items=items,
        x=x,
        y=y,
        width=width,
        height=height,
        font_size=font_size,
        color=color,
        bullet=bullet,
    )


@server.tool()
def impress_add_image(
    slide: int,
    path: str,
    x: float | None = None,
    y: float | None = None,
    width: float | None = None,
    height: float | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Add an image to a slide, centred and scaled to fit when no size is given."""
    return _safe(
        client.add_image,
        slide=slide,
        path=path,
        x=x,
        y=y,
        width=width,
        height=height,
        name=name,
    )


@server.tool()
def impress_add_shape(
    slide: int,
    kind: str,
    x: float,
    y: float,
    width: float,
    height: float,
    fill_color: str | None = None,
    line_color: str | None = None,
    line_width: float | None = None,
) -> dict[str, Any]:
    """Add a rectangle, ellipse, or line. Coordinates and sizes are in centimetres."""
    return _safe(
        client.add_shape,
        slide=slide,
        kind=kind,
        x=x,
        y=y,
        width=width,
        height=height,
        fill_color=fill_color,
        line_color=line_color,
        line_width=line_width,
    )


@server.tool()
def impress_set_slide_background(slide: int, color: str) -> dict[str, Any]:
    """Set a solid background colour for one slide."""
    return _safe(client.set_slide_background, slide=slide, color=color)


@server.tool()
def impress_set_slide_size(width_cm: float, height_cm: float) -> dict[str, Any]:
    """Set the page size of every slide in centimetres (e.g. 33.87 x 19.05 for 16:9)."""
    return _safe(client.set_slide_size, width_cm=width_cm, height_cm=height_cm)


@server.tool()
def impress_set_notes(slide: int, text: str) -> dict[str, Any]:
    """Set the speaker notes for a slide."""
    return _safe(client.set_notes, slide=slide, text=text)


@server.tool()
def impress_duplicate_slide(slide: int) -> dict[str, Any]:
    """Duplicate a slide and place the copy directly after it (1-based)."""
    return _safe(client.duplicate_slide, slide=slide)


@server.tool()
def impress_move_slide(slide: int, to: int) -> dict[str, Any]:
    """Move a slide to a new 1-based position."""
    return _safe(client.move_slide, slide=slide, to=to)


@server.tool()
def impress_delete_slide(slide: int) -> dict[str, Any]:
    """Delete a slide by its 1-based number."""
    return _safe(client.delete_slide, slide=slide)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

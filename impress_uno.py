from __future__ import annotations

import os
import shutil
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import uno
from com.sun.star.beans import PropertyValue

PRESENTATION_SERVICE = "com.sun.star.presentation.PresentationDocument"
TITLE_SERVICE = "com.sun.star.presentation.TitleTextShape"
OUTLINE_SERVICE = "com.sun.star.presentation.OutlineTextShape"

CM = 1000


class ImpressError(RuntimeError):
    pass


def _pv(name: str, value: Any) -> PropertyValue:
    prop = PropertyValue()
    prop.Name = name
    prop.Value = value
    return prop


def _enum(type_name: str, value: str) -> Any:
    return uno.Enum(type_name, value)


def _cm(value: float) -> int:
    return int(round(float(value) * CM))


def _color(value: Any) -> int:
    named = {
        "black": 0x000000,
        "white": 0xFFFFFF,
        "red": 0xFF0000,
        "green": 0x00A651,
        "blue": 0x0000FF,
        "yellow": 0xFFFF00,
        "orange": 0xFF8000,
        "purple": 0x800080,
        "grey": 0x808080,
        "gray": 0x808080,
    }
    if isinstance(value, int):
        return value & 0xFFFFFF
    if isinstance(value, (list, tuple)) and len(value) == 3:
        r, g, b = (int(v) for v in value)
        return (r & 0xFF) << 16 | (g & 0xFF) << 8 | (b & 0xFF)
    text = str(value).strip().lower()
    if text in named:
        return named[text]
    text = text.lstrip("#")
    if len(text) == 6:
        return int(text, 16)
    raise ImpressError(f"Invalid colour {value!r}; use #RRGGBB, a name, or [r, g, b].")


def image_dimensions(path: str | os.PathLike[str]) -> tuple[int, int] | None:
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"BM" and len(data) >= 26:
        return (
            abs(struct.unpack("<i", data[18:22])[0]),
            abs(struct.unpack("<i", data[22:26])[0]),
        )
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
                i += 2
                continue
            length = struct.unpack(">H", data[i + 2 : i + 4])[0]
            if marker in (
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            ):
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return width, height
            i += 2 + length
    return None


def _as_text(value: str | Iterable[str]) -> str:
    if isinstance(value, str):
        return value
    return "\n".join(str(item) for item in value)


def _supports(obj: Any, service: str) -> bool:
    try:
        return bool(obj.supportsService(service))
    except Exception:
        return False


def _shape_text(shape: Any) -> str | None:
    try:
        value = shape.String
    except Exception:
        return None
    return str(value)


class ImpressClient:
    def __init__(self) -> None:
        self.host = os.environ.get("IMPRESS_MCP_HOST", "localhost")
        self.port = int(os.environ.get("IMPRESS_MCP_PORT", "2002"))
        self.profile = Path(
            os.environ.get(
                "IMPRESS_MCP_PROFILE",
                str(Path.home() / ".cache" / "libreoffice-impress-mcp" / "profile"),
            )
        )
        self._headless = os.environ.get("IMPRESS_MCP_HEADLESS", "0") == "1"
        self._lock = threading.RLock()
        self._ctx: Any = None
        self._desktop: Any = None
        self._launched = False

    def _url(self) -> str:
        return (
            f"uno:socket,host={self.host},port={self.port};"
            "urp;StarOffice.ComponentContext"
        )

    def _alive(self) -> bool:
        if self._desktop is None:
            return False
        try:
            self._desktop.getComponents().createEnumeration()
            return True
        except Exception:
            self._desktop = None
            self._ctx = None
            return False

    def _attach(self) -> None:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local
        )
        ctx = resolver.resolve(self._url())
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx
        )
        desktop.getComponents().createEnumeration()
        self._ctx = ctx
        self._desktop = desktop

    def _wait_for_socket(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self._attach()
                return
            except Exception as exc:
                last = exc
                time.sleep(0.5)
        raise ImpressError(
            "LibreOffice did not open its control socket in time. "
            f"Last error: {last}"
        )

    def connect(
        self,
        auto_launch: bool = False,
        headless: bool | None = None,
        timeout: float = 45,
    ) -> dict[str, Any]:
        with self._lock:
            if self._alive():
                return self.status()
            try:
                self._attach()
            except Exception as exc:
                if not auto_launch:
                    raise ImpressError(
                        "Could not reach LibreOffice Impress. Start it with "
                        "impress_launch (or call impress_connect with "
                        "auto_launch=true). "
                        f"Socket: {self._url()} ({exc})"
                    ) from exc
                self.launch(
                    headless=self._headless if headless is None else headless,
                    timeout=timeout,
                )
            return self.status()

    def launch(
        self, headless: bool | None = None, timeout: float = 45
    ) -> dict[str, Any]:
        with self._lock:
            if self._alive():
                return self.status()
            soffice = shutil.which("soffice") or shutil.which("libreoffice")
            if not soffice:
                raise ImpressError(
                    "LibreOffice is not installed or 'soffice' is not on PATH."
                )
            self.profile.mkdir(parents=True, exist_ok=True)
            command = [
                soffice,
                f"-env:UserInstallation={uno.systemPathToFileUrl(str(self.profile))}",
                (
                    f"--accept=socket,host={self.host},port={self.port};"
                    "urp;StarOffice.ComponentContext"
                ),
                "--norestore",
                "--nofirststartwizard",
            ]
            if self._headless if headless is None else headless:
                command.append("--headless")
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            self._launched = True
            self._wait_for_socket(timeout)
            return self.status()

    def _ensure(self) -> None:
        if self._alive():
            return
        try:
            self._attach()
        except Exception as exc:
            if os.environ.get("IMPRESS_MCP_AUTOLAUNCH", "0") == "1":
                self.launch()
                return
            raise ImpressError(
                "Not connected to LibreOffice. Run impress_launch to start "
                "Impress, or impress_connect(auto_launch=true). "
                f"Socket: {self._url()} ({exc})"
            ) from exc

    def _is_impress(self, component: Any) -> bool:
        return component is not None and _supports(component, PRESENTATION_SERVICE)

    def _find_document(self) -> Any | None:
        try:
            current = self._desktop.getCurrentComponent()
        except Exception:
            current = None
        if self._is_impress(current):
            return current
        try:
            components = self._desktop.getComponents().createEnumeration()
            while components.hasMoreElements():
                component = components.nextElement()
                if self._is_impress(component):
                    return component
        except Exception as exc:
            raise ImpressError(f"Could not inspect open documents: {exc}") from exc
        return None

    def _document(self, create: bool = False) -> Any:
        self._ensure()
        document = self._find_document()
        if document is None:
            if create:
                return self._load_factory()
            raise ImpressError(
                "No Impress presentation is open. Use impress_new_presentation "
                "or impress_open first."
            )
        return document

    def _load_factory(self) -> Any:
        return self._desktop.loadComponentFromURL(
            "private:factory/simpress", "_blank", 0, ()
        )

    def _pages(self, document: Any) -> Any:
        return document.getDrawPages()

    def _page(self, document: Any, slide: int) -> Any:
        pages = self._pages(document)
        count = pages.getCount()
        if not isinstance(slide, int) or slide < 1 or slide > count:
            raise ImpressError(
                f"Slide number must be between 1 and {count} (got {slide})."
            )
        return pages.getByIndex(slide - 1)

    def _set_position(self, shape: Any, x: float, y: float) -> None:
        position = uno.createUnoStruct("com.sun.star.awt.Point")
        position.X = _cm(x)
        position.Y = _cm(y)
        shape.Position = position

    def _set_size(self, shape: Any, width: float, height: float) -> None:
        size = uno.createUnoStruct("com.sun.star.awt.Size")
        size.Width = _cm(width)
        size.Height = _cm(height)
        shape.Size = size

    def _shape_kind(self, shape: Any) -> str:
        if _supports(shape, TITLE_SERVICE):
            return "title"
        if _supports(shape, OUTLINE_SERVICE):
            return "outline"
        if _supports(shape, "com.sun.star.drawing.GraphicObjectShape"):
            return "image"
        if _supports(shape, "com.sun.star.drawing.RectangleShape"):
            return "rectangle"
        if _supports(shape, "com.sun.star.drawing.EllipseShape"):
            return "ellipse"
        if _supports(shape, "com.sun.star.drawing.LineShape"):
            return "line"
        if _supports(shape, "com.sun.star.drawing.TextShape"):
            return "text"
        return "shape"

    def _shape_info(self, shape: Any) -> dict[str, Any]:
        info: dict[str, Any] = {"type": self._shape_kind(shape)}
        text = _shape_text(shape)
        if text:
            info["text"] = text
        try:
            position = shape.Position
            size = shape.Size
            info["x_cm"] = round(position.X / CM, 2)
            info["y_cm"] = round(position.Y / CM, 2)
            info["width_cm"] = round(size.Width / CM, 2)
            info["height_cm"] = round(size.Height / CM, 2)
        except Exception:
            pass
        return info

    def _slide_info(self, document: Any, index: int) -> dict[str, Any]:
        page = self._pages(document).getByIndex(index)
        shapes = [
            self._shape_info(page.getByIndex(i)) for i in range(page.getCount())
        ]
        return {
            "slide": index + 1,
            "name": str(getattr(page, "Name", "")),
            "width_cm": round(page.Width / CM, 2),
            "height_cm": round(page.Height / CM, 2),
            "shape_count": len(shapes),
            "shapes": shapes,
        }

    def _document_info(self, document: Any) -> dict[str, Any]:
        pages = self._pages(document)
        url = ""
        try:
            url = str(document.getURL())
        except Exception:
            pass
        return {
            "document": url or "Untitled",
            "slide_count": pages.getCount(),
            "width_cm": round(pages.getByIndex(0).Width / CM, 2),
            "height_cm": round(pages.getByIndex(0).Height / CM, 2),
        }

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "connected": False,
            "socket": self._url(),
            "launched_by_mcp": self._launched,
        }
        if not self._alive():
            return result
        result["connected"] = True
        documents = []
        try:
            enumeration = self._desktop.getComponents().createEnumeration()
            while enumeration.hasMoreElements():
                component = enumeration.nextElement()
                if self._is_impress(component):
                    documents.append(self._document_info(component))
        except Exception as exc:
            result["error"] = str(exc)
        result["presentations"] = documents
        return result

    def new_presentation(self) -> dict[str, Any]:
        self._ensure()
        return self._document_info(self._load_factory())

    def open(self, path: str) -> dict[str, Any]:
        self._ensure()
        target = Path(path).expanduser().resolve()
        if not target.is_file():
            raise ImpressError(f"File not found: {target}")
        document = self._desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(str(target)), "_blank", 0, ()
        )
        if not self._is_impress(document):
            raise ImpressError(f"Opened document is not a presentation: {target}")
        return self._document_info(document)

    def get_info(self) -> dict[str, Any]:
        return self._document_info(self._document())

    def list_slides(self) -> list[dict[str, Any]]:
        document = self._document()
        pages = self._pages(document)
        slides = []
        for i in range(pages.getCount()):
            page = pages.getByIndex(i)
            slides.append(
                {
                    "slide": i + 1,
                    "name": str(getattr(page, "Name", "")),
                    "shape_count": page.getCount(),
                    "texts": [
                        text
                        for text in (
                            _shape_text(page.getByIndex(j))
                            for j in range(page.getCount())
                        )
                        if text
                    ],
                }
            )
        return slides

    def get_slide(self, slide: int) -> dict[str, Any]:
        document = self._document()
        return self._slide_info(document, self._page_index(document, slide))

    def _page_index(self, document: Any, slide: int) -> int:
        self._page(document, slide)
        return slide - 1

    def _find_placeholder(self, page: Any, service: str) -> Any | None:
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            if _supports(shape, service):
                return shape
        return None

    def _find_body_shape(self, page: Any) -> Any | None:
        for i in range(page.getCount()):
            shape = page.getByIndex(i)
            if _supports(shape, TITLE_SERVICE):
                continue
            if _supports(shape, "com.sun.star.drawing.TextShape"):
                return shape
        return None

    def _add_text_shape(
        self,
        document: Any,
        page: Any,
        text: str,
        x: float,
        y: float,
        width: float,
        height: float,
        font_size: float = 24,
        bold: bool = False,
        color: Any = None,
        align: str = "left",
        font_name: str | None = None,
    ) -> Any:
        shape = document.createInstance("com.sun.star.drawing.TextShape")
        page.add(shape)
        self._set_position(shape, x, y)
        self._set_size(shape, width, height)
        shape.String = text
        shape.CharHeight = float(font_size)
        shape.CharWeight = 150.0 if bold else 100.0
        align_map = {
            "left": "LEFT",
            "center": "CENTER",
            "centre": "CENTER",
            "right": "RIGHT",
            "justify": "BLOCK",
            "block": "BLOCK",
        }
        shape.ParaAdjust = _enum(
            "com.sun.star.style.ParagraphAdjust",
            align_map.get(align.lower(), "LEFT"),
        )
        if color is not None:
            shape.CharColor = _color(color)
        if font_name:
            shape.CharFontName = font_name
        try:
            shape.TextAutoGrowHeight = True
        except Exception:
            pass
        return shape

    def add_slide(
        self,
        title: str | None = None,
        body: str | Sequence[str] | None = None,
        background: Any = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        document = self._document()
        pages = self._pages(document)
        pages.insertNewByIndex(pages.getCount())
        page = pages.getByIndex(pages.getCount() - 1)
        if name:
            page.Name = name
        width = page.Width / CM
        height = page.Height / CM
        if background is not None:
            self._paint_background(document, page, background)
        if title is not None:
            shape = document.createInstance(TITLE_SERVICE)
            page.add(shape)
            self._set_position(shape, 1.5, 0.8)
            self._set_size(shape, width - 3.0, 2.6)
            shape.String = str(title)
            shape.CharHeight = 40.0
            shape.CharWeight = 150.0
        if body is not None:
            lines = [body] if isinstance(body, str) else list(body)
            text = "\n".join(f"•  {line}" for line in lines)
            self._add_text_shape(
                document,
                page,
                text,
                1.5,
                4.0,
                width - 3.0,
                height - 5.0,
                font_size=24,
            )
        return self._slide_info(document, pages.getCount() - 1)

    def set_slide_text(
        self, slide: int, title: str | None = None, body: str | Sequence[str] | None = None
    ) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        width = page.Width / CM
        height = page.Height / CM
        if title is not None:
            title_shape = self._find_placeholder(page, TITLE_SERVICE)
            if title_shape is not None:
                title_shape.String = str(title)
            else:
                self._add_text_shape(
                    document,
                    page,
                    str(title),
                    1.5,
                    0.8,
                    width - 3.0,
                    2.6,
                    font_size=40,
                    bold=True,
                )
        if body is not None:
            body_shape = self._find_placeholder(page, OUTLINE_SERVICE)
            if body_shape is None:
                body_shape = self._find_body_shape(page)
            if body_shape is not None:
                if isinstance(body, str):
                    body_shape.String = body
                else:
                    body_shape.String = "\n".join(f"•  {line}" for line in body)
            else:
                lines = [body] if isinstance(body, str) else list(body)
                self._add_text_shape(
                    document,
                    page,
                    "\n".join(f"•  {line}" for line in lines),
                    1.5,
                    4.0,
                    width - 3.0,
                    height - 5.0,
                    font_size=24,
                )
        return self._slide_info(document, slide - 1)

    def add_text(
        self,
        slide: int,
        text: str,
        x: float = 1.5,
        y: float = 1.5,
        width: float | None = None,
        height: float | None = None,
        font_size: float = 24,
        bold: bool = False,
        color: Any = None,
        align: str = "left",
        font_name: str | None = None,
    ) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        page_width = page.Width / CM
        page_height = page.Height / CM
        shape = self._add_text_shape(
            document,
            page,
            text,
            x,
            y,
            page_width - x - 1.5 if width is None else width,
            page_height - y - 1.5 if height is None else height,
            font_size=font_size,
            bold=bold,
            color=color,
            align=align,
            font_name=font_name,
        )
        return self._shape_info(shape)

    def add_bullets(
        self,
        slide: int,
        items: Sequence[str],
        x: float = 1.5,
        y: float = 3.5,
        width: float | None = None,
        height: float | None = None,
        font_size: float = 24,
        color: Any = None,
        bullet: str = "•",
    ) -> dict[str, Any]:
        if not items:
            raise ImpressError("items must contain at least one bullet.")
        text = "\n".join(f"{bullet}  {item}" for item in items)
        return self.add_text(
            slide,
            text,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
            color=color,
        )

    def add_image(
        self,
        slide: int,
        path: str,
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        target = Path(path).expanduser().resolve()
        if not target.is_file():
            raise ImpressError(f"Image not found: {target}")
        page_width = page.Width / CM
        page_height = page.Height / CM
        natural = image_dimensions(target)
        if natural:
            natural_width, natural_height = natural
            if width is None and height is None:
                max_width = page_width - 3.0
                max_height = page_height - 3.0
                scale = min(max_width / natural_width, max_height / natural_height, 1.0)
                width = natural_width * scale
                height = natural_height * scale
            elif width is None:
                width = float(height) * natural_width / natural_height
            elif height is None:
                height = float(width) * natural_height / natural_width
        if width is None:
            width = page_width - 3.0
        if height is None:
            height = page_height - 3.0
        if x is None:
            x = (page_width - width) / 2
        if y is None:
            y = (page_height - height) / 2
        shape = document.createInstance("com.sun.star.drawing.GraphicObjectShape")
        page.add(shape)
        shape.GraphicURL = uno.systemPathToFileUrl(str(target))
        try:
            provider = self._ctx.ServiceManager.createInstanceWithContext(
                "com.sun.star.graphic.GraphicProvider", self._ctx
            )
            graphic = provider.queryGraphic((_pv("URL", uno.systemPathToFileUrl(str(target))),))
            if graphic is not None:
                shape.Graphic = graphic
        except Exception:
            pass
        self._set_position(shape, x, y)
        self._set_size(shape, width, height)
        if name:
            try:
                shape.Name = name
            except Exception:
                pass
        return self._shape_info(shape)

    def add_shape(
        self,
        slide: int,
        kind: str,
        x: float,
        y: float,
        width: float,
        height: float,
        fill_color: Any = None,
        line_color: Any = None,
        line_width: float | None = None,
    ) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        aliases = {
            "rect": "com.sun.star.drawing.RectangleShape",
            "rectangle": "com.sun.star.drawing.RectangleShape",
            "box": "com.sun.star.drawing.RectangleShape",
            "ellipse": "com.sun.star.drawing.EllipseShape",
            "oval": "com.sun.star.drawing.EllipseShape",
            "circle": "com.sun.star.drawing.EllipseShape",
            "line": "com.sun.star.drawing.LineShape",
        }
        service = aliases.get(kind.lower())
        if service is None:
            raise ImpressError(
                "Unsupported shape. Use rectangle, ellipse, or line."
            )
        shape = document.createInstance(service)
        page.add(shape)
        self._set_position(shape, x, y)
        self._set_size(shape, width, height)
        if service == "com.sun.star.drawing.LineShape":
            fill_color = None
        if fill_color is None or (
            isinstance(fill_color, str)
            and fill_color.lower() in ("none", "transparent")
        ):
            try:
                shape.FillStyle = _enum("com.sun.star.drawing.FillStyle", "NONE")
            except Exception:
                pass
        else:
            shape.FillStyle = _enum("com.sun.star.drawing.FillStyle", "SOLID")
            shape.FillColor = _color(fill_color)
        if line_color is None or (
            isinstance(line_color, str)
            and line_color.lower() in ("none", "transparent")
        ):
            shape.LineStyle = _enum("com.sun.star.drawing.LineStyle", "NONE")
        else:
            shape.LineStyle = _enum("com.sun.star.drawing.LineStyle", "SOLID")
            shape.LineColor = _color(line_color)
            if line_width is not None:
                shape.LineWidth = _cm(line_width)
        return self._shape_info(shape)

    def _paint_background(self, document: Any, page: Any, color: Any) -> None:
        shape = document.createInstance("com.sun.star.drawing.RectangleShape")
        page.add(shape)
        self._set_position(shape, 0, 0)
        self._set_size(shape, page.Width / CM, page.Height / CM)
        shape.FillStyle = _enum("com.sun.star.drawing.FillStyle", "SOLID")
        shape.FillColor = _color(color)
        shape.LineStyle = _enum("com.sun.star.drawing.LineStyle", "NONE")
        try:
            shape.ZOrder = 0
        except Exception:
            pass

    def set_slide_background(self, slide: int, color: Any) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        self._paint_background(document, page, color)
        return self._slide_info(document, slide - 1)

    def set_slide_size(self, width_cm: float, height_cm: float) -> dict[str, Any]:
        if width_cm <= 0 or height_cm <= 0:
            raise ImpressError("Slide width and height must be positive.")
        document = self._document()
        pages = self._pages(document)
        for i in range(pages.getCount()):
            page = pages.getByIndex(i)
            page.Width = _cm(width_cm)
            page.Height = _cm(height_cm)
        return {
            "width_cm": round(width_cm, 2),
            "height_cm": round(height_cm, 2),
            "slide_count": pages.getCount(),
        }

    def set_notes(self, slide: int, text: str) -> dict[str, Any]:
        document = self._document()
        page = self._page(document, slide)
        notes = page.getNotesPage()
        if notes is None:
            raise ImpressError("This slide has no notes page.")
        shape = document.createInstance("com.sun.star.drawing.TextShape")
        notes.add(shape)
        self._set_position(shape, 1.5, 1.5)
        self._set_size(shape, notes.Width / CM - 3.0, notes.Height / CM - 3.0)
        shape.String = text
        shape.CharHeight = 14.0
        return {"slide": slide, "notes": text}

    def _dispatch(self, document: Any, command: str) -> None:
        if self._ctx is None:
            raise ImpressError("Not connected to LibreOffice.")
        controller = document.getCurrentController()
        frame = controller.getFrame()
        helper = self._ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", self._ctx
        )
        helper.executeDispatch(frame, f".uno:{command}", "", 0, ())

    def duplicate_slide(self, slide: int) -> dict[str, Any]:
        document = self._document()
        pages = self._pages(document)
        if pages.getCount() < 1:
            raise ImpressError("There are no slides to duplicate.")
        source = self._page(document, slide)
        document.duplicate(source)
        return self._slide_info(document, slide)

    def move_slide(self, slide: int, to: int) -> dict[str, Any]:
        document = self._document()
        pages = self._pages(document)
        count = pages.getCount()
        self._page(document, slide)
        if not isinstance(to, int) or to < 1 or to > count:
            raise ImpressError(f"Target position must be between 1 and {count}.")
        if slide == to:
            return self._slide_info(document, slide - 1)
        page = pages.getByIndex(slide - 1)
        controller = document.getCurrentController()
        controller.setCurrentPage(page)
        if to == 1:
            self._dispatch(document, "MovePageFirst")
        elif to == count:
            self._dispatch(document, "MovePageLast")
        elif to < slide:
            for _ in range(slide - to):
                self._dispatch(document, "MovePageUp")
        else:
            for _ in range(to - slide):
                self._dispatch(document, "MovePageDown")
        return self._slide_info(document, to - 1)

    def delete_slide(self, slide: int) -> dict[str, Any]:
        document = self._document()
        pages = self._pages(document)
        if pages.getCount() <= 1:
            raise ImpressError("Cannot delete the only slide in the presentation.")
        page = self._page(document, slide)
        pages.remove(page)
        return {"deleted_slide": slide, "slide_count": pages.getCount()}

    def save(self, path: str | None = None, format: str | None = None) -> dict[str, Any]:
        document = self._document()
        filters = {
            "pptx": "Impress MS PowerPoint 2007 XML",
            "odp": "impress8",
            "otp": "impress8",
            "pdf": "impress_pdf_Export",
        }
        if format is None:
            if path:
                suffix = Path(path).suffix.lower().lstrip(".")
                format = suffix if suffix in filters else "pptx"
            else:
                format = "pptx"
        format = format.lower().lstrip(".")
        filter_name = filters.get(format)
        if filter_name is None:
            raise ImpressError(
                "Unsupported format. Use pptx, odp, otp, or pdf "
                "(or impress_export_pdf)."
            )
        if path is None:
            try:
                url = document.getURL()
            except Exception:
                url = ""
            if not url:
                raise ImpressError(
                    "This presentation has not been saved yet; provide a path."
                )
            target = Path(uno.fileUrlToSystemPath(url))
        else:
            target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        args = (
            _pv("FilterName", filter_name),
            _pv("Overwrite", True),
        )
        url = uno.systemPathToFileUrl(str(target))
        document.storeAsURL(url, args)
        return {"saved": str(target), "format": format}

    def export_pdf(self, path: str) -> dict[str, Any]:
        document = self._document()
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        document.storeToURL(
            uno.systemPathToFileUrl(str(target)),
            (
                _pv("FilterName", "impress_pdf_Export"),
                _pv("Overwrite", True),
            ),
        )
        return {"exported": str(target), "format": "pdf"}

    def close(self, save: bool = False) -> dict[str, Any]:
        document = self._document()
        if save:
            try:
                url = document.getURL()
            except Exception:
                url = ""
            if not url:
                raise ImpressError(
                    "Cannot save an untitled presentation on close; "
                    "call impress_save with a path first."
                )
            document.store()
        document.close(True)
        return {"closed": True, "saved": bool(save)}

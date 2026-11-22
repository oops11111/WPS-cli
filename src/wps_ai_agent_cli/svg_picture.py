"""Native SVG pictures in a presentation.

PowerPoint renders an SVG picture from the ``svgBlip`` extension on the picture's
``<a:blip>``; renderers that do not understand it show the raster fallback instead,
so an SVG picture is always paired with one. python-pptx has no SVG path (its
``Image`` goes through PIL, which cannot read SVG, and ``image_content_types``
has no ``svg`` entry), so the SVG part is added by hand here.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

SVG_BLIP_EXTENSION_URI = "{96DAC541-7B7A-43D3-8B79-0ABCA5BDA020}"
SVG_CONTENT_TYPE = "image/svg+xml"
SVG_NAMESPACE = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"


def add_svg_picture(slide, svg: bytes | str | Path | BinaryIO, fallback, left, top, width, height):
    """Add a picture that renders as vector SVG where supported, else the raster fallback.

    ``svg`` is the SVG markup (bytes, text, a path, or a readable file object);
    ``fallback`` is the raster image python-pptx can read (a path or a file object).
    Returns the created picture shape.
    """
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from pptx.oxml import parse_xml
    from pptx.oxml.ns import qn
    from pptx.parts.image import ImagePart

    if isinstance(svg, (str, Path)):
        svg_bytes = Path(svg).read_bytes() if isinstance(svg, Path) else svg.encode("utf-8")
    elif isinstance(svg, bytes):
        svg_bytes = svg
    else:
        svg_bytes = svg.read()

    picture = slide.shapes.add_picture(fallback, left, top, width, height)
    package = slide.part.package
    svg_part = ImagePart(package.next_image_partname("svg"), SVG_CONTENT_TYPE, package, svg_bytes)
    rId_svg = slide.part.relate_to(svg_part, RT.IMAGE)
    blip = picture._element.find(".//" + qn("a:blip"))
    ext_xml = (
        '<a:extLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
        f' xmlns:asvg="{SVG_NAMESPACE}">'
        f'<a:ext uri="{SVG_BLIP_EXTENSION_URI}"><asvg:svgBlip r:embed="{rId_svg}"/></a:ext>'
        "</a:extLst>"
    )
    blip.append(parse_xml(ext_xml))
    return picture


def svg_fallback_bytes(png: bytes) -> BytesIO:
    """Wrap raster fallback bytes as the file object ``add_picture`` takes."""
    return BytesIO(png)

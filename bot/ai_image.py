"""Small, self-contained AI image generation for the Discord chatbot.

Groq provides the prompt understanding but not an image-generation endpoint.
The chat model therefore produces a constrained SVG illustration, which is
sanitized and rasterized locally to a PNG before it is sent to Discord.
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any

SVG_NS = "http://www.w3.org/2000/svg"
SVG_MAX_BYTES = 32_000
PNG_MAX_BYTES = 4 * 1024 * 1024
CANVAS_SIZE = 768

_IMAGE_ACTIONS = re.compile(
    r"\b(?:draw|paint|sketch|illustrate|create|generate|make|design|"
    r"iguhit|gumuhit|gumawa|lukis|buat|zeichne|erstelle)\b",
    re.IGNORECASE,
)
_DIRECT_DRAW_ACTIONS = re.compile(
    r"\b(?:draw|paint|sketch|illustrate|iguhit|gumuhit|lukis)\b",
    re.IGNORECASE,
)
_IMAGE_SUBJECTS = re.compile(
    r"\b(?:image|picture|pic|illustration|drawing|artwork|art|photo|"
    r"painting|logo|icon|avatar|wallpaper|sticker|poster|portrait|landscape|"
    r"meme|vector|bild|gambar|larawan)\b",
    re.IGNORECASE,
)
_SVG_BLOCK = re.compile(r"<svg\b[^>]*>.*?</svg\s*>", re.IGNORECASE | re.DOTALL)
_NUMBER_TEXT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_NUMBER = re.compile(_NUMBER_TEXT)
_NUMBER_OR_PERCENT = re.compile(_NUMBER_TEXT + r"%?")
_SAFE_COLOR_NAMES = {
    "black", "white", "red", "green", "blue", "yellow", "orange", "purple",
    "pink", "gray", "grey", "cyan", "magenta", "teal", "navy", "gold",
    "coral", "brown", "indigo", "violet", "lime", "transparent", "none",
}
_SAFE_ELEMENTS = {
    "svg", "g", "defs", "linearGradient", "radialGradient", "stop",
    "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
}
_ATTRS_BY_ELEMENT = {
    "svg": {"viewBox", "width", "height", "preserveAspectRatio"},
    "g": {
        "transform", "opacity", "fill", "stroke", "stroke-width",
        "stroke-linecap", "stroke-linejoin", "fill-rule",
    },
    "defs": set(),
    "linearGradient": {
        "id", "x1", "y1", "x2", "y2", "gradientUnits",
        "gradientTransform", "spreadMethod",
    },
    "radialGradient": {
        "id", "cx", "cy", "r", "fx", "fy", "fr", "gradientUnits",
        "gradientTransform", "spreadMethod",
    },
    "stop": {"offset", "stop-color", "stop-opacity"},
    "path": {
        "d", "fill", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset",
        "fill-rule", "opacity", "fill-opacity", "stroke-opacity", "transform",
    },
    "rect": {
        "x", "y", "width", "height", "rx", "ry", "fill", "stroke",
        "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity",
        "fill-opacity", "stroke-opacity", "transform",
    },
    "circle": {
        "cx", "cy", "r", "fill", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform",
    },
    "ellipse": {
        "cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width",
        "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity",
        "stroke-opacity", "transform",
    },
    "line": {
        "x1", "y1", "x2", "y2", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "opacity", "stroke-opacity", "transform",
    },
    "polyline": {
        "points", "fill", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform",
    },
    "polygon": {
        "points", "fill", "stroke", "stroke-width", "stroke-linecap",
        "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform",
    },
}
_NUMERIC_ATTRIBUTES = {
    "x", "y", "cx", "cy", "r", "rx", "ry", "x1", "y1", "x2", "y2",
    "width", "height", "stroke-width", "stroke-dashoffset", "fr",
}


def is_image_generation_request(message: str) -> bool:
    """Detect direct drawing requests without hijacking explanatory questions."""
    message = message.strip()
    if not message:
        return False
    if re.match(
        r"^(?:how|what|why|when|where|who|explain|teach me|tell me how)\b",
        message,
        re.IGNORECASE,
    ):
        return False
    if not _IMAGE_ACTIONS.search(message):
        return False
    return bool(_DIRECT_DRAW_ACTIONS.search(message) or _IMAGE_SUBJECTS.search(message))


def _local_name(tag: str) -> str:
    if tag.startswith(f"{{{SVG_NS}}}"):
        return tag[len(SVG_NS) + 2 :]
    if "}" in tag or ":" in tag:
        raise ValueError("SVG namespaces other than SVG are not allowed")
    return tag


def _is_number_list(value: str, *, allow_percent: bool = False) -> bool:
    if not value or not re.fullmatch(
        rf"\s*{_NUMBER_TEXT}%?(?:[\s,]+{_NUMBER_TEXT}%?)*\s*", value
    ):
        return False
    if not allow_percent and "%" in value:
        return False
    return all(
        abs(float(number.rstrip("%"))) <= 20_000
        for number in _NUMBER_OR_PERCENT.findall(value)
    )


def _is_transform(value: str) -> bool:
    expression = re.compile(
        r"(?:translate|scale|rotate)\s*\(\s*[-+0-9.eE,\s]+\s*\)"
    )
    parts = expression.findall(value)
    return bool(parts) and not expression.sub("", value).strip()


def _is_color(value: str, ids: set[str]) -> bool:
    if value.lower() in _SAFE_COLOR_NAMES or re.fullmatch(
        r"#[0-9a-fA-F]{3,8}", value
    ):
        return True
    rgb = re.fullmatch(
        r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)",
        value,
        re.IGNORECASE,
    )
    if rgb:
        return all(int(channel) <= 255 for channel in rgb.groups())
    reference = re.fullmatch(r"url\(#([A-Za-z_][A-Za-z0-9_.-]{0,63})\)", value)
    return bool(reference and reference.group(1) in ids)


def sanitize_svg(model_output: str) -> str:
    """Extract and validate a small SVG subset, rejecting active or remote content."""
    if len(model_output.encode("utf-8")) > SVG_MAX_BYTES:
        raise ValueError("Generated SVG is too large")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", model_output, re.IGNORECASE):
        raise ValueError("SVG declarations and entities are not allowed")
    match = _SVG_BLOCK.search(model_output)
    if not match:
        raise ValueError("The model did not return an SVG image")

    root = ET.fromstring(match.group(0))
    if _local_name(root.tag) != "svg":
        raise ValueError("Generated document is not an SVG")

    # Ignore model-provided raster dimensions; the renderer always uses a
    # fixed-size canvas, preventing oversized or unit-based SVG dimensions.
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)

    ET.register_namespace("", SVG_NS)
    elements = list(root.iter())
    if len(elements) > 500:
        raise ValueError("Generated SVG contains too many elements")

    ids: set[str] = set()
    for element in elements:
        tag = _local_name(element.tag)
        if tag not in _SAFE_ELEMENTS:
            raise ValueError(f"SVG element {tag!r} is not allowed")
        element.tag = f"{{{SVG_NS}}}{tag}"
        for key in element.attrib:
            if key == "id":
                value = element.attrib[key]
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", value):
                    raise ValueError("SVG contains an invalid element id")
                if value in ids:
                    raise ValueError("SVG contains duplicate element ids")
                ids.add(value)

    for element in elements:
        tag = _local_name(element.tag)
        if set(element.attrib) - _ATTRS_BY_ELEMENT[tag]:
            raise ValueError(f"SVG {tag} contains an unsupported attribute")
        if element.text and element.text.strip():
            raise ValueError("Text content is not allowed in generated SVG")
        if element.tail and element.tail.strip():
            raise ValueError("Text outside SVG elements is not allowed")

        for name, value in element.attrib.items():
            if name == "id":
                continue
            if name == "d":
                if len(value) > 16_000 or not re.fullmatch(
                    r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]+", value
                ):
                    raise ValueError("SVG path data is invalid or too large")
            elif name == "points":
                if not _is_number_list(value):
                    raise ValueError("SVG point data is invalid")
            elif name in {"transform", "gradientTransform"}:
                if not _is_transform(value):
                    raise ValueError("SVG transform is invalid")
            elif name in {"fill", "stroke", "stop-color"}:
                if not _is_color(value, ids):
                    raise ValueError("SVG contains an unsupported color")
            elif name in {"opacity", "fill-opacity", "stroke-opacity", "stop-opacity"}:
                try:
                    if not 0 <= float(value) <= 1:
                        raise ValueError("SVG opacity must be between 0 and 1")
                except ValueError as exc:
                    raise ValueError("SVG opacity is invalid") from exc
            elif name == "offset":
                if not _is_number_list(value, allow_percent=True):
                    raise ValueError("SVG gradient offset is invalid")
            elif name in _NUMERIC_ATTRIBUTES or name in {
                "x1", "y1", "x2", "y2", "fx", "fy",
            }:
                if not _is_number_list(value, allow_percent=True):
                    raise ValueError(f"SVG {name} is invalid")
            elif name == "stroke-dasharray":
                if value != "none" and not _is_number_list(value):
                    raise ValueError("SVG stroke dash array is invalid")
            elif name == "stroke-linecap" and value not in {"butt", "round", "square"}:
                raise ValueError("SVG stroke line cap is invalid")
            elif name == "stroke-linejoin" and value not in {"miter", "round", "bevel"}:
                raise ValueError("SVG stroke line join is invalid")
            elif name == "fill-rule" and value not in {"nonzero", "evenodd"}:
                raise ValueError("SVG fill rule is invalid")
            elif name == "gradientUnits" and value not in {
                "userSpaceOnUse", "objectBoundingBox",
            }:
                raise ValueError("SVG gradient units are invalid")
            elif name == "spreadMethod" and value not in {"pad", "reflect", "repeat"}:
                raise ValueError("SVG spread method is invalid")
            elif name == "preserveAspectRatio" and value not in {
                "none", "xMidYMid meet", "xMidYMid slice",
            }:
                raise ValueError("SVG aspect ratio is invalid")

    view_box = root.get("viewBox")
    if view_box is not None:
        if not _is_number_list(view_box) or len(
            _NUMBER.findall(view_box)
        ) != 4:
            raise ValueError("SVG viewBox must contain four numbers")
        _, _, width, height = map(float, _NUMBER.findall(view_box))
        if width <= 0 or height <= 0:
            raise ValueError("SVG viewBox dimensions must be positive")
    else:
        view_box = f"0 0 {CANVAS_SIZE} {CANVAS_SIZE}"

    root.set("width", str(CANVAS_SIZE))
    root.set("height", str(CANVAS_SIZE))
    root.set("viewBox", view_box)
    return ET.tostring(root, encoding="unicode")


def render_svg_png(svg: str) -> bytes:
    """Rasterize a sanitized SVG through ImageMagick with bounded output."""
    result = subprocess.run(
        [
            "magick", "-limit", "memory", "128MiB", "-limit", "map", "256MiB",
            "-density", "96", "svg:-", "-resize",
            f"{CANVAS_SIZE}x{CANVAS_SIZE}", "-strip", "png:-",
        ],
        input=svg.encode("utf-8"),
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("ImageMagick could not render the generated image")
    if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ImageMagick did not return a valid PNG")
    if len(result.stdout) > PNG_MAX_BYTES:
        raise RuntimeError("Generated PNG is too large to upload")
    return result.stdout


def generate_image_png(client: Any, model: str, prompt: str) -> bytes:
    """Ask the configured text model for an illustration and return a PNG."""
    system_message = (
        "You are an SVG illustration generator. Return exactly one complete SVG document "
        "and nothing else: no intro, explanation, or Markdown. The root must use "
        'xmlns="http://www.w3.org/2000/svg" and viewBox="0 0 768 768". '
        "Allowed elements only: svg, g, defs, linearGradient, radialGradient, stop, path, "
        "rect, circle, ellipse, line, polyline, polygon. Use only geometry, fills, strokes, "
        "opacity, transforms, and gradients. Never use text, style, script, filters, image, "
        "href, mask, foreignObject, or external resources. Make the user's subject into a "
        "clear, polished, colorful illustration."
    )
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(2):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=3000,
        )
        model_output = response.choices[0].message.content or ""
        try:
            safe_svg = sanitize_svg(model_output)
        except ValueError:
            if attempt:
                raise
            messages.extend(
                [
                    {"role": "assistant", "content": model_output[:SVG_MAX_BYTES]},
                    {
                        "role": "user",
                        "content": (
                            "That was not a valid SVG illustration. Try again and return "
                            "one complete SVG document only, following the exact restrictions "
                            "from the system message."
                        ),
                    },
                ]
            )
            continue
        return render_svg_png(safe_svg)
    raise ValueError("The model did not return a valid SVG image")

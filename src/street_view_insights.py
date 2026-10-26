"""Plain-language presentation helpers for the existing HSV color-share scan."""
from __future__ import annotations

import math
from collections.abc import Mapping


def valid_percentage(result: Mapping | None, key: str) -> float | None:
    """Return a finite percentage only when the image pipeline supplied a valid value."""
    if not isinstance(result, Mapping):
        return None
    try:
        value = float(result.get(key))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return value


def formatted_pixel_count(result: Mapping | None) -> str | None:
    if not isinstance(result, Mapping):
        return None
    try:
        count = int(result.get("sampled_pixels"))
    except (TypeError, ValueError, OverflowError):
        return None
    if count < 1:
        return None
    return f"{count:,}"


def plain_language_reading(result: Mapping | None) -> str:
    green = valid_percentage(result, "green_hued_pixel_share_pct")
    gray = valid_percentage(result, "low_saturation_gray_pixel_share_pct")
    if green is None or gray is None:
        return "A complete color summary is not available for this image. Try another clear, supported photo."
    if green == 0 and gray == 0:
        return "This scan did not register pixels matching either selected color rule. There is no color cue to describe here, so review the full image manually."
    return (
        f"The color scan marked {green:.1f}% of sampled pixels as green-hued and "
        f"{gray:.1f}% as low-saturation gray. These are color groups only; they do not "
        "identify what objects are in the image. Use the photo as a prompt for closer inspection."
    )

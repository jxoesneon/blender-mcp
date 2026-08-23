"""
Color conversion utilities, including Planckian locus / blackbody Kelvin color temperature approximations.
"""

from __future__ import annotations

import math
from typing import Tuple


def kelvin_to_rgb(temperature_k: float) -> Tuple[float, float, float]:
    """Converts a correlated color temperature (Kelvin, 1000K to 12000K) to linear sRGB components."""
    temp = max(1000.0, min(float(temperature_k), 12000.0)) / 100.0

    # Calculate Red
    if temp <= 66.0:
        red = 255.0
    else:
        red = max(0.0, min(255.0, 329.698727446 * ((temp - 60.0) ** -0.1332047592)))

    # Calculate Green
    if temp <= 66.0:
        green = max(0.0, min(255.0, 99.4708025861 * math.log(max(1.0, temp)) - 161.1195681661))
    else:
        green = max(0.0, min(255.0, 288.1221695283 * ((temp - 60.0) ** -0.0755148492)))

    # Calculate Blue
    if temp >= 66.0:
        blue = 255.0
    elif temp <= 19.0:
        blue = 0.0
    else:
        blue = max(0.0, min(255.0, 138.5177312231 * math.log(max(1.0, temp - 10.0)) - 305.0447927307))

    # Convert sRGB (0-255) to Linear RGB (0.0-1.0)
    def to_linear(c: float) -> float:
        c_norm = c / 255.0
        if c_norm <= 0.04045:
            return max(0.0, min(1.0, c_norm / 12.92))
        return max(0.0, min(1.0, ((c_norm + 0.055) / 1.055) ** 2.4))

    return (to_linear(red), to_linear(green), to_linear(blue))

"""Optional TECH-A motion state.

The Rainmeter skin keeps BG1-BG6 static and animates a separate rotator
configuration. This module contains only the portable motion state so the HUD
can disable or restore the animation without touching the static composition.
"""


class TechAAnimation:
    """Preserve the existing Jarvis motion values independently of the HUD."""

    def __init__(self):
        self.rotator_1 = 0.0
        self.rotator_2 = 0.0
        self.rotator_3 = 0.0
        self.group_angle = 0.0
        self.orbit_angle = 0.0

    def step(self):
        """Advance only the optional animated layers."""
        self.rotator_1 += 0.16
        self.rotator_2 -= 0.12
        self.rotator_3 += 0.20
        self.group_angle += 0.01
        self.orbit_angle -= 0.08

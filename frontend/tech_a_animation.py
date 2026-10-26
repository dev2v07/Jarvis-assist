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
        self.rotator_enabled = True
        self.big_animation_enabled = False
        self.big_animation_frame = 0

    def step(self):
        """Advance only the optional animated layers."""
        if self.rotator_enabled:
            self.rotator_1 += 0.16
            self.rotator_2 -= 0.12
            self.rotator_3 += 0.20
        if self.big_animation_enabled:
            self.big_animation_frame = (self.big_animation_frame + 1) % 10

    def toggle_big_animation(self):
        self.big_animation_enabled = not self.big_animation_enabled
        return self.big_animation_enabled

    def toggle_game_mode(self):
        self.rotator_enabled = not self.rotator_enabled
        return not self.rotator_enabled

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
        self._rotator_elapsed_ms = 0.0
        self._bg000_elapsed_ms = 0.0
        self._big_animation_elapsed_ms = 0.0
        # Jarvis starts in GAME MODE: rotating layers are hidden until the
        # existing GAME button toggles back to the normal desktop mode.
        self.rotator_enabled = False
        self.rotator_visible = False
        self.bg000_enabled = True
        self.rotator_1_duration_ms = 75000.0
        self.rotator_2_duration_ms = 125000.0
        self.bg000_duration_ms = 40000.0
        # Start with the TECH-A animation enabled; XPLR then toggles it off.
        self.big_animation_enabled = True
        self.big_animation_frame = 0

    def step(self, elapsed_ms=16.0):
        """Advance only the optional animated layers."""
        self._rotator_elapsed_ms += elapsed_ms
        while self._rotator_elapsed_ms >= 50.0:
            self._rotator_elapsed_ms -= 50.0
            if self.rotator_enabled:
                self.rotator_1 = (self.rotator_1 + 360.0 * 50.0 / self.rotator_1_duration_ms) % 360.0
                self.rotator_2 = (self.rotator_2 - 360.0 * 50.0 / self.rotator_2_duration_ms) % 360.0

        if self.bg000_enabled:
            self._bg000_elapsed_ms += elapsed_ms
            while self._bg000_elapsed_ms >= 50.0:
                self._bg000_elapsed_ms -= 50.0
                self.rotator_3 = (self.rotator_3 - 360.0 * 50.0 / self.bg000_duration_ms) % 360.0

        if self.big_animation_enabled:
            self._big_animation_elapsed_ms += elapsed_ms
            while self._big_animation_elapsed_ms >= 1000.0:
                self._big_animation_elapsed_ms -= 1000.0
                self.big_animation_frame = (self.big_animation_frame + 1) % 10

    def set_motion_settings(self, settings):
        """Apply persisted TECH-A motion controls in milliseconds."""
        motion = settings or {}
        self.rotator_1_duration_ms = max(1000.0, float(motion.get("rotator_1_seconds", 75)) * 1000.0)
        self.rotator_2_duration_ms = max(1000.0, float(motion.get("rotator_2_seconds", 125)) * 1000.0)
        self.bg000_duration_ms = max(1000.0, float(motion.get("bg000_seconds", 40)) * 1000.0)

    def toggle_big_animation(self):
        self.big_animation_enabled = not self.big_animation_enabled
        return self.big_animation_enabled

    def toggle_game_mode(self):
        self.rotator_visible = not self.rotator_visible
        self.rotator_enabled = self.rotator_visible
        return not self.rotator_visible

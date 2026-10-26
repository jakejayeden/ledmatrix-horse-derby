from __future__ import annotations

import math
import random
import time
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from src.plugin_system.base_plugin import BasePlugin


class HorseDerbyPlugin(BasePlugin):
    """Four-horse derby for LEDMatrix displays.

    Cycle:
      countdown -> race -> results -> repeat
    """

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self.needs_high_fps = True
        self._rng = random.SystemRandom()
        self._phase_started = time.monotonic()
        self._phase = "countdown"
        self._finish_order: List[int] = []
        self._finish_times: Dict[int, float] = {}
        self._race_noise: Dict[int, float] = {}
        self._load_config(config)
        self._start_countdown()

    def _load_config(self, config):
        self.countdown_seconds = self._positive(config.get("countdown_seconds", 15), 15.0)
        self.race_seconds = self._positive(config.get("race_seconds", 30), 30.0)
        self.results_seconds = self._positive(config.get("results_seconds", 15), 15.0)
        self.show_lane_numbers = bool(config.get("show_lane_numbers", True))

    @staticmethod
    def _positive(value, default):
        try:
            value = float(value)
            return value if value > 0 else float(default)
        except (TypeError, ValueError):
            return float(default)

    def on_config_change(self, new_config):
        self.config = new_config
        self._load_config(new_config)

    def reset_cycle_state(self):
        # A new rotation starts a fresh full derby.
        self._start_countdown()

    def get_display_duration(self):
        return self.countdown_seconds + self.race_seconds + self.results_seconds

    def update(self):
        pass

    def _start_countdown(self):
        self._phase = "countdown"
        self._phase_started = time.monotonic()
        self._finish_order = []
        self._finish_times = {}
        self._race_noise = {}

    def _start_race(self):
        self._phase = "race"
        self._phase_started = time.monotonic()
        self._finish_order = [1, 2, 3, 4]
        self._rng.shuffle(self._finish_order)

        # Keep the whole finish clustered near the requested race duration.
        # Winner crosses first, then the rest in the predetermined order.
        spacing = max(0.55, min(1.5, self.race_seconds * 0.035))
        winner_time = max(3.0, self.race_seconds - (spacing * 3.0))
        self._finish_times = {
            horse: winner_time + (rank * spacing)
            for rank, horse in enumerate(self._finish_order)
        }
        self._race_noise = {horse: self._rng.uniform(0.0, math.tau) for horse in range(1, 5)}

    def _start_results(self):
        self._phase = "results"
        self._phase_started = time.monotonic()

    def _advance_phase(self, now):
        elapsed = now - self._phase_started
        if self._phase == "countdown" and elapsed >= self.countdown_seconds:
            self._start_race()
        elif self._phase == "race" and elapsed >= self.race_seconds:
            self._start_results()
        elif self._phase == "results" and elapsed >= self.results_seconds:
            self._start_countdown()

    def display(self, force_clear=False):
        now = time.monotonic()
        if force_clear:
            self._start_countdown()
            now = time.monotonic()

        self._advance_phase(now)
        width = int(getattr(self.display_manager, "width", 128) or 128)
        height = int(getattr(self.display_manager, "height", 32) or 32)

        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        if self._phase == "countdown":
            self._render_countdown(draw, width, height, now)
        elif self._phase == "race":
            self._render_race(draw, width, height, now)
        else:
            self._render_results(draw, width, height)

        self._present(image)

    def _font(self):
        return ImageFont.load_default()

    def _text_size(self, draw, text):
        box = draw.textbbox((0, 0), text, font=self._font())
        return box[2] - box[0], box[3] - box[1]

    def _center_text(self, draw, width, y, text, fill=(255, 255, 255)):
        tw, _ = self._text_size(draw, text)
        draw.text(((width - tw) // 2, y), text, font=self._font(), fill=fill)

    def _render_countdown(self, draw, width, height, now):
        elapsed = now - self._phase_started
        remaining = max(0, int(math.ceil(self.countdown_seconds - elapsed)))
        self._center_text(draw, width, 4, "RACE STARTS IN", (255, 220, 0))
        self._center_text(draw, width, 17, str(remaining), (255, 255, 255))

    def _render_race(self, draw, width, height, now):
        elapsed = max(0.0, now - self._phase_started)
        left = 10 if self.show_lane_numbers else 2
        finish_x = width - 5
        travel = max(1, finish_x - left - 8)
        lane_h = max(6, height // 4)

        # Finish line.
        for y in range(0, height, 2):
            draw.point((finish_x, y), fill=(255, 255, 255))
            if y + 1 < height:
                draw.point((finish_x + 1, y + 1), fill=(255, 255, 255))

        horse_colors = {
            1: (255, 80, 80),
            2: (80, 180, 255),
            3: (255, 210, 70),
            4: (130, 255, 120),
        }

        for horse in range(1, 5):
            y0 = (horse - 1) * lane_h
            cy = min(height - 3, y0 + lane_h // 2)
            if self.show_lane_numbers:
                draw.text((1, max(0, cy - 3)), str(horse), font=self._font(), fill=horse_colors[horse])

            finish_t = self._finish_times.get(horse, self.race_seconds)
            base = min(1.0, elapsed / finish_t)

            # Lead changes while preserving finishing order. The wobble fades
            # out near the line so crossing order cannot be inverted.
            fade = max(0.0, 1.0 - base) ** 1.7
            wobble = math.sin(elapsed * 1.35 + self._race_noise.get(horse, 0.0)) * 0.055 * fade
            surge = math.sin(elapsed * 0.47 + horse * 1.8) * 0.025 * fade
            progress = max(0.0, min(1.0, base + wobble + surge))
            x = left + int(progress * travel)

            frame = int(elapsed * 7 + horse) % 2
            self._draw_horse(draw, x, cy, horse_colors[horse], frame)

    def _draw_horse(self, draw, x, cy, color, frame):
        """Tiny 8x7 pixel horse, facing right."""
        # body
        draw.rectangle((x + 1, cy - 2, x + 5, cy + 1), fill=color)
        # neck/head
        draw.point((x + 5, cy - 3), fill=color)
        draw.rectangle((x + 6, cy - 4, x + 7, cy - 2), fill=color)
        # tail
        draw.point((x, cy - 2), fill=color)
        draw.point((x - 1, cy - 3), fill=color)
        # legs animate between two poses
        if frame == 0:
            draw.line((x + 2, cy + 2, x + 1, cy + 4), fill=color)
            draw.line((x + 5, cy + 2, x + 6, cy + 4), fill=color)
        else:
            draw.line((x + 2, cy + 2, x + 3, cy + 4), fill=color)
            draw.line((x + 5, cy + 2, x + 4, cy + 4), fill=color)

    def _render_results(self, draw, width, height):
        self._center_text(draw, width, 1, "RESULTS", (255, 220, 0))
        order = self._finish_order or [1, 2, 3, 4]
        labels = ["1ST", "2ND", "3RD", "4TH"]
        y_positions = [9, 15, 21, 27]
        for label, horse, y in zip(labels, order, y_positions):
            text = f"{label} H{horse}"
            tw, _ = self._text_size(draw, text)
            draw.text(((width - tw) // 2, y), text, font=self._font(), fill=(255, 255, 255))

    def _present(self, image):
        # Current LEDMatrix plugins commonly render with Pillow; support the
        # usual display-manager surfaces without depending on raw matrix access.
        if hasattr(self.display_manager, "display_image"):
            self.display_manager.display_image(image)
            return
        if hasattr(self.display_manager, "show_image"):
            self.display_manager.show_image(image)
            return
        if hasattr(self.display_manager, "image"):
            self.display_manager.image = image
            if hasattr(self.display_manager, "update_display"):
                self.display_manager.update_display()
            return

        # Last-resort compatibility path for managers exposing a canvas image.
        canvas = getattr(self.display_manager, "canvas", None)
        if canvas is not None and hasattr(canvas, "paste"):
            canvas.paste(image, (0, 0))
            if hasattr(self.display_manager, "update_display"):
                self.display_manager.update_display()

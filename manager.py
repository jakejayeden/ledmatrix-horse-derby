from __future__ import annotations

import math
import random
import time
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from src.plugin_system.base_plugin import BasePlugin


class HorseDerbyPlugin(BasePlugin):
    """Animated four-horse derby for LEDMatrix displays."""

    HORSE_COLORS = {
        1: (255, 80, 80),       # red
        2: (80, 180, 255),      # blue
        3: (255, 210, 70),      # yellow
        4: (130, 255, 120),     # green
    }

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self.needs_high_fps = True
        self._rng = random.SystemRandom()
        self._phase = "countdown"
        self._phase_started = time.monotonic()
        self._finish_order: List[int] = []
        self._finish_times: Dict[int, float] = {}
        self._race_noise: Dict[int, float] = {}
        self._last_progress: Dict[int, float] = {}
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
        self._last_progress = {}

    def _start_race(self):
        self._phase = "race"
        self._phase_started = time.monotonic()
        self._finish_order = [1, 2, 3, 4]
        self._rng.shuffle(self._finish_order)

        spacing = max(0.55, min(1.5, self.race_seconds * 0.035))
        winner_time = max(3.0, self.race_seconds - (spacing * 3.0))
        self._finish_times = {
            horse: winner_time + (rank * spacing)
            for rank, horse in enumerate(self._finish_order)
        }
        self._race_noise = {
            horse: self._rng.uniform(0.0, math.tau) for horse in range(1, 5)
        }
        self._last_progress = {horse: 0.0 for horse in range(1, 5)}

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

        self.display_manager.image = image
        self.display_manager.update_display()

    @staticmethod
    def _font():
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
        title_y = max(1, height // 8)
        number_y = max(title_y + 10, height // 2)
        self._center_text(draw, width, title_y, "RACE STARTS IN", (255, 220, 0))

        number = str(remaining)
        number_w, _ = self._text_size(draw, number)
        number_x = (width - number_w) // 2
        draw.text((number_x, number_y), number, font=self._font(), fill=(255, 255, 255))

        # All four starters share one baseline with the countdown number.
        # Red + blue sit well-spaced on the left; green + yellow mirror them
        # on the right. Their legs gallop in place while waiting.
        frame = int(elapsed * 5) % 2
        horse_cy = min(height - 5, number_y + 4)
        left_near_x = max(14, number_x - 22)
        left_far_x = max(2, left_near_x - 18)
        right_near_x = min(width - 10, number_x + number_w + 14)
        right_far_x = min(width - 10, right_near_x + 18)
        self._draw_horse(draw, left_far_x, horse_cy, self.HORSE_COLORS[1], frame)
        self._draw_horse(draw, left_near_x, horse_cy, self.HORSE_COLORS[2], 1 - frame)
        self._draw_horse(draw, right_near_x, horse_cy, self.HORSE_COLORS[4], 1 - frame)
        self._draw_horse(draw, right_far_x, horse_cy, self.HORSE_COLORS[3], frame)

    def _render_race(self, draw, width, height, now):
        elapsed = max(0.0, now - self._phase_started)
        left = 10 if self.show_lane_numbers else 2
        finish_x = max(left + 10, width - 5)
        travel = max(1, finish_x - left - 7)
        lane_h = max(6, height // 4)

        # One-pixel dashed track under each horse. The track begins immediately
        # after the lane-number area and stops just before the checker line.
        # It is drawn first so the horse remains crisp when its feet overlap it.
        track_start = left
        track_end = finish_x - 1
        for horse in range(1, 5):
            y0 = (horse - 1) * lane_h
            cy = min(height - 5, y0 + lane_h // 2)
            track_y = min(height - 1, cy + 4)
            for x in range(track_start, track_end + 1, 4):
                dash_end = min(x + 1, track_end)
                draw.line((x, track_y, dash_end, track_y), fill=(90, 90, 90))

        # Checker finish line is rendered over the track ends.
        for y in range(height):
            if y % 2 == 0:
                draw.point((finish_x, y), fill=(255, 255, 255))
            elif finish_x + 1 < width:
                draw.point((finish_x + 1, y), fill=(255, 255, 255))

        for horse in range(1, 5):
            y0 = (horse - 1) * lane_h
            cy = min(height - 5, y0 + lane_h // 2)
            color = self.HORSE_COLORS[horse]

            if self.show_lane_numbers:
                draw.text((1, max(0, cy - 4)), str(horse), font=self._font(), fill=color)

            finish_t = self._finish_times.get(horse, self.race_seconds)
            base = min(1.0, elapsed / finish_t)

            # Surges still create changing pace and lead swaps, but progress is
            # clamped against the horse's previous frame so it can never move
            # backwards on the track.
            fade = max(0.0, 1.0 - base) ** 1.7
            wobble = math.sin(elapsed * 1.35 + self._race_noise.get(horse, 0.0)) * 0.055 * fade
            surge = math.sin(elapsed * 0.47 + horse * 1.8) * 0.025 * fade
            candidate = max(0.0, min(1.0, base + wobble + surge))
            progress = max(self._last_progress.get(horse, 0.0), candidate)
            self._last_progress[horse] = progress
            x = left + int(progress * travel)

            frame = int(elapsed * 7 + horse) % 2
            self._draw_horse(draw, x, cy, color, frame)

    @staticmethod
    def _draw_horse(draw, x, cy, color, frame):
        draw.rectangle((x + 1, cy - 2, x + 5, cy + 1), fill=color)
        draw.point((x + 5, cy - 3), fill=color)
        draw.rectangle((x + 6, cy - 4, x + 7, cy - 2), fill=color)
        draw.point((x, cy - 2), fill=color)
        draw.point((x - 1, cy - 3), fill=color)

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
        items = [f"{labels[i]} H{order[i]}" for i in range(4)]
        y_top = max(10, height // 3)
        y_bottom = min(height - 8, y_top + 10)
        positions = [
            (2, y_top),
            (width // 2 + 2, y_top),
            (2, y_bottom),
            (width // 2 + 2, y_bottom),
        ]

        for index, (text, (x, y)) in enumerate(zip(items, positions)):
            horse = order[index]
            draw.text((x, y), text, font=self._font(), fill=self.HORSE_COLORS[horse])

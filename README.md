# LEDMatrix Horse Derby

Animated four-horse derby plugin for [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix), designed around a 128x32 RGB LED matrix.

## What it does

Each derby runs as a complete cycle:

1. **15 second countdown** — `RACE STARTS IN` followed by the remaining seconds.
2. **~30 second race** — four animated pixel horses race from left to right.
3. **Random result every race** — the complete finishing order is shuffled before the race begins.
4. **Guaranteed finish order** — each horse receives a fixed crossing time, so the chosen winner is always the first horse across the finish line and 2nd/3rd/4th follow in the selected order.
5. **15 second results screen** — shows `1ST`, `2ND`, `3RD`, and `4TH` with the corresponding horse numbers.
6. The next time the plugin cycle starts, a fresh race and finishing order are generated.

During the race, each horse gets small pace variations so the field does not simply move at four fixed speeds. Those variations fade near the finish line so they cannot change the predetermined crossing order.

## Installation

In the LEDMatrix web interface, install this as a custom plugin from:

```text
https://github.com/jakejayeden/ledmatrix-horse-derby
```

LEDMatrix supports third-party plugin repositories directly by URL.

For development, you can also link the repository into LEDMatrix using its development helper:

```bash
./scripts/dev/dev_plugin_setup.sh link-github horse-derby https://github.com/jakejayeden/ledmatrix-horse-derby.git
```

If your LEDMatrix development setup scans `plugins/`, make sure `plugin_system.plugins_directory` is set accordingly. Production installs normally use `plugin-repos/`.

## Configuration

The plugin exposes these settings through `config_schema.json`:

| Setting | Default | Description |
| --- | ---: | --- |
| `countdown_seconds` | 15 | Countdown before the race starts |
| `race_seconds` | 30 | Approximate duration of the race |
| `results_seconds` | 15 | How long the finishing order is shown |
| `show_lane_numbers` | true | Show horse numbers 1-4 on the left side |

The plugin's display duration is automatically calculated as countdown + race + results so a normal rotation has enough time to show a full derby.

## Display design

The reference layout is **128x32**, declared in `manifest.json`.

- Horse 1: red
- Horse 2: blue
- Horse 3: yellow
- Horse 4: green
- Checker-style finish line at the right side
- Two-frame running-leg animation
- Results use a 2x2 layout so all four places remain readable on a 32-pixel-high panel

The code reads `display_manager.width` and `display_manager.height` dynamically, so it is not tied directly to raw matrix hardware dimensions.

## Files

- `manager.py` — game state, random race generation, animation, and rendering
- `manifest.json` — LEDMatrix plugin metadata
- `config_schema.json` — web UI configuration options
- `requirements.txt` — no additional dependencies beyond LEDMatrix/Pillow

## Version

Current version: **1.0.0**

## License

GPL-3.0. See `LICENSE`.

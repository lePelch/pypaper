# pypaper

pypaper is a small GUI application for Hyprland that helps you apply wallpapers per monitor.

It is designed around a stable set of generated files (`monitor_1.png`, `monitor_2.png`, ...) so you can keep the same monitor-to-wallpaper mapping across session restarts.

## What it does

- Lists your monitors and lets you assign each one a slot (1..N).
- Lets you browse a theme (a folder of images) and apply an image to a monitor.
- Converts the selected image to PNG and writes it to a stable path in the `Loaded/` folder.
- Stores the monitor/slot/theme state in a JSON file so labels and selection can be restored.

## Requirements

- Hyprland (provides `hyprctl`)
- hyprpaper
- Python + PySide6

## Data directory

By default pypaper stores everything under:

`~/.local/share/pypaper/`

Notable paths:

- `~/.local/share/pypaper/themes/` (your themes)
- `~/.local/share/pypaper/Loaded/` (generated wallpapers)
- `~/.local/share/pypaper/Loaded/state.json` (mapping and last applied selections)

You can override the location:

- `PYPAPER_DATA_ROOT=/some/path`
- `PYPAPER_THEME_ROOT=/some/path`

## Themes

Create folders under `~/.local/share/pypaper/themes/`.

Example:

```
~/.local/share/pypaper/themes/
  MyTheme/
    a.jpg
    b.png
    c.webp
```

## Persisting wallpapers across session restarts

pypaper writes stable files like:

- `~/.local/share/pypaper/Loaded/monitor_1.png`
- `~/.local/share/pypaper/Loaded/monitor_2.png`

To keep the same wallpapers after restarting your Hyprland session, point your hyprpaper configuration to those `Loaded/` files.

Example `hyprpaper.conf`:

```
preload = ~/.local/share/pypaper/Loaded/monitor_1.png
preload = ~/.local/share/pypaper/Loaded/monitor_2.png

wallpaper = eDP-1,~/.local/share/pypaper/Loaded/monitor_1.png
wallpaper = DP-8,~/.local/share/pypaper/Loaded/monitor_2.png
```

The monitor names must match what `hyprctl monitors -j` reports on your system.

## Running

- From source: `uv run python main.py`

## Arch Linux Installation


```
git clone https://github.com/lePelch/pypaper.git
cd pypaper
makepkg -si
```

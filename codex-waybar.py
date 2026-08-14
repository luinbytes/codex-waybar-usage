#!/usr/bin/env python3
"""Waybar label and GTK4 hover card for Codex usage limits."""

import ctypes.util
import json
import math
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
import tomllib
from datetime import UTC, datetime
from pathlib import Path

APP_NAME = "codex-waybar-usage"
REFRESH_SECONDS = 180
CARD_WIDTH = 340
CARD_HEIGHT = 166
CARD_RIGHT = 12
CARD_TOP = 32
HITBOX_WIDTH = 76
HITBOX_HEIGHT = 26
FALLBACK_THEME = {
    "accent": "#7aa2f7",
    "foreground": "#a9b1d6",
    "background": "#1a1b26",
    "color0": "#32344a",
    "color1": "#f7768e",
    "color7": "#787c99",
    "color8": "#444b6a",
}


def env_int(name, default, minimum=0, maximum=10_000):
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, default))))
    except ValueError:
        return default


def number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rounded(value):
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def percent(value):
    value = number(value)
    return None if value is None else max(0, min(100, rounded(value)))


def window_label(window):
    seconds = number(window.get("limit_window_seconds"), 0)
    if seconds <= 6 * 60 * 60:
        return "5h"
    if seconds <= 8 * 24 * 60 * 60:
        return "weekly"
    return f"{round(seconds / 86400)}d"


def duration_text(seconds):
    seconds = max(0, int(seconds))
    if seconds == 0:
        return "now"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def pace(window, used, now):
    duration = number(window.get("limit_window_seconds"), 0)
    if duration <= 0:
        return None

    used = max(0.0, min(100.0, number(used, 0)))
    reset = number(window.get("reset_at"))
    elapsed = (
        used / 100 if reset is None else (duration - max(0, reset - now)) / duration
    )
    elapsed = max(0.001, min(0.999, elapsed))
    remaining = 100 - used
    margin = remaining - 100 * (1 - elapsed)

    if margin > 4:
        state, status, glyph = "ahead", "under pace", "▲"
    elif margin < -4:
        state, status, glyph = "behind", "over pace", "▼"
    else:
        state, status, glyph = "onpace", "on pace", "●"
    if remaining <= 0.5:
        status, glyph = "spent", "■"
    elif remaining >= 99.5:
        status, glyph = "full", "◆"

    slope = (remaining - 100) / elapsed
    show_projection = slope < -0.01
    projection_elapsed = 1.0
    projected_remaining = remaining
    runs_out = False
    if show_projection:
        runout = elapsed + remaining / -slope
        if runout <= 1:
            projection_elapsed, projected_remaining, runs_out = runout, 0.0, True
        else:
            projected_remaining = max(0.0, remaining + slope * (1 - elapsed))

    effective_reset = (
        reset if reset is not None and reset > now else now + (1 - elapsed) * duration
    )
    return {
        "used": used,
        "status": status,
        "glyph": glyph,
        "pace_state": state,
        "margin": margin,
        "elapsed": elapsed,
        "projection_elapsed": projection_elapsed,
        "projected": 100 - projected_remaining,
        "show_projection": show_projection,
        "runs_out": runs_out,
        "effective_reset": effective_reset,
    }


def request_rate_limits(timeout=None):
    timeout = timeout or env_int("CODEX_WAYBAR_TIMEOUT", 12, 1, 60)
    codex = os.environ.get("CODEX_BIN", "codex")
    process = subprocess.Popen(
        [codex, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    messages = queue.Queue()
    threading.Thread(
        target=lambda: [messages.put(json.loads(line)) for line in process.stdout],
        daemon=True,
    ).start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def receive(request_id):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex app-server did not respond")
            try:
                message = messages.get(timeout=remaining)
            except queue.Empty as error:
                raise TimeoutError("Codex app-server did not respond") from error
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(
                    message["error"].get("message", "Codex app-server error")
                )
            return message["result"]

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": {"name": APP_NAME, "version": "1"}},
            }
        )
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "account/rateLimits/read"})
        return receive(2)
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def normalize_windows(result):
    by_id = result.get("rateLimitsByLimitId") or {}
    snapshot = by_id.get("codex") if isinstance(by_id, dict) else None
    if not snapshot or not any(snapshot.get(key) for key in ("primary", "secondary")):
        snapshot = result.get("rateLimits") or {}

    windows = []
    for key in ("primary", "secondary"):
        source = snapshot.get(key)
        if not isinstance(source, dict):
            continue
        minutes = number(source.get("windowDurationMins"), 0)
        used = percent(source.get("usedPercent"))
        if used is None or minutes <= 0:
            continue
        window = {"used_percent": used, "limit_window_seconds": minutes * 60}
        if number(source.get("resetsAt")) is not None:
            window["reset_at"] = number(source["resetsAt"])
        windows.append(window)
    return windows


def fetch_windows():
    return normalize_windows(request_rate_limits())


def select_windows(windows):
    valid = [
        window
        for window in windows
        if percent(window.get("used_percent")) is not None
        and number(window.get("limit_window_seconds"), 0) > 0
    ]
    if not valid:
        return None, None
    session = next((window for window in valid if window_label(window) == "5h"), None)
    weekly = next(
        (window for window in valid if window_label(window) == "weekly"), None
    )
    weekly = weekly or max(
        valid, key=lambda window: number(window.get("limit_window_seconds"), 0)
    )
    return (None if session is weekly else session), weekly


def derive_state(windows, now=None):
    now = time.time() if now is None else now
    session, weekly = select_windows(windows)
    if weekly is None:
        return None
    pacing = pace(weekly, number(weekly.get("used_percent"), 0), now)
    if pacing is None:
        return None
    reset = pacing["effective_reset"]
    seconds = max(0, int(reset - now))
    days, remainder = divmod(seconds, 86400)
    relative = f"{days}d {remainder // 3600}h" if days else duration_text(seconds)
    return {
        **pacing,
        "session_used": None
        if session is None
        else percent(session.get("used_percent")),
        "reset": f"{relative}  ·  {datetime.fromtimestamp(reset, UTC).astimezone().strftime('%a %H:%M')}",
    }


def waybar_output(windows):
    _session, weekly = select_windows(windows)
    if weekly is None:
        return {
            "text": "[USG --]",
            "class": "inactive",
            "tooltip": "Codex usage unavailable",
        }
    remaining = 100 - percent(weekly.get("used_percent"))
    return {
        "text": f"[USG {remaining}%]",
        "class": "warning" if remaining <= 30 else "active",
        "tooltip": f"Codex weekly: {remaining}% left",
    }


def burn_segments(used, elapsed, periods=7):
    burn_rate = used / elapsed if elapsed > 0.001 else 0
    ideal = 100 / periods
    segments = []
    for index in range(periods):
        start, end = index / periods, (index + 1) / periods
        if end <= elapsed:
            width, alpha, consumed = 1.0, 0.17, burn_rate * (end - start)
        elif start < elapsed:
            width = (elapsed - start) / (end - start)
            alpha, consumed = 0.13, burn_rate * (elapsed - start)
        else:
            segments.append((1.0, 1.0, None))
            continue
        segments.append((width, consumed / ideal, alpha))
    return segments


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def theme_file():
    default = config_home() / "omarchy/current/theme/colors.toml"
    return Path(os.environ.get("CODEX_WAYBAR_THEME", default)).expanduser()


def load_theme():
    try:
        source = tomllib.loads(theme_file().read_text())
    except (OSError, tomllib.TOMLDecodeError):
        source = FALLBACK_THEME

    def color(name, fallback):
        value = source.get(name)
        if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
            try:
                int(value[1:], 16)
                return value
            except ValueError:
                pass
        return fallback

    background = color("background", FALLBACK_THEME["background"])
    foreground = color("foreground", FALLBACK_THEME["foreground"])
    accent = color("accent", foreground)
    dim = color("color0", background)
    return {
        "background": background,
        "foreground": foreground,
        "primary": foreground,
        "muted": color("color7", foreground),
        "dim": dim,
        "positive": accent,
        "warning": color("color1", accent),
    }


def ensure_layer_shell():
    if os.environ.get("CODEX_WAYBAR_PRELOADED") == "1":
        return
    candidates = [
        os.environ.get("CODEX_WAYBAR_LAYER_SHELL", ""),
        "/usr/lib/libgtk4-layer-shell.so",
        "/usr/lib/x86_64-linux-gnu/libgtk4-layer-shell.so",
        "/usr/lib64/libgtk4-layer-shell.so",
        "/usr/lib/aarch64-linux-gnu/libgtk4-layer-shell.so",
        ctypes.util.find_library("gtk4-layer-shell") or "",
    ]
    library = next(
        (
            path
            for path in candidates
            if path and (not path.startswith("/") or Path(path).exists())
        ),
        "",
    )
    if not library:
        return
    environment = dict(os.environ)
    existing = environment.get("LD_PRELOAD", "")
    environment["LD_PRELOAD"] = f"{library}:{existing}" if existing else library
    environment["CODEX_WAYBAR_PRELOADED"] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], environment)


POPUP_MODE = "--popup" in sys.argv
if POPUP_MODE:
    ensure_layer_shell()
    import cairo
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell

    def rgb(hex_color, alpha=1.0):
        value = hex_color.lstrip("#")
        return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)) + (
            alpha,
        )

    def theme_css(theme):
        return f"""
          window.codex-overlay {{ background: transparent; }}
          .codex-hitbox {{ background: rgba(0, 0, 0, 0.02); }}
          .codex-card {{ background: {theme["background"]}; color: {theme["primary"]}; border: 1px solid {theme["dim"]}; border-radius: 18px; padding: 26px 28px 13px; box-shadow: 0 10px 26px rgba(0,0,0,0.42); font-family: sans-serif; }}
          .codex-dot {{ color: {theme["positive"]}; -gtk-icon-shadow: 0 0 7px {theme["positive"]}; min-width: 8px; min-height: 8px; }}
          .codex-header {{ min-height: 20px; }}
          .codex-title {{ color: {theme["primary"]}; font-size: 14px; font-weight: 600; }}
          .codex-subtitle {{ color: {theme["muted"]}; font-size: 11px; letter-spacing: 0.3px; min-height: 16px; }}
          .codex-session {{ min-height: 15px; margin-top: 10px; margin-bottom: 8px; }}
          .codex-tag {{ color: {theme["muted"]}; font-size: 11px; font-weight: 800; letter-spacing: 1px; min-height: 14px; }}
          .codex-muted {{ color: {theme["muted"]}; font-size: 11px; min-height: 14px; }}
          .codex-separator {{ background: {theme["dim"]}; min-height: 1px; }}
          .codex-status {{ color: {theme["positive"]}; font-size: 11px; font-weight: 600; min-height: 17px; }}
          .codex-arrow {{ color: {theme["positive"]}; font-size: 13px; font-weight: 700; margin-top: 2px; }}
          .codex-margin {{ color: {theme["positive"]}; font-size: 26px; font-weight: 600; }}
          .codex-over {{ color: {theme["warning"]}; }}
          .codex-percent {{ color: {theme["muted"]}; font-size: 13px; margin-top: 8px; }}
          .codex-reset {{ color: {theme["foreground"]}; font-size: 11px; min-height: 18px; margin-top: 1px; }}
        """

    class BurnChart(Gtk.DrawingArea):
        def __init__(self, app):
            super().__init__()
            self.app, self.state = app, None
            self.set_size_request(158, 50)
            self.set_valign(Gtk.Align.CENTER)
            self.set_draw_func(self.draw)

        def update(self, state):
            self.state = state
            self.queue_draw()

        def draw(self, _area, cr, width, height):
            if not self.state:
                return
            left, top, right, bottom = 1, 5, width - 1, height - 2
            plot_width, plot_height = right - left, bottom - top
            elapsed = max(0.001, min(0.999, self.state["elapsed"]))
            now_x = left + plot_width * elapsed
            actual_y = top + plot_height * self.state["used"] / 100
            projection_x = left + plot_width * self.state["projection_elapsed"]
            projected_y = top + plot_height * self.state["projected"] / 100
            theme = self.app.theme
            accent = (
                theme["warning"]
                if self.state["pace_state"] == "behind"
                else theme["positive"]
            )
            slot, reference_height = plot_width / 7, 0.46 * plot_height

            for index, (width_fraction, height_ratio, alpha) in enumerate(
                burn_segments(self.state["used"], elapsed)
            ):
                x = left + index * slot
                if alpha is None:
                    cr.set_source_rgba(*rgb(theme["foreground"], 0.045))
                    cr.rectangle(
                        x, bottom - reference_height, slot - 1, reference_height
                    )
                    cr.fill()
                    continue
                bar_width, total_height = (
                    width_fraction * (slot - 1),
                    height_ratio * reference_height,
                )
                base_height = min(total_height, reference_height)
                if base_height > 0:
                    cr.set_source_rgba(*rgb(theme["foreground"], alpha))
                    cr.rectangle(x, bottom - base_height, bar_width, base_height)
                    cr.fill()
                if total_height > reference_height:
                    cr.set_source_rgba(
                        *rgb(theme["foreground"], 0.34 if alpha == 0.17 else 0.26)
                    )
                    cr.rectangle(
                        x,
                        bottom - total_height,
                        bar_width,
                        total_height - reference_height,
                    )
                    cr.fill()

            cr.set_line_width(1)
            cr.set_source_rgba(*rgb(theme["dim"], 0.78))
            cr.move_to(now_x + 0.5, top)
            cr.line_to(now_x + 0.5, bottom)
            cr.stroke()
            cr.move_to(left, bottom + 0.5)
            cr.line_to(right, bottom + 0.5)
            cr.stroke()
            cr.set_dash([2.5, 3])
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_width(1.4)
            cr.set_source_rgba(*rgb(theme["muted"], 0.72))
            cr.move_to(left, top)
            cr.line_to(right, bottom)
            cr.stroke()
            if self.state["show_projection"]:
                cr.set_dash([0.5, 3.5])
                cr.set_line_width(1.6)
                cr.set_source_rgba(*rgb(accent, 0.82))
                cr.move_to(now_x, actual_y)
                cr.line_to(projection_x, projected_y)
                cr.stroke()
            cr.set_dash([])
            cr.set_line_width(2.4)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            cr.set_source_rgba(*rgb(accent))
            cr.move_to(left, top)
            cr.line_to(now_x, actual_y)
            cr.stroke()
            cr.set_source_rgb(*rgb(theme["background"])[:3])
            cr.arc(now_x, actual_y, 5.4, 0, 2 * math.pi)
            cr.fill()
            cr.set_source_rgba(*rgb(accent))
            cr.arc(now_x, actual_y, 3.4, 0, 2 * math.pi)
            cr.fill()

    class MonitorCard:
        def __init__(self, app, monitor):
            self.app = app
            geometry = monitor.get_geometry()
            self.width, self.height = geometry.width, geometry.height
            hitbox_right = env_int("CODEX_WAYBAR_HITBOX_RIGHT", 88, 0, self.width)
            self.hitbox_x = self.width - hitbox_right - HITBOX_WIDTH
            self.window = Gtk.ApplicationWindow(application=app)
            self.window.set_decorated(False)
            self.window.set_default_size(self.width, self.height)
            self.window.add_css_class("codex-overlay")
            Gtk4LayerShell.init_for_window(self.window)
            Gtk4LayerShell.set_monitor(self.window, monitor)
            Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_keyboard_mode(
                self.window, Gtk4LayerShell.KeyboardMode.NONE
            )
            Gtk4LayerShell.set_exclusive_zone(self.window, -1)
            for edge in (
                Gtk4LayerShell.Edge.TOP,
                Gtk4LayerShell.Edge.RIGHT,
                Gtk4LayerShell.Edge.BOTTOM,
                Gtk4LayerShell.Edge.LEFT,
            ):
                Gtk4LayerShell.set_anchor(self.window, edge, True)

            surface = Gtk.Fixed()
            surface.set_size_request(self.width, self.height)
            self.window.set_child(surface)
            self.hitbox = Gtk.Box()
            self.hitbox.set_size_request(HITBOX_WIDTH, HITBOX_HEIGHT)
            self.hitbox.add_css_class("codex-hitbox")
            motion = Gtk.EventControllerMotion()
            motion.connect("enter", self.enter)
            motion.connect("leave", self.leave)
            self.hitbox.add_controller(motion)
            click = Gtk.GestureClick()
            click.set_button(0)
            click.connect("pressed", self.click)
            self.hitbox.add_controller(click)
            surface.put(self.hitbox, self.hitbox_x, 0)
            self.card = self.build_card()
            self.card.set_opacity(0)
            surface.put(self.card, self.width - CARD_WIDTH - CARD_RIGHT, CARD_TOP)
            self.window.present()
            GLib.idle_add(self.limit_input_region)

        @staticmethod
        def label(text, css_class):
            label = Gtk.Label(label=text)
            label.add_css_class(css_class)
            return label

        def build_card(self):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            card.set_size_request(CARD_WIDTH, CARD_HEIGHT)
            card.add_css_class("codex-card")
            header = Gtk.Box(spacing=6)
            header.add_css_class("codex-header")
            dot = Gtk.Image.new_from_icon_name("media-record-symbolic")
            dot.set_pixel_size(8)
            dot.add_css_class("codex-dot")
            title = self.label("Codex", "codex-title")
            subtitle = self.label("Session & weekly limits", "codex-subtitle")
            subtitle.set_hexpand(True)
            subtitle.set_xalign(1)
            header.append(dot)
            header.append(title)
            header.append(subtitle)
            card.append(header)
            session = Gtk.Box(spacing=12)
            session.add_css_class("codex-session")
            session.append(self.label("S", "codex-tag"))
            self.session_value = self.label("No data", "codex-muted")
            session.append(self.session_value)
            card.append(session)
            separator = Gtk.Separator()
            separator.add_css_class("codex-separator")
            card.append(separator)
            content = Gtk.Box(spacing=12)
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            labels.set_size_request(112, 68)
            status_row = Gtk.Box(spacing=12)
            status_row.append(self.label("7D", "codex-tag"))
            self.status = self.label("under pace", "codex-status")
            status_row.append(self.status)
            labels.append(status_row)
            hero = Gtk.Box(spacing=2)
            self.arrow = self.label("▲", "codex-arrow")
            self.margin = self.label("0", "codex-margin")
            hero.append(self.arrow)
            hero.append(self.margin)
            hero.append(self.label("%", "codex-percent"))
            labels.append(hero)
            self.reset = self.label("", "codex-reset")
            self.reset.set_xalign(0)
            labels.append(self.reset)
            self.chart = BurnChart(self.app)
            content.append(labels)
            content.append(self.chart)
            card.append(content)
            return card

        def limit_input_region(self):
            surface = self.window.get_surface()
            if surface:
                surface.set_input_region(
                    cairo.Region(
                        cairo.RectangleInt(
                            self.hitbox_x, 0, HITBOX_WIDTH, HITBOX_HEIGHT
                        )
                    )
                )
            return False

        def enter(self, *_args):
            self.app.refresh_theme()
            self.card.set_opacity(1)
            self.app.refresh_async()

        def leave(self, *_args):
            self.card.set_opacity(0)

        def click(self, gesture, _presses, _x, _y):
            button = gesture.get_current_button()
            if button == 1 and (command := os.environ.get("CODEX_WAYBAR_LAUNCH")):
                try:
                    subprocess.Popen(shlex.split(command))
                except (OSError, ValueError) as error:
                    print(f"{APP_NAME}: launcher failed: {error}", file=sys.stderr)
            elif button == 3:
                self.app.refresh_async()
                signal = env_int("CODEX_WAYBAR_SIGNAL", 13, 0, 31)
                if signal:
                    subprocess.Popen(["pkill", f"-RTMIN+{signal}", "-x", "waybar"])

        def update(self, state):
            if not state:
                self.session_value.set_text("No data")
                self.status.set_text("No data")
                self.margin.set_text("—")
                self.reset.set_text("")
                self.chart.update(None)
                return
            session = state["session_used"]
            self.session_value.set_text(
                "No data" if session is None else f"{session}% used"
            )
            self.status.set_text(state["status"])
            self.arrow.set_text(state["glyph"])
            self.margin.set_text(str(abs(rounded(state["margin"]))))
            for widget in (self.status, self.arrow, self.margin):
                (
                    widget.add_css_class
                    if state["pace_state"] == "behind"
                    else widget.remove_css_class
                )("codex-over")
            self.reset.set_text("↻  " + state["reset"])
            self.chart.update(state)

    class Popup(Gtk.Application):
        def __init__(self):
            super().__init__(application_id="io.github.luinbytes.codex-waybar-usage")
            self.cards, self.refreshing = [], False
            self.theme, self.css = load_theme(), Gtk.CssProvider()

        def refresh_theme(self):
            theme = load_theme()
            if theme == self.theme and self.cards:
                return
            self.theme = theme
            self.css.load_from_data(theme_css(theme).encode())
            for card in self.cards:
                card.chart.queue_draw()

        def do_activate(self):
            if self.cards:
                return
            self.refresh_theme()
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                self.css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            monitors = Gdk.Display.get_default().get_monitors()
            for index in range(monitors.get_n_items()):
                self.cards.append(MonitorCard(self, monitors.get_item(index)))
            self.refresh_async()
            GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh_timer)

        def refresh_timer(self):
            self.refresh_async()
            return True

        def refresh_async(self):
            if not self.refreshing:
                self.refreshing = True
                threading.Thread(target=self.refresh_worker, daemon=True).start()

        def refresh_worker(self):
            try:
                state = derive_state(fetch_windows())
            except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
                print(f"{APP_NAME}: refresh failed: {error}", file=sys.stderr)
                state = None
            GLib.idle_add(self.apply_state, state)

        def apply_state(self, state):
            for card in self.cards:
                card.update(state)
            self.refreshing = False
            return False


def self_test():
    payload = {
        "rateLimits": {"primary": None, "secondary": None},
        "rateLimitsByLimitId": {
            "codex": {
                "primary": {
                    "usedPercent": 20,
                    "windowDurationMins": 300,
                    "resetsAt": 13167,
                },
                "secondary": {
                    "usedPercent": 15,
                    "windowDurationMins": 10080,
                    "resetsAt": 441531,
                },
            }
        },
    }
    windows = normalize_windows(payload)
    assert len(windows) == 2 and windows[0]["limit_window_seconds"] == 18000
    state = derive_state(windows, now=27)
    assert state["status"] == "under pace" and abs(rounded(state["margin"])) == 12
    assert state["session_used"] == 20 and round(state["projected"]) == 56
    assert waybar_output(windows)["text"] == "[USG 85%]"
    assert normalize_windows({"rateLimits": {"primary": None, "secondary": None}}) == []
    runout = pace({"limit_window_seconds": 100, "reset_at": 100}, 70, 50)
    assert runout["runs_out"] and abs(runout["projection_elapsed"] - 5 / 7) < 1e-9
    segments = burn_segments(50, 0.5)
    assert len(segments) == 7 and segments[0][2] == 0.17 and segments[3][2] == 0.13
    assert segments[4][2] is None
    assert rounded(0.5) == 1 and rounded(-0.5) == -1
    assert all(
        value.startswith("#") and len(value) == 7 for value in load_theme().values()
    )
    print(f"{APP_NAME} self-test: ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    elif POPUP_MODE:
        Popup().run(None)
    else:
        try:
            print(json.dumps(waybar_output(fetch_windows())))
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            print(f"{APP_NAME}: {error}", file=sys.stderr)
            print(json.dumps(waybar_output([])))

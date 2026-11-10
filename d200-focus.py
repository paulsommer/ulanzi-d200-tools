#!/usr/bin/python3
"""d200-focus - switch the Ulanzi D200 layout depending on the focused application.

KDE Wayland does not expose the active window to normal programs, so this service
loads a tiny KWin script that reports every window activation back via D-Bus.
For each activation the layout ~/.config/ulanzi/apps/<app>.yaml is looked up
(falling back to default.yaml), copied to ~/.config/ulanzi/config.yaml and the
ulanzi-daemon is restarted, which pushes the new buttons to the device. The KWin
script is loaded again whenever KWin (re)appears on the session bus.

The firmware draws its clock (wide display without entry) on the Ulanzi logo. After
service start, resume and USB plug-in (D-Bus method "prime", called by
d200-wide-black.service via udev) the helper layout ~/.config/ulanzi/wide-black.yaml is sent
first, which stores a black background in the device; the real layout follows.

The brightness is global: every layout is written to config.yaml with the active
value from ~/.config/d200-focus/brightness.json (set in the layout editor).

Dimming: the daemon logs every key press (also of the wide display) in the journal,
which is followed here. Without a key press for "dim_minutes" the D200 is dimmed to
"dim" (D-Bus method "dim", also used by the editor's test button); the next key press
wakes it again (D-Bus method "wake"). That key still runs its action. Only this service
sets the brightness in config.yaml: the editor calls "wake" when the brightness changes,
otherwise the dimmed state kept here and the device would drift apart.

Runs as systemd user service d200-focus.service.
"""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib, GLibUnix

VERSION = "1.4.0"
BUS_NAME = "io.github.paulsommer.D200Focus"
PLUGIN_NAME = "d200-focus"
ULANZI_DIR = Path.home() / ".config/ulanzi" ### <--- change this to your path (where ~/.config/ulanzi/ is set up)
APPS_DIR = ULANZI_DIR / "apps"
CONFIG_FILE = ULANZI_DIR / "config.yaml"
# Must live next to config.yaml so that relative image paths (./icons/...) resolve
CHECK_FILE = ULANZI_DIR / ".d200-focus-check.yaml"
VALIDATOR = Path.home() / ".local/ulanzi/venv/bin/ulanzi-manager" ### <--- change this to your path (venv of ulanzi-d200-linux install.sh)
DEFAULT_LAYOUT = "default"
WIDE_BLACK_FILE = ULANZI_DIR / "wide-black.yaml"
BRIGHTNESS_FILE = Path.home() / ".config/d200-focus/brightness.json"
# Same defaults as the layout editor (layout-editor/config.py)
DEFAULT_SETTINGS = {"day": 100, "night": 30, "night_mode": False, "dim": 1, "dim_minutes": 10}
# Log line of ulanzi-daemon for a key press, e.g. "... - INFO - Button 13 pressed (state=200)"
KEY_PRESS = re.compile(rb" - Button \d+ pressed ")
# Wait for focus to settle (e.g. Alt+Tab) before restarting the daemon
DEBOUNCE_MS = 300
# Wait for the device to settle after resume or plug-in before sending the black background
PRIME_DELAY_MS = 2000
# Time the daemon needs to push the helper layout before the real layout follows
PRIME_DURATION_MS = 1000

KWIN_SCRIPT = f"""
function report(window) {{
    if (window)
        callDBus("{BUS_NAME}", "/", "{BUS_NAME}", "activated",
                 String(window.resourceClass), String(window.desktopFileName || ""));
}}
workspace.windowActivated.connect(report);
report(workspace.activeWindow);
"""


# --------------------------------------------------------------------------
def layout_for(app_class: str, desktop_file: str = "") -> str:
    """Return the layout name for a window class or its desktop file.

    Wayland window classes are often reverse-DNS app ids (org.kde.konsole),
    so both the full class and its last component are tried. This lets the
    user simply name the file konsole.yaml. The desktop file name is tried
    afterwards, for apps whose window class differs from their desktop entry.

    Args:
        app_class: resourceClass reported by KWin.
        desktop_file: desktopFileName reported by KWin (may be empty).

    Returns:
        Layout name (file name without .yaml).
    """
    candidates = [part for value in (app_class.lower(), desktop_file.lower())
                  for part in (value, value.rsplit(".", 1)[-1])]
    for name in candidates:
        if name and (APPS_DIR / f"{name}.yaml").is_file():
            return name
    return DEFAULT_LAYOUT


# --------------------------------------------------------------------------
def load_settings() -> dict:
    """Return the brightness and dim settings chosen in the layout editor.

    Read whenever they are needed, so a change in the editor needs no notification.
    Keys missing in an older file are taken from the defaults.
    """
    if not BRIGHTNESS_FILE.is_file():
        return DEFAULT_SETTINGS
    return {**DEFAULT_SETTINGS, **json.loads(BRIGHTNESS_FILE.read_text())}


# --------------------------------------------------------------------------
def write_layout(source: Path, target: Path, brightness: int) -> None:
    """Copy a layout and set the global brightness in the copy.

    The daemon falls back to 100 without a value, so it has to be in every file
    sent to it. A "brightness" line left in a layout is replaced: layouts cannot
    override the global value.

    Args:
        source: Layout file.
        target: File to write (config.yaml or its check copy).
        brightness: Value to write (day/night or dim value).
    """
    text = re.sub(r"^brightness:.*\n", "", source.read_text(), flags=re.MULTILINE)
    target.write_text(f"brightness: {brightness}\n{text}")


class FocusService(dbus.service.Object):
    """D-Bus object called by the KWin script on every window activation."""

    # --------------------------------------------------------------------------
    def __init__(self, bus: dbus.SessionBus):
        """Register the object on the session bus."""
        super().__init__(dbus.service.BusName(BUS_NAME, bus), "/")
        self.current_layout = None
        self.pending_layout = DEFAULT_LAYOUT
        self.timer_id = None
        self.priming = False
        self.prime_timer_id = None
        self.dimmed = False
        self.idle_timer_id = None
        self.restart_idle_timer()

    # --------------------------------------------------------------------------
    def brightness(self) -> int:
        """Return the brightness to send: the dim value while dimmed, else day or night."""
        settings = load_settings()
        if self.dimmed:
            return settings["dim"]
        return settings["night"] if settings["night_mode"] else settings["day"]

    # --------------------------------------------------------------------------
    @dbus.service.method(BUS_NAME, in_signature="ss")
    def activated(self, app_class: str, desktop_file: str):
        """Remember the wanted layout and (re)start the debounce timer.

        Args:
            app_class: resourceClass of the newly focused window.
            desktop_file: desktopFileName of the newly focused window (may be empty).
        """
        layout = layout_for(app_class, desktop_file)
        # Format "focus: <class> -> ..." is parsed by layout-editor/new_layout_dialog.py
        print(f"focus: {app_class} -> {layout} (desktop file: {desktop_file})", flush=True)
        self.pending_layout = layout
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(DEBOUNCE_MS, self.apply)

    # --------------------------------------------------------------------------
    @dbus.service.method(BUS_NAME, in_signature="")
    def prime(self):
        """Schedule sending the black wide display background.

        Called at service start, after resume and by d200-wide-black.service when
        the D200 is plugged in - in all these cases the firmware has reloaded its
        logo. Layout switches are held back until the real layout is sent again.
        """
        print("wide display: black background requested", flush=True)
        self.priming = True
        if self.prime_timer_id:
            GLib.source_remove(self.prime_timer_id)
        self.prime_timer_id = GLib.timeout_add(PRIME_DELAY_MS, self.send_wide_black)

    # --------------------------------------------------------------------------
    @dbus.service.method(BUS_NAME, in_signature="")
    def dim(self):
        """Dim the D200 until the next key press.

        Called by the idle timer and by the "dim" button of the layout editor. Sent
        even when already dimmed: the editor's test button may have sent a brighter
        config.yaml meanwhile.
        """
        print("dim", flush=True)
        self.dimmed = True
        self.send_brightness()

    # --------------------------------------------------------------------------
    @dbus.service.method(BUS_NAME, in_signature="")
    def wake(self):
        """Send the day/night brightness again and restart the idle timer.

        Called on a key press while dimmed and by the layout editor whenever the
        brightness changes, so the dimmed state here always matches the device.
        """
        print("wake", flush=True)
        self.dimmed = False
        self.restart_idle_timer()
        self.send_brightness()

    # --------------------------------------------------------------------------
    def key_pressed(self) -> None:
        """Key press on the D200 (from the daemon's journal): wake up or restart the idle timer."""
        if self.dimmed:
            self.wake()
        else:
            self.restart_idle_timer()

    # --------------------------------------------------------------------------
    def restart_idle_timer(self) -> None:
        """(Re)start the timer that dims the D200 after "dim_minutes" without a key press."""
        if self.idle_timer_id:
            GLib.source_remove(self.idle_timer_id)
        self.idle_timer_id = GLib.timeout_add_seconds(load_settings()["dim_minutes"] * 60, self.idle)

    # --------------------------------------------------------------------------
    def idle(self) -> bool:
        """Idle timer expired: dim the D200."""
        self.idle_timer_id = None
        self.dim()
        return False

    # --------------------------------------------------------------------------
    def send_brightness(self) -> None:
        """Send the current layout again with the brightness of the current state.

        Rewrites config.yaml instead of the app layout, so a layout sent with the
        editor's test button stays. While priming, prime_done() sends the layout
        with the right brightness anyway.
        """
        if self.priming:
            return
        write_layout(CONFIG_FILE, CHECK_FILE, self.brightness())
        os.replace(CHECK_FILE, CONFIG_FILE)
        subprocess.run(["systemctl", "--user", "--no-block", "restart", "ulanzi-daemon.service"])

    # --------------------------------------------------------------------------
    def on_sleep(self, start: bool):
        """logind PrepareForSleep handler: prime again after resume.

        Args:
            start: True before suspend, False after resume.
        """
        if not start:
            self.prime()

    # --------------------------------------------------------------------------
    def send_wide_black(self) -> bool:
        """Push the helper layout, then schedule the real layout."""
        self.prime_timer_id = None
        write_layout(WIDE_BLACK_FILE, CONFIG_FILE, self.brightness())
        subprocess.run(["systemctl", "--user", "restart", "ulanzi-daemon.service"])
        GLib.timeout_add(PRIME_DURATION_MS, self.prime_done)
        return False

    # --------------------------------------------------------------------------
    def prime_done(self) -> bool:
        """Send the wanted layout again after the helper layout."""
        self.priming = False
        self.current_layout = None
        return self.apply()

    # --------------------------------------------------------------------------
    def apply(self) -> bool:
        """Copy the pending layout to config.yaml and restart the daemon if it changed.

        The layout is validated with ulanzi-manager first. A broken layout would
        make the daemon fail to start and leave the device showing the previous
        buttons without any visible reason, so it is rejected and logged instead.
        """
        self.timer_id = None
        if self.priming:
            return False  # prime_done() applies the pending layout
        layout = self.pending_layout
        if layout != self.current_layout:
            source = APPS_DIR / f"{layout}.yaml"
            if not source.is_file():
                print(f"missing layout file: {source}", file=sys.stderr, flush=True)
                return False
            write_layout(source, CHECK_FILE, self.brightness())
            check = subprocess.run([str(VALIDATOR), "validate", str(CHECK_FILE)], capture_output=True, text=True)
            if check.returncode != 0:
                CHECK_FILE.unlink()
                errors = [line for line in check.stderr.splitlines() if "ERROR" in line]
                print(f"invalid layout {source}, keeping previous:", *errors, sep="\n  ", file=sys.stderr, flush=True)
                return False
            os.replace(CHECK_FILE, CONFIG_FILE)
            subprocess.run(["systemctl", "--user", "--no-block", "restart", "ulanzi-daemon.service"])
            print(f"layout: {layout}", flush=True)
            self.current_layout = layout
        return False


# --------------------------------------------------------------------------
def load_kwin_script(bus: dbus.SessionBus) -> None:
    """Write the KWin script to the runtime dir and load it into KWin.

    An instance left over from a previous run is unloaded first, otherwise
    KWin refuses to load a script with the same plugin name.
    """
    path = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "d200-focus-kwin.js"
    path.write_text(KWIN_SCRIPT)
    scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting"), "org.kde.kwin.Scripting")
    if scripting.isScriptLoaded(PLUGIN_NAME):
        scripting.unloadScript(PLUGIN_NAME)
    # loadScript is overloaded, so the two-argument variant must be selected explicitly
    scripting.loadScript(str(path), PLUGIN_NAME, signature="ss")
    scripting.start()


# --------------------------------------------------------------------------
def unload_kwin_script(bus: dbus.SessionBus) -> None:
    """Remove the KWin script again when the service stops."""
    scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting"), "org.kde.kwin.Scripting")
    scripting.unloadScript(PLUGIN_NAME)


# --------------------------------------------------------------------------
def watch_kwin(bus: dbus.SessionBus) -> None:
    """Load the KWin script now if KWin runs, and again whenever KWin (re)starts.

    A KWin restart (crash, kwin_wayland --replace) drops all loaded scripts,
    and at login d200-focus may start before KWin is on the bus. Idea taken
    from Ulanzi-Deck-Linux (crates/ulanzi-deckd/src/focus/kwin.rs).
    """
    # --------------------------------------------------------------------------
    def on_owner_changed(_name: str, _old_owner: str, new_owner: str) -> None:
        """NameOwnerChanged handler: KWin got a (new) owner on the bus."""
        if new_owner:
            print("KWin (re)started, loading focus script", flush=True)
            load_kwin_script(bus)

    bus.add_signal_receiver(
        on_owner_changed, signal_name="NameOwnerChanged",
        dbus_interface="org.freedesktop.DBus", arg0="org.kde.KWin")
    if bus.name_has_owner("org.kde.KWin"):
        load_kwin_script(bus)


# --------------------------------------------------------------------------
def watch_key_presses(service: FocusService) -> subprocess.Popen:
    """Follow the journal of ulanzi-daemon and report every key press to the service.

    The daemon has no other interface for key events, but it logs each of them,
    also for keys without an action (wide display with the clock). journalctl
    keeps following the unit across the daemon restarts of every layout switch.

    Returns:
        The journalctl process, to stop it when the service ends.
    """
    journal = subprocess.Popen(
        ["journalctl", "--user", "--unit=ulanzi-daemon.service", "--follow", "--lines=0", "--output=cat"],
        stdout=subprocess.PIPE)
    rest = b""

    # --------------------------------------------------------------------------
    def on_output(fd: int, _condition) -> bool:
        """Read new journal lines; a line may arrive in two chunks, so the last part is kept."""
        nonlocal rest
        data = os.read(fd, 4096)
        if not data:
            print("journalctl ended, no wake up on key press", file=sys.stderr, flush=True)
            return False
        *lines, rest = (rest + data).split(b"\n")
        if any(KEY_PRESS.search(line) for line in lines):
            service.key_pressed()
        return True

    GLib.io_add_watch(journal.stdout.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN | GLib.IO_HUP, on_output)
    return journal


# --------------------------------------------------------------------------
def main() -> None:
    """Start the D-Bus service, load the KWin script and run until terminated."""
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    service = FocusService(bus)
    service.prime()
    dbus.SystemBus().add_signal_receiver(
        service.on_sleep, signal_name="PrepareForSleep",
        dbus_interface="org.freedesktop.login1.Manager", bus_name="org.freedesktop.login1")
    watch_kwin(bus)
    journal = watch_key_presses(service)

    loop = GLib.MainLoop()
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, loop.quit)  # from systemd
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, loop.quit)   # Ctrl+C
    try:
        loop.run()
    finally:
        journal.terminate()
        unload_kwin_script(bus)


if __name__ == "__main__":
    main()

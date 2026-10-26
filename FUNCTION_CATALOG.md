# Function Catalog

Dependencies: bash, ydotool, awk, librsvg2-bin (rsvg-convert), unzip, linux-libc-dev (input-event-codes.h), python3-dbus, python3-gi, systemd, KWin (Plasma 6), ulanzi-d200-linux (racerxdl).

## d200-key

No functions. Translates `ctrl+shift+f1` into ydotool key codes (looked up in `/usr/include/linux/input-event-codes.h`,
aliases ctrl/shift/alt/altgr/super), presses all keys in order and releases them in reverse order.

## d200-icon

No functions. Reads an SVG, PNG or JPG file (type by extension), an SVG from `archive.jar!path.svg` (via `unzip -p`), or
none with `-`, and builds a wrapper SVG (image as base64 data URI, scaled to fit with aspect ratio kept, plus optional
text lines split at `|`) that `rsvg-convert` renders as a black
196×196 button image. Icon size and margins come from the layout values at the top of the script (marked `### <--- layout`); with two or
more text lines the text moves closer to the bottom edge (`text_bottom_multi`) and the icon grows by that difference;
text-only is centered.

## my-layouts/make-icons.sh

No functions. One `d200-icon` call per key image (PyCharm JAR, GIMP 3 icon themes, Breeze, hicolor, own SVGs in
`my-layouts/svg/`), output to `my-layouts/icons/`; images not made with `d200-icon` are listed in the closing comment.

## d200-focus

| Line | Function | Description |
|------|----------|-------------|
| 59 | `layout_for` | Maps a window class to a layout name: tries the full class and its last dot component (`org.kde.konsole` → `konsole`) in `~/.config/ulanzi/apps/`, else `default` |
| 79 | `FocusService` | D-Bus object `io.github.paulsommer.D200Focus` on the session bus, called by the KWin script and by `d200-wide-black.service` |
| 83 | `FocusService.__init__` | Registers the bus name and object path `/` |
| 94 | `FocusService.activated` | D-Bus method called on every window activation; stores the wanted layout and restarts the 300 ms debounce timer |
| 109 | `FocusService.prime` | D-Bus method (start, resume, USB plug-in): holds back layout switches and sends the black wide display background after 2 s, so the firmware clock is not drawn on the Ulanzi logo |
| 123 | `FocusService.on_sleep` | logind `PrepareForSleep` handler on the system bus; calls `prime` after resume |
| 133 | `FocusService.send_wide_black` | Copies `~/.config/ulanzi/wide-black.yaml` (link to `my-layouts/`) to config.yaml, restarts ulanzi-daemon and schedules `prime_done` after 1 s |
| 142 | `FocusService.prime_done` | Ends priming and applies the pending layout again |
| 149 | `FocusService.apply` | If the layout changed (and no priming is running): validates it with `ulanzi-manager validate` (copy next to config.yaml so `./icons/` resolves), rejects broken layouts with a log message, otherwise replaces config.yaml and restarts ulanzi-daemon |
| 180 | `load_kwin_script` | Writes the KWin script (reports `workspace.windowActivated` via `callDBus`) to `$XDG_RUNTIME_DIR` and loads it, unloading a leftover instance first |
| 197 | `unload_kwin_script` | Unloads the KWin script when the service stops |
| 204 | `main` | Sets up the GLib D-Bus main loop, primes the wide display, subscribes to logind `PrepareForSleep`, loads the KWin script, quits on SIGTERM/SIGINT |

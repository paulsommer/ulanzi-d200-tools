# Issue texts for racerxdl/ulanzi-d200-linux

Ready to paste into https://github.com/racerxdl/ulanzi-d200-linux/issues/new. Derived from `ulanzi-d200-feature-proposals.md`. Copy the title line into the title field and the content of the block into the description.

## Compact variant (send this first)

A single short issue as first contact. The detailed issues below are kept for follow-ups if the author shows interest.

**Title:** `Reload config without restarting the daemon?`

~~~~markdown
Hi, thanks for this project – my D200 runs nicely on Kubuntu 26.04 / Plasma 6 Wayland.

I switch layouts per focused application (small KWin script + D-Bus service on my side, no changes to your code). Right now every switch means copying config.yaml and restarting ulanzi-daemon, which re-enumerates the USB device each time. A reload on SIGHUP (or via the API) would make this much cleaner.

Related small thing: `null` buttons are left out of the manifest (config.py, `if button_data is None: continue`), so after a layout swap they keep the previous layout's images. `enabled: false` + `background_tile` from #20 works around it.

I also have a ydotool-based key helper for Wayland and some notes on the firmware clock on the wide display, if that's of interest.
~~~~

## Detailed issues (for follow-ups)

## Issue 1

**Title:** `[Feature Request] Config reload without restart / per-application layouts`

~~~~markdown
Thanks for ulanzi-d200-linux! It runs my D200 on Kubuntu 26.04 with KDE Plasma 6 on Wayland (tested on commit `d46d521`).

I built per-application layouts around the daemon: a small Python service switches the layout when the focused window changes (~0.4 s). It doesn't touch your code. This issue is about two things that would make that cleaner.

### How it works on my side

1. **Active window:** Wayland gives normal programs no access to the active window. The service writes a small KWin script, loads it via D-Bus (`org.kde.KWin /Scripting`, `loadScript(path, name)` with explicit signature `ss`, because the method is overloaded) and calls `start()`.
2. **Report:** the script connects to `workspace.windowActivated` and calls `callDBus(...)` with `window.resourceClass` on a session-bus service.
3. **Mapping:** `~/.config/ulanzi/apps/<class>.yaml`, else `default.yaml`. Reverse-DNS classes also match their last part (`org.kde.konsole` → `konsole.yaml`).
4. **Debounce:** 300 ms, so Alt+Tab and the lock screen don't cause extra switches.
5. **Validate:** the layout is copied next to `config.yaml` (so `./icons/` resolves) and checked with `ulanzi-manager validate`. A broken layout is logged and the previous one stays.
6. **Apply:** copy to `config.yaml`, then `systemctl --user restart ulanzi-daemon`. This needs a drop-in with `StartLimitIntervalSec=0`, otherwise systemd blocks the daemon after 5 restarts in 10 s.

### Problem

The daemon reads `config.yaml` only at start. Every layout switch is a full restart, and every daemon stop makes the D200 re-enumerate its HID interfaces (new `input` and `hidraw` devices in the kernel log). Other tools watching input devices, such as input-remapper, react each time.

### Suggestions

- Reload `config.yaml` without restarting the daemon, e.g. on SIGHUP or via an API call. That avoids the USB reconnect on every switch.
- Optionally, per-application profiles in the daemon itself. The KWin script is the only Plasma-specific part; I'm happy to share it.
~~~~

## Issue 2

**Title:** `[Feature Request] ydotool backend for the key action on Wayland`

~~~~markdown
The `key` action uses xdotool, which only works on X11. On KDE Plasma 6 Wayland (Kubuntu 26.04) I use a small bash helper called from the `command` action instead:

- **Backend:** `ydotool key` with raw evdev codes, through the `ydotoold` user service (Ubuntu package `ydotool`).
- **Key names:** the `KEY_*` names from `/usr/include/linux/input-event-codes.h` without the prefix (`f8`, `left`, `playpause`, `nextsong`), plus the aliases `ctrl`, `shift`, `alt`, `altgr`, `super`. Codes are looked up from the header at runtime.
- **Order:** all keys are pressed in order and released in reverse, e.g. `ctrl+shift+f1` → `29:1 42:1 59:1 59:0 42:0 29:0`.
- **Layout:** evdev codes are physical keys, so `shift+alt+7` hits the 7 key on any keyboard layout.
- **Double press:** works with a shell chain, e.g. Search Everywhere in JetBrains IDEs: `d200-key shift && d200-key shift`.

### Suggestion

Use ydotool as the `key` backend when `WAYLAND_DISPLAY` is set. I can share the helper script if useful.
~~~~

## Issue 3

**Title:** `Unused (null) buttons keep the image of the previous layout`

~~~~markdown
After switching to a layout (replacing `config.yaml` and restarting the daemon), buttons that are `null` in the new layout keep the image of the previous layout.

### Cause

`ConfigParser` skips `null` entries, so `set_buttons()` leaves their keys out of the manifest. The firmware keeps whatever it showed in those slots.

### Workaround

A disabled button with a black 196×196 PNG as background, the form the web UI writes itself:

```yaml
- enabled: false
  background_tile: ./icons/blank.png
```

This is the form introduced in #20. #20 also fills empty slots with a tile, but only in the web UI and only when a global mosaic `background` is set. A hand-written or swapped-in `config.yaml` with `null` entries still leaves the old images on the device.

Things that don't work:

- `enabled: false` alone is rejected by the validator ("must specify either 'image' or 'icon_spec'").
- `image: ./icons/blank.png` with `action_enabled: false` works in the daemon, but the web UI then refuses to save ("Botão 3: preencha cmd"), since it treats the button as enabled without a command.

### Suggestion

On a full (non-partial) upload, send an empty entry for every unused slot 0–12, or use a built-in blank image.
~~~~

## Issue 4

**Title:** `[Feature Request] display_mode: clock with background image for the wide display`

~~~~markdown
The firmware clock (`SmallViewMode` 1, wide display without config entry) is drawn on the last background stored in the device. By default, and again after resume or USB re-plug, that is the Ulanzi logo with the web address.

### Workaround (config only)

1. Send a helper layout where only button 13 is set: a black 458×196 PNG with `display_mode: background`.
2. About 1 s later, send the real layout with button 13 = `null`. The daemon now selects clock mode, and the clock appears on black after 3–4 s.
3. Layout switches keep the black background, since button 13 is not in the manifest.
4. Repeat 1–2 at service start, after resume (logind `PrepareForSleep(false)`) and on USB plug-in (udev rule starting a oneshot user unit).

The same happens with the web UI alone: switching button 13 to stats and back to inactive leaves the clock on black, because the last stats frame stays stored. So the clock always uses the last stored wide image.

**Warning:** sending the black image and `SmallViewMode` 1 together in one manifest crashed the firmware into its factory state. A daemon restart restored everything. Image first (background mode), then mode 1 separately, works.

### Suggestion

A `display_mode: clock` for button 13 with an optional background image. The daemon would upload the image in background mode and then switch to mode 1. Since it already re-sends the mode every second as keepalive and restores the config after a firmware restart, resume would be covered too.
~~~~

## Issue 5

**Title:** `Stats mode on the wide display turns black after a few seconds`

~~~~markdown
Button 13 with `display_mode: stats` and a black PNG as background shows CPU/RAM/GPU at first, then turns black after 2–3 s.

This also happens with only the daemon and the web UI running (no other tools). The daemon log shows no error or restart in the meantime.

Setup: Kubuntu 26.04, KDE Plasma 6 Wayland, commit `d46d521`. Seen once and not investigated further; happy to test or provide logs.
~~~~

## Issue 6

**Title:** `Web UI drops YAML comments and icon_spec when saving`

~~~~markdown
Saving in the web UI rewrites `config.yaml` and drops YAML comments and `icon_spec` entries. That makes hand-edited layouts hard to combine with the UI.

Would it be possible to preserve unknown or unchanged fields (and ideally comments, e.g. via ruamel.yaml) when saving?
~~~~

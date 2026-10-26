# Ulanzi D200 on KDE Plasma Wayland – feature proposals

## Context

Thanks for ulanzi-d200-linux. It runs my D200 on Kubuntu 26.04 with KDE Plasma 6 on Wayland, based on commit `d46d521`. Below are four add-ons I built around it, plus a few observations. The core is feature 1, per-application layouts; features 2–4 came up while using it. None of them touch your code: they are a small script, a service, a udev rule and some YAML. Take whatever fits your plans. I can send the full scripts on request.

| Feature | Problem on my setup | Suggestion for the daemon |
| --- | --- | --- |
| 1. Per-application layouts | No active-window info on Wayland | KWin script + D-Bus, config reload without restart |
| 2. Key action on Wayland | `key` needs xdotool (X11 only) | ydotool backend |
| 3. Clear unused buttons | `null` keeps the previous image | Send empty entries for unused slots |
| 4. Clock without logo | Firmware clock is drawn on the Ulanzi logo | `display_mode: clock` with a background image |

## 1. Per-application layouts (KDE Plasma Wayland)

The Python service `d200-focus` switches the layout when the focused window changes, in about 0.4 s.

1. **Active window:** Wayland gives normal programs no access to the active window. The service writes a small KWin script, loads it via D-Bus (`org.kde.KWin /Scripting`, `loadScript(path, name)` with explicit signature `ss`, because the method is overloaded) and calls `start()`.
2. **Report:** the script connects to `workspace.windowActivated` and calls `callDBus(...)` with `window.resourceClass` on a session-bus service (`io.github.paulsommer.D200Focus`, method `activated(s)`).
3. **Mapping:** `~/.config/ulanzi/apps/<class>.yaml`, else `default.yaml`. Reverse-DNS classes also match their last part, so `org.kde.konsole` finds `konsole.yaml`.
4. **Debounce:** 300 ms, so Alt+Tab and the lock screen don't cause extra switches.
5. **Validate:** the layout is copied next to `config.yaml` (so `./icons/` resolves) and checked with `ulanzi-manager validate`. A broken layout is logged and the previous one stays.
6. **Apply:** copy to `config.yaml`, then `systemctl --user restart ulanzi-daemon`. A drop-in with `StartLimitIntervalSec=0` is needed, otherwise systemd blocks the daemon after 5 restarts in 10 s.

**Suggestions:**

- A reload of `config.yaml` without restarting the daemon (SIGHUP or an API call). That avoids the USB reconnect on every switch.
- Optionally, per-application profiles in the daemon itself. The KWin script is the only Plasma-specific part.

## 2. Key action on Wayland (ydotool)

Key combinations like `ctrl+shift+f1` work on Wayland through a small bash helper `d200-key`, called by the `command` action.

- **Backend:** `ydotool key` with raw evdev codes, through the `ydotoold` user service (Ubuntu package `ydotool`).
- **Key names:** the `KEY_*` names from `/usr/include/linux/input-event-codes.h` without the prefix (`f8`, `left`, `playpause`, `nextsong`), plus the aliases `ctrl`, `shift`, `alt`, `altgr`, `super`. Codes are looked up from the header at runtime.
- **Order:** all keys are pressed in order and released in reverse, e.g. `29:1 42:1 59:1 59:0 42:0 29:0`.
- **Layout:** evdev codes are physical keys, so `shift+alt+7` hits the 7 key on any keyboard layout.
- **Double press:** works with a shell chain, e.g. Search Everywhere in JetBrains IDEs: `d200-key shift && d200-key shift`.

**Suggestion:** use ydotool as the `key` backend when `WAYLAND_DISPLAY` is set.

## 3. Clearing unused buttons

After a layout switch, buttons that are `null` in the new layout keep the image of the previous layout.

- **Cause:** `ConfigParser` skips `null` entries, so `set_buttons()` leaves their keys out of the manifest. The firmware keeps whatever it showed in those slots.
- **Workaround:** a disabled button with a black 196×196 PNG as background, the form your web UI writes itself:

```yaml
- enabled: false
  background_tile: ./icons/blank.png
```

- `enabled: false` alone is rejected by the validator ("must specify either 'image' or 'icon\_spec'").
- `image: ./icons/blank.png` with `action_enabled: false` works in the daemon, but the web UI then refuses to save ("Botão 3: preencha cmd"), since it treats the button as enabled without a command.

**Suggestion:** on a full (non-partial) upload, send an empty entry for every unused slot 0–12, or a built-in blank image.

## 4. Firmware clock on black instead of the logo

The firmware clock (`SmallViewMode` 1, wide display without config entry) is drawn on the last background stored in the device. By default, and again after resume or USB re-plug, that is the Ulanzi logo with the web address.

**Workaround, config only:**

1. Send a helper layout where only button 13 is set: a black 458×196 PNG with `display_mode: background`.
2. About 1 s later, send the real layout with button 13 = `null`. The daemon now selects clock mode, and the clock appears on black after 3–4 s.
3. Layout switches keep the black background, since button 13 is not in the manifest.
4. Repeat steps 1–2 at service start, after resume (logind `PrepareForSleep(false)` on the system bus) and on USB plug-in (udev rule with `ENV{SYSTEMD_USER_WANTS}` that starts a oneshot user unit, which calls `prime()` on the service via `busctl --user`).

**Warning:** sending the black image and `SmallViewMode` 1 together in one manifest crashed the firmware into its factory state. A daemon restart restored everything. Image first (background mode, as your daemon does), then mode 1 separately, works.

**Seen with the web UI alone:** switching button 13 to stats and back to inactive also leaves the clock on black, because the last stats frame stays stored in the device. That confirms the clock always uses the last stored wide image.

**Suggestion:** a `display_mode: clock` for button 13 with an optional background image. The daemon would upload the image in background mode and then switch to mode 1. It already re-sends the mode every second as keepalive and restores the config after a firmware restart, so resume would be covered too.

## Smaller observations

These were seen once or in passing and not investigated further.

- **Stats mode goes black:** button 13 with `display_mode: stats` and a black PNG as background showed CPU/RAM/GPU at first, then turned black after 2–3 s. The same happens with only your daemon and web UI running (my services stopped); the daemon log shows no error or restart meanwhile.
- **USB re-enumeration:** every daemon stop makes the D200 re-register its HID interfaces (new `input` and `hidraw` devices in the kernel log). Other tools that watch input devices, such as input-remapper, react each time.
- **Web UI drops data:** saving drops YAML comments and `icon_spec`, which makes hand-edited layouts hard to combine with the UI.
- **No hot reload:** the daemon reads `config.yaml` only at start. Changes need `systemctl --user restart ulanzi-daemon`.

# ulanzi-d200-tools

The **Ulanzi D200** is a stream controller: a small desk keypad with 13 display keys and one wide display.
[racerxdl/ulanzi-d200-linux](https://github.com/racerxdl/ulanzi-d200-linux) makes it usable on Linux. This project
adds what I needed on top of it with KDE Plasma 6 on Wayland: keys that send keyboard shortcuts (via `ydotool`,
because `xdotool` does not work on Wayland), and key layouts that switch automatically with the application in the
foreground – for example debugger keys in PyCharm and tool keys in GIMP.

It is my personal setup (Kubuntu 26.04, Plasma 6, Wayland), shared as it is. The scripts are small and should be easy
to adapt.

## Contents

| File | Purpose |
|---|---|
| `d200-key` | sends a key combination such as `ctrl+shift+f1` via `ydotool` (replacement for the `key` action, which needs `xdotool` and does not work on Wayland) |
| `d200-icon` | renders an application's SVG icon (from a file or from a JAR) and/or the function name as a 196×196 key image on black; needs `librsvg2-bin` |
| `d200-focus` | service: on every window switch it picks the layout `~/.config/ulanzi/apps/<application>.yaml`, validates it, copies it to `config.yaml` and restarts the daemon |
| `systemd/d200-focus.service` | user unit for `d200-focus` (starts with the Plasma session) |
| `systemd/d200-wide-black.service` | user unit started by udev when the D200 is plugged in; makes `d200-focus` send the black background again |
| `udev/99-d200-focus.rules` | udev rule, starts `d200-wide-black.service` on plug-in |
| `systemd/ulanzi-daemon.service.d/override.conf` | lifts systemd's restart limit for the daemon (otherwise blocked after 5 restarts in 10 s); `TimeoutStopSec=2`, because the daemon loses a SIGTERM during its internal reconfiguration after plug-in and systemd would wait 90 s before killing it |
| `my-layouts/apps/*.yaml` | key layout per application (`default.yaml`, `konsole.yaml`, ...) |
| `my-layouts/wide-black.yaml` | helper layout: only a black background for the wide display (see "Clock on black") |
| `my-layouts/icons/*.png` | key images (196×196, `blank-wide.png` 458×196) |
| `ulanzi-d200-feature-proposals.md` | feature proposals for the author of ulanzi-d200-linux |
| `ulanzi-d200-issues.md` | GitHub issue texts derived from them: a compact version for first contact, detailed single issues for follow-up questions |

Scripts and units are symlinked into `~/.local/bin` and `~/.local/share/systemd/user`, `my-layouts/apps`,
`my-layouts/icons` and `my-layouts/wide-black.yaml` into `~/.config/ulanzi/`. Changes to layouts and images therefore
end up directly in the repository.

`~/.config/ulanzi/layouts/`, on the other hand, is the folder where the web UI stores its saved layouts (file names =
sha256). It does not belong to this project and is deliberately not a link – that is why this project's folder is
called `my-layouts`.

The unit links are deliberately not placed in `~/.config/systemd/user`: there, a symlink to a file outside the search
paths counts as a "linked" unit, and `systemctl --user disable` deletes it – afterwards systemd reports "Unit does not
exist". The link in `~/.local/share/systemd/user` survives `disable`. `enable` still creates an additional link in
`~/.config/systemd/user`, which `disable` removes again; that is normal.

## Where things live

| What | Location | After a reinstall |
|---|---|---|
| ydotool (incl. `ydotoold` and user unit `ydotool.service`) | apt package | install again |
| udev rule (access to `hidraw`) | `/etc/udev/rules.d/99-ulanzi.rules` | copy from the ulanzi-d200-linux repo |
| ulanzi-d200-linux clone | e.g. `~/Projekte/ulanzi-d200-linux` | stays (data partition) |
| venv, wrapper | `~/.local/ulanzi/venv`, `~/.local/bin/ulanzi-daemon` | `install.sh` creates both again |
| services `ulanzi-daemon`, `ulanzi-web` | `~/.config/systemd/user/` | `install.sh` creates them again |
| scripts, `d200-focus` units, layouts, images | this project | create the symlinks again |

## Installation

Adjust `T` and the path of the ulanzi-d200-linux clone to your setup.

```bash
sudo apt install ydotool
T=~/Projekte/ulanzi-d200-tools
# layouts, icons and helper layout first, so install.sh does not create its own icons dir
mkdir -p ~/.config/ulanzi
ln -s $T/my-layouts/apps $T/my-layouts/icons $T/my-layouts/wide-black.yaml ~/.config/ulanzi/
cp $T/my-layouts/apps/default.yaml ~/.config/ulanzi/config.yaml

cd ~/Projekte/ulanzi-d200-linux
sudo cp 99-ulanzi.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger
bash install.sh
# PyGObject (launching applications) comes from the system, not from pip
sed -i 's/^include-system-site-packages = false/include-system-site-packages = true/' ~/.local/ulanzi/venv/pyvenv.cfg

mkdir -p ~/.local/bin ~/.config/systemd/user/ulanzi-daemon.service.d
ln -s $T/d200-key $T/d200-focus ~/.local/bin/
mkdir -p ~/.local/share/systemd/user
ln -s $T/systemd/d200-focus.service $T/systemd/d200-wide-black.service ~/.local/share/systemd/user/
sudo cp $T/udev/99-d200-focus.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules
ln -s $T/systemd/ulanzi-daemon.service.d/override.conf ~/.config/systemd/user/ulanzi-daemon.service.d/
systemctl --user daemon-reload
systemctl --user enable --now ydotool.service ulanzi-daemon.service d200-focus.service
```

`install.sh` does not overwrite an existing `config.yaml` and leaves the linked `icons` untouched. Afterwards unplug
the D200 and plug it in again.

## Layouts per application

- One layout per application: `~/.config/ulanzi/apps/<application>.yaml`, `default.yaml` for all others.
- The application name is the window class without prefix: `org.kde.konsole` → `konsole.yaml`. The names are shown by
  `journalctl --user -u d200-focus -f` (e.g. `focus: gimp -> default`).
- **Only edit the files in `apps/`.** `config.yaml` is overwritten on every switch.
- A changed file is picked up the next time its layout is selected, immediately with
  `systemctl --user restart d200-focus`.
- Broken layouts are rejected and the current one stays active. The error message is in the journal of `d200-focus`.
- Comments (`#`) and blank lines are allowed and are kept.
- The application launcher, KRunner and Plasma dialogs count as windows too and switch to `default`.

A switch takes about 0.4 s (300 ms delay against intermediate Alt+Tab steps, validation, daemon restart).

### Keys

Numbered row by row from 0 at the top left (0–4, 5–9, 10–12, 13 = wide display). The position in the `buttons:` list
determines the key.

An empty key needs the black image `blank.png`. With `null` the daemon does not send the key at all, and the device
keeps showing the image from the previous layout. `enabled: false` alone is rejected by the validator (image missing).
For disabled keys the daemon shows `background_tile`. This is the format the web UI writes and accepts as well. The
variant `image` + `action_enabled: false` is accepted by the daemon, but the web UI then refuses to save ("Botão N:
preencha cmd").
Key 13 (wide display) stays `null`, then the firmware shows its clock (see "Clock on black").

```yaml
# 7: empty
- enabled: false
  background_tile: ./icons/blank.png
```

The web UI only writes `config.yaml`, which d200-focus overwrites again on the next window switch. It is therefore only
useful for trying things out. Anything that should stay belongs in `apps/<application>.yaml`.

```yaml
buttons:

# 3: previous track
- image: ./icons/media-previous.png
  label: ''
  action: command
  params:
    cmd: ~/.local/bin/d200-key previoussong
```

`d200-key` knows all names from `/usr/include/linux/input-event-codes.h` without `KEY_` (e.g. `f1`, `enter`,
`playpause`, `nextsong`) plus the short forms `ctrl`, `shift`, `alt`, `altgr`, `super`.
The names are scancodes of the US keyboard, other keyboard layouts remap them: on a German layout `y` gives **Z** and
vice versa (undo in GIMP is therefore `ctrl+y` in my layouts). The same applies to special characters.

Other actions: `app` (launch an application, `params: {name: firefox}`), `command` (any command), `obs`.

### Icons from applications

Many applications ship their toolbar icons as SVG. `d200-icon` draws such an icon on black and optionally writes the
function name below it (`|` = new line); with `-` instead of an SVG it becomes a text-only key. The text is part of the
image because the firmware draws labels in only one font size per layout – set `ShowTitle: false` in the layout.
JetBrains IDEs keep them in `lib/app-client.jar` under `expui/` (variant `_dark` for the black background), the icons
of the old UI without `expui/` – useful when the new UI has no icon for a function any more. KDE applications keep them
in `/usr/share/icons/breeze-dark/actions/`.

```bash
J=~/apps/pycharm/lib/app-client.jar
unzip -l $J | grep -i 'expui/run/.*_dark.svg'      # find names
./d200-icon "$J!expui/run/resume_dark.svg" my-layouts/icons/pycharm-resume.png Resume
./d200-icon - my-layouts/icons/pycharm-usages.png "Find|Usages"
```

### Clock on black

The firmware clock is drawn on the image that was last sent as the wide display's background. After standby and
plug-in that is the Ulanzi logo again. `d200-focus` therefore sends `~/.config/ulanzi/wide-black.yaml` first at start,
after resume (logind `PrepareForSleep`) and on plug-in (udev → `d200-wide-black.service` → D-Bus method `prime`), and
then the actual layout again. The keys switch immediately, the clock appears after about 3–4 s. No change to the
ulanzi-d200-linux code is needed; manually: `systemctl --user start d200-wide-black`.

## Pitfalls

- **The web UI** is in Portuguese only (Firefox's page translation is enough). It does not know `icon_spec` and drops
  `icon_spec` and all comments when saving. With `d200-focus` it is only useful for viewing anyway.
- **`icon_spec`** (text images generated by the daemon, `icons/button_icon_<n>.png`): rename the generated images and
  reference them via `image:`.
- **`ulanzi-manager validate`** run directly in `apps/` reports missing images, because `./icons/` is resolved relative
  to the file. Copy the file to `~/.config/ulanzi/` to validate it.
- **Wide display (13):** without an entry the firmware shows its clock on the last stored background, after standby or
  plug-in on the Ulanzi logo (fix see "Clock on black"). With an entry the tool only allows an image, a GIF or the
  system stats, and the firmware clock is gone. An attempt to show the clock on a custom background (`SmallViewMode` 1
  with an image) crashed the firmware back to factory state; a daemon restart restores everything.
- **Without the daemon** the wide key sends a built-in keyboard macro (link `www.ulanzistudio.com` or a screenshot),
  because the D200 also registers as a USB keyboard.
- **The daemon does not reload `config.yaml` by itself**, only at start (`systemctl --user restart ulanzi-daemon`).

## License

MIT, see [LICENSE](LICENSE).

# ulanzi-d200-tools

*English: [README.md](README.md)*

Der **Ulanzi D200** ist ein Stream-Controller: ein kleines Tastenfeld für den Schreibtisch mit 13 Display-Tasten und
einem breiten Display. [racerxdl/ulanzi-d200-linux](https://github.com/racerxdl/ulanzi-d200-linux) macht ihn unter
Linux nutzbar. Dieses Projekt ergänzt, was ich darüber hinaus unter KDE Plasma 6 mit Wayland gebraucht habe: Tasten,
die Tastenkombinationen senden (per `ydotool`, weil `xdotool` unter Wayland nicht funktioniert), und Tastenbelegungen,
die automatisch mit dem Programm im Vordergrund wechseln – zum Beispiel Debugger-Tasten in PyCharm und Werkzeug-Tasten
in GIMP.

Es ist mein persönliches Setup (Kubuntu 26.04, Plasma 6, Wayland) und wird so geteilt, wie es ist. Die Skripte sind
klein und sollten sich leicht anpassen lassen.

## Inhalt

| Datei | Zweck |
|---|---|
| `d200-key` | sendet eine Tastenkombination wie `ctrl+shift+f1` per `ydotool` (Ersatz für die Aktion `key`, die `xdotool` braucht und unter Wayland nicht geht) |
| `d200-icon` | rendert ein SVG-Icon eines Programms (Datei oder aus einer JAR) und/oder den Funktionsnamen als 196×196-Tastenbild auf Schwarz; braucht `librsvg2-bin` |
| `d200-focus` | Dienst: wählt beim Fensterwechsel das Layout `~/.config/ulanzi/apps/<programm>.yaml`, prüft es, kopiert es auf `config.yaml` und startet den Daemon neu |
| `systemd/d200-focus.service` | User-Unit für `d200-focus` (startet mit der Plasma-Sitzung) |
| `systemd/d200-wide-black.service` | User-Unit, von udev beim Einstecken des D200 gestartet; lässt `d200-focus` den schwarzen Hintergrund neu schicken |
| `udev/99-d200-focus.rules` | udev-Regel, startet beim Einstecken `d200-wide-black.service` |
| `systemd/ulanzi-daemon.service.d/override.conf` | hebt die Neustart-Sperre von systemd für den Daemon auf (sonst nach 5 Neustarts in 10 s blockiert); `TimeoutStopSec=2`, weil der Daemon ein SIGTERM während seiner internen Neukonfiguration nach dem Einstecken verliert und systemd sonst 90 s bis zum Kill wartet |
| `my-layouts/apps/*.yaml` | Tastenbelegung je Programm (`default.yaml`, `konsole.yaml`, ...) |
| `my-layouts/wide-black.yaml` | Hilfslayout: nur schwarzer Hintergrund für das große Display (siehe „Uhr auf Schwarz“) |
| `my-layouts/icons/*.png` | Tastenbilder (196×196, `blank-wide.png` 458×196) |
| `ulanzi-d200-feature-proposals.md` | Vorschläge an den Autor von ulanzi-d200-linux (englisch) |
| `ulanzi-d200-issues.md` | GitHub-Issue-Texte daraus (englisch): kompakte Variante für den Erstkontakt, ausführliche Einzel-Issues für Rückfragen |

Skripte und Units sind nach `~/.local/bin` bzw. `~/.local/share/systemd/user` verlinkt, `my-layouts/apps`, `my-layouts/icons`
und `my-layouts/wide-black.yaml` nach `~/.config/ulanzi/`. Änderungen an Layouts und Bildern landen dadurch direkt im
Repo.

`~/.config/ulanzi/layouts/` ist dagegen der Ordner, in dem die Web-GUI ihre gespeicherten Layouts ablegt
(Dateinamen = sha256). Er gehört nicht zu diesem Projekt und ist bewusst kein Link – deshalb heißt der Ordner dieses
Projekts `my-layouts`.

Die Unit-Links liegen bewusst nicht in `~/.config/systemd/user`: Dort gilt ein Symlink auf eine Datei außerhalb der
Suchpfade als „gelinkte“ Unit, und `systemctl --user disable` löscht ihn mit – danach meldet systemd „Unit does not
exist“. Den Link in `~/.local/share/systemd/user` lässt `disable` stehen. `enable` legt in `~/.config/systemd/user`
trotzdem zusätzlich einen Link an, den `disable` wieder entfernt; das ist normal.

## Wo liegt was

| Was | Ort | Nach Neuinstallation |
|---|---|---|
| ydotool (inkl. `ydotoold` und User-Unit `ydotool.service`) | apt-Paket | neu installieren |
| udev-Regel (Zugriff auf `hidraw`) | `/etc/udev/rules.d/99-ulanzi.rules` | aus dem ulanzi-d200-linux-Repo kopieren |
| ulanzi-d200-linux-Klon | z. B. `~/Projekte/ulanzi-d200-linux` | bleibt (Datenpartition) |
| venv, Wrapper | `~/.local/ulanzi/venv`, `~/.local/bin/ulanzi-daemon` | `install.sh` legt beides neu an |
| Dienste `ulanzi-daemon`, `ulanzi-web` | `~/.config/systemd/user/` | `install.sh` legt sie neu an |
| Skripte, `d200-focus`-Units, Layouts, Bilder | dieses Projekt | Symlinks neu anlegen |

## Installation

`T` und den Pfad des ulanzi-d200-linux-Klons an das eigene System anpassen.

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

`install.sh` überschreibt keine vorhandene `config.yaml` und lässt das verlinkte `icons` unverändert. Danach den D200
einmal ab- und wieder anstecken.

## Layouts je Programm

- Ein Layout pro Programm: `~/.config/ulanzi/apps/<programm>.yaml`, für alle anderen `default.yaml`.
- Der Programmname ist die Fensterklasse ohne Präfix: `org.kde.konsole` → `konsole.yaml`. Die Namen zeigt
  `journalctl --user -u d200-focus -f` (z. B. `focus: gimp -> default`).
- **Nur die Dateien in `apps/` bearbeiten.** `config.yaml` wird bei jedem Wechsel überschrieben.
- Eine geänderte Datei wird beim nächsten Wechsel zu diesem Layout übernommen, oder sofort mit
  `systemctl --user restart d200-focus`.
- Fehlerhafte Layouts werden abgelehnt, das bisherige bleibt aktiv. Die Fehlermeldung steht im Journal von `d200-focus`.
- Kommentare (`#`) und Leerzeilen sind erlaubt und bleiben erhalten.
- Startmenü, KRunner und Plasma-Dialoge zählen auch als Fenster und schalten auf `default`.

Ein Wechsel dauert etwa 0,4 s (300 ms Wartezeit gegen Alt+Tab-Zwischenschritte, Prüfung, Daemon-Neustart).

### Tasten

Nummern zeilenweise ab 0 oben links (0–4, 5–9, 10–12, 13 = großes Display). Die Position in der Liste `buttons:`
bestimmt die Taste.

Eine leere Taste braucht das schwarze Bild `blank.png`. Bei `null` überträgt der Daemon die Taste gar nicht, und das
Gerät zeigt weiter das Bild aus dem vorherigen Layout. `enabled: false` allein lehnt der Validator ab (Bild fehlt).
Bei deaktivierten Tasten zeigt der Daemon `background_tile` an. Das ist das Format, das auch die Web-GUI
schreibt und akzeptiert. Die Variante `image` + `action_enabled: false` nimmt der Daemon zwar an, die GUI lehnt
dann aber das Speichern ab („Botão N: preencha cmd“).
Taste 13 (großes Display) bleibt `null`, dann zeigt die Firmware ihre Uhr (siehe „Uhr auf Schwarz“).

```yaml
# 7: empty
- enabled: false
  background_tile: ./icons/blank.png
```

Die Web-GUI schreibt nur in `config.yaml`, die d200-focus beim nächsten Fensterwechsel wieder überschreibt. Sie
taugt deshalb nur zum Ausprobieren. Was bleiben soll, gehört in `apps/<programm>.yaml`.

```yaml
buttons:

# 3: previous track
- image: ./icons/media-previous.png
  label: ''
  action: command
  params:
    cmd: ~/.local/bin/d200-key previoussong
```

`d200-key` kennt alle Namen aus `/usr/include/linux/input-event-codes.h` ohne `KEY_` (z. B. `f1`, `enter`,
`playpause`, `nextsong`) und die Kurzformen `ctrl`, `shift`, `alt`, `altgr`, `super`.
Die Namen sind Scancodes der US-Tastatur, andere Tastaturlayouts bilden sie um: Beim deutschen Layout ergibt `y` ein
**Z** und umgekehrt (Undo in GIMP ist in meinen Layouts deshalb `ctrl+y`). Bei Sonderzeichen gilt das ebenso.

Weitere Aktionen: `app` (Programm starten, `params: {name: firefox}`), `command` (beliebiger Befehl), `obs`.

### Icons aus Programmen

Viele Programme haben ihre Symbolleisten-Icons als SVG dabei. `d200-icon` zeichnet so ein Icon auf Schwarz und schreibt
optional den Funktionsnamen darunter (`|` = neue Zeile); mit `-` statt SVG wird es eine reine Text-Taste. Der Text steckt
im Bild, weil die Firmware Labels nur mit einer Schriftgröße je Layout zeichnet – im Layout dann `ShowTitle: false`.
Bei JetBrains-IDEs liegen sie in `lib/app-client.jar` unter `expui/` (Variante `_dark` für den schwarzen Hintergrund),
die der alten Oberfläche ohne `expui/` – nützlich, wenn die neue für eine Funktion kein Icon mehr hat. Bei
KDE-Programmen liegen sie in `/usr/share/icons/breeze-dark/actions/`.

```bash
J=~/apps/pycharm/lib/app-client.jar
unzip -l $J | grep -i 'expui/run/.*_dark.svg'      # find names
./d200-icon "$J!expui/run/resume_dark.svg" my-layouts/icons/pycharm-resume.png Resume
./d200-icon - my-layouts/icons/pycharm-usages.png "Find|Usages"
```

### Uhr auf Schwarz

Die Firmware-Uhr liegt auf dem Bild, das zuletzt als Hintergrund des großen Displays ins Gerät kam. Nach Standby und
Einstecken ist das wieder das Ulanzi-Logo. `d200-focus` schickt deshalb beim Start, nach dem Aufwachen (logind
`PrepareForSleep`) und beim Einstecken (udev → `d200-wide-black.service` → D-Bus-Methode `prime`) zuerst
`~/.config/ulanzi/wide-black.yaml` und danach wieder das eigentliche Layout. Die Tasten wechseln sofort, die Uhr erscheint
nach etwa 3–4 s. Ohne Änderung am ulanzi-d200-linux-Code; von Hand: `systemctl --user start d200-wide-black`.

## Fallstricke

- **Web-UI** ist fest auf Portugiesisch (Firefox-Übersetzung reicht). Sie kennt `icon_spec` nicht und verwirft beim
  Speichern `icon_spec` und alle Kommentare. Mit `d200-focus` ist sie ohnehin nur zum Ansehen sinnvoll.
- **`icon_spec`** (vom Daemon erzeugte Textbilder, `icons/button_icon_<n>.png`): erzeugte Bilder umbenennen und per
  `image:` eintragen.
- **`ulanzi-manager validate`** direkt in `apps/` meldet fehlende Bilder, weil `./icons/` relativ zur Datei aufgelöst
  wird. Zum Prüfen nach `~/.config/ulanzi/` kopieren.
- **Großes Display (13):** Ohne Eintrag zeigt die Firmware ihre Uhr auf dem zuletzt gespeicherten Hintergrund, nach
  Standby oder Einstecken auf dem Ulanzi-Logo (Abhilfe siehe „Uhr auf Schwarz“). Mit Eintrag erlaubt das Tool nur
  Bild, GIF oder Systemanzeige, die Firmware-Uhr geht dann nicht. Ein Versuch, die Uhr auf eigenem Hintergrund zu zeigen
  (`SmallViewMode` 1 mit Bild), hat die Firmware in den Werkszustand gestürzt; ein Daemon-Neustart stellt alles wieder her.
- **Ohne Daemon** schickt die große Taste ein eingebautes Tastaturmakro (Link `www.ulanzistudio.com` bzw. Screenshot),
  weil sich der D200 zusätzlich als USB-Tastatur meldet.
- **Daemon lädt `config.yaml` nicht selbst neu**, nur beim Start (`systemctl --user restart ulanzi-daemon`).

## Lizenz

MIT, siehe [LICENSE](LICENSE).

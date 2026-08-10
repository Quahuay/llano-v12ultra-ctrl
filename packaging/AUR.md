# Arch-Paket bauen und (optional) im AUR veröffentlichen

Diese Anleitung ist bewusst vollständig und eigenständig, damit sie ohne fremde Hilfe
funktioniert. Sie hat zwei getrennte Teile:

- **Teil A: lokal bauen und installieren.** Braucht kein AUR-Konto und keine
  AUR-Verfügbarkeit. Das ist der Weg, der immer funktioniert.
- **Teil B: im AUR veröffentlichen.** Optional, nur damit andere Arch-Nutzer das Paket per
  `yay -S llano-v12ultra-ctrl` bekommen. Status aktuell: TBD (noch nicht eingereicht).

Alles hier wird gegen [`PKGBUILD`](PKGBUILD) in diesem Verzeichnis ausgeführt.

---

## Teil A: lokal bauen und installieren (ohne AUR)

Voraussetzung: ein Arch-basiertes System (Arch, EndeavourOS, Manjaro, CachyOS, ...).

### A1. Build-Werkzeuge installieren

```bash
sudo pacman -S --needed base-devel git python-build python-installer python-wheel
```

### A2. PKGBUILD holen

```bash
git clone https://github.com/Quahuay/llano-v12ultra-ctrl.git
cd llano-v12ultra-ctrl/packaging
```

### A3. Prüfsumme setzen

Das `PKGBUILD` steht bewusst auf `sha256sums=('SKIP')`, solange es noch kein getaggtes Release
gibt. Sobald ein Release existiert, einmalig:

```bash
updpkgsums          # aus dem Paket pacman-contrib, setzt die echte Prüfsumme ein
```

Falls `updpkgsums` fehlt: `sudo pacman -S pacman-contrib`.

### A4. Bauen und installieren

```bash
makepkg -si
```

`-s` zieht fehlende Abhängigkeiten automatisch, `-i` installiert das Ergebnis danach. Wer nur die
Paketdatei will, ohne zu installieren, nimmt `makepkg` ohne Flags. Das Ergebnis ist dann eine
`.pkg.tar.zst`-Datei im selben Verzeichnis, installierbar per:

```bash
sudo pacman -U llano-v12ultra-ctrl-*.pkg.tar.zst
```

### A5. udev-Regel scharfschalten

Das Paket legt die Regel nach `/usr/lib/udev/rules.d/` ab. udev übernimmt sie beim nächsten
Geräte-Event automatisch. Wenn das Pad schon eingesteckt war, einmalig nachhelfen:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG plugdev "$USER"   # danach neu einloggen
```

### A6. Testen

```bash
llano-v12ultra-ctrl status
llano-v12ultra-ctrl-gui
```

### A7. Ohne Arch-Maschine bauen (Docker/Podman)

Praktisch, wenn gerade kein Arch-System verfügbar ist, aber Docker oder Podman läuft. Getestet
wird damit der Build, nicht die Hardware-Ansteuerung (der Container hat keinen Zugriff auf das
USB-Gerät):

```bash
cd llano-v12ultra-ctrl
docker run --rm -it -v "$PWD":/src -w /src archlinux:latest bash -c '
  pacman -Sy --noconfirm base-devel python-build python-installer python-wheel python-pyqt6 git
  useradd -m builder && chown -R builder:builder /src
  cp packaging/PKGBUILD . && chown builder:builder PKGBUILD
  su builder -c "makepkg --noconfirm --skipchecksums"
  ls -la *.pkg.tar.zst
'
```

Die entstandene `.pkg.tar.zst` liegt danach im Projektverzeichnis und lässt sich auf ein echtes
Arch-System kopieren und dort per `sudo pacman -U ...` installieren.

---

## Teil B: im AUR veröffentlichen (optional)

Nur nötig, wenn das Paket öffentlich als `yay -S llano-v12ultra-ctrl` verfügbar sein soll. Für die
eigene Nutzung reicht Teil A vollständig aus.

Wichtig vorab: **im AUR liegt nur das `PKGBUILD`, nicht der Quellcode.** Das AUR-Repo ist ein
winziges Git-Repo mit im Wesentlichen zwei Dateien (`PKGBUILD` und `.SRCINFO`). Der eigentliche
Code wird beim Bauen vom GitHub-Release heruntergeladen.

### B0. Voraussetzung: ein getaggtes GitHub-Release

Das `PKGBUILD` lädt seinen Quellcode von
`https://github.com/Quahuay/llano-v12ultra-ctrl/archive/refs/tags/v$pkgver.tar.gz`. Diese URL muss
existieren, sonst schlägt jeder Build fehl. Also zuerst ein Release taggen:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Das löst zugleich den [`release.yml`](../.github/workflows/release.yml) Workflow aus, der die
Installer für alle Plattformen baut.

### B1. AUR-Konto anlegen

Registrieren unter https://aur.archlinux.org/register mit Benutzername und E-Mail. Danach die
E-Mail-Bestätigung abschließen. Kein Zahlungsmittel, keine weitere Verifikation nötig.

### B2. Eigenen SSH-Schlüssel erzeugen

Bewusst ein eigener Schlüssel, nicht der GitHub-Schlüssel:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aur -C "aur-llano-v12ultra-ctrl"
```

### B3. Öffentlichen Schlüssel im AUR hinterlegen

Inhalt anzeigen und kopieren:

```bash
cat ~/.ssh/aur.pub
```

Auf https://aur.archlinux.org einloggen, dann "My Account", das Feld "SSH Public Key" befüllen und
mit "Update" speichern.

### B4. SSH-Konfiguration ergänzen

An `~/.ssh/config` anhängen:

```
Host aur.archlinux.org
    IdentityFile ~/.ssh/aur
    User aur
```

Verbindung prüfen:

```bash
ssh aur@aur.archlinux.org help
```

Bei Erfolg antwortet der Server mit einer Liste verfügbarer Kommandos. Eine Shell gibt es dort
nicht, das ist normal und kein Fehler.

### B5. AUR-Repo klonen

Für ein noch nicht existierendes Paket ist das Repo leer. Der Klon warnt entsprechend, das ist
korrekt so:

```bash
git clone ssh://aur@aur.archlinux.org/llano-v12ultra-ctrl.git aur-llano
cd aur-llano
```

### B6. PKGBUILD und .SRCINFO einspielen

`.SRCINFO` ist eine maschinenlesbare Zusammenfassung des `PKGBUILD`. Das AUR **lehnt Pushes ohne
sie ab**, und sie muss bei jeder Änderung am `PKGBUILD` neu erzeugt werden:

```bash
cp ../llano-v12ultra-ctrl/packaging/PKGBUILD .
makepkg --printsrcinfo > .SRCINFO
```

Ohne Arch-Maschine geht das auch im Container:

```bash
docker run --rm -v "$PWD":/pkg -w /pkg archlinux:latest bash -c '
  pacman -Sy --noconfirm base-devel
  useradd -m builder && chown -R builder:builder /pkg
  su builder -c "makepkg --printsrcinfo" > .SRCINFO
'
```

### B7. Vor dem Push lokal gegenprüfen

Erst prüfen, dann veröffentlichen. Ein kaputtes AUR-Paket ärgert fremde Nutzer:

```bash
namcap PKGBUILD                     # statische Prüfung, aus dem Paket "namcap"
makepkg -si                         # baut und installiert wirklich durch
llano-v12ultra-ctrl status          # Funktionstest gegen echte Hardware
```

### B8. Push ins AUR

```bash
git add PKGBUILD .SRCINFO
git commit -m "Initial upload: llano-v12ultra-ctrl 0.1.0"
git push origin master
```

Der Branch heißt im AUR `master`, nicht `main`. Beim ersten Push wird das Paket automatisch
angelegt, es gibt kein separates Formular dafür.

Danach ist es erreichbar unter
`https://aur.archlinux.org/packages/llano-v12ultra-ctrl` und installierbar per
`yay -S llano-v12ultra-ctrl`.

### B9. Bei jedem neuen Release aktualisieren

```bash
cd aur-llano
# pkgver im PKGBUILD auf die neue Version setzen, pkgrel wieder auf 1
updpkgsums                          # neue Prüfsumme des Release-Tarballs
makepkg --printsrcinfo > .SRCINFO   # nicht vergessen, sonst lehnt das AUR den Push ab
git commit -am "Update to 0.2.0"
git push origin master
```

---

## Warum das nicht automatisch per GitHub Actions läuft

Technisch möglich (der AUR-Push bräuchte den privaten SSH-Schlüssel als GitHub-Secret), aber
bewusst nicht eingerichtet:

- Ein privater Schlüssel mit Schreibrecht auf ein öffentliches Paket gehört nicht ohne Not in
  einen CI-Runner.
- Solange das Packaging noch nirgends Ende-zu-Ende bestätigt ist (siehe Paket-Status im README),
  wäre ein automatischer Push in ein öffentliches Repository der falsche Zeitpunkt.

Sinnvoll wird die Automatisierung, sobald ein oder zwei Releases sauber durchgelaufen sind. Bis
dahin sind die paar Handgriffe aus B9 pro Release der ehrlichere Weg.

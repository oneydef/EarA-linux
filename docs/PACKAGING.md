# Install

Pre-built packages: [GitHub Releases](https://github.com/oneydef/EarA-linux/releases)

| Format | Install |
|--------|---------|
| Debian / Ubuntu | `sudo dpkg -i eara_*_all.deb` |
| Fedora / RHEL | `sudo dnf install ./eara-*.rpm` |
| AppImage | `chmod +x EarA-*.AppImage && ./EarA-*.AppImage gui` |
| From source | `./scripts/install-user.sh` then `eara gui` (see [README](../README.md)) |

## Flatpak

When published on Flathub:

```bash
flatpak install flathub io.github.oneydef.eara
flatpak run io.github.oneydef.eara
```

## GNOME Software

After installing the `.deb`, search for **Nothing X**, **Nothing Ears**, or **EarA** in GNOME Software.

## Arch Linux

A `PKGBUILD` for packagers is in [`packaging/arch/`](../packaging/arch/). Build locally with `makepkg -si` until the package is published on the AUR.

## Dependencies

- Python 3.10+
- GTK 4, libadwaita, PyGObject, python3-dbus
- BlueZ, PulseAudio or PipeWire

```bash
sudo apt install python3 python3-gi python3-dbus gir1.2-gtk-4.0 gir1.2-adw-1 bluez
```

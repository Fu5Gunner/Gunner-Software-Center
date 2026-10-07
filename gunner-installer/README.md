# Gunner Installer

A KDE Plasma GUI for installing, updating and managing a curated list of programs
(AUR, official repos, Flatpak) on CachyOS.

## Install

    ./install.sh

This builds a `gunner-installer` pacman package from the files in this folder and installs it.
Afterwards launch **Gunner Installer** from the application menu, or run `gunner-installer`.

Uninstall with `./install.sh --uninstall` (or `sudo pacman -Rns gunner-installer`).

## Your program list

The package ships a default list at `/usr/share/gunner-installer/programs.json`.
To use your own, copy it to `~/.config/gunner-installer/programs.json` and edit that copy;
it takes priority. Your own icons can go in `~/.config/gunner-installer/icons/<id>.png`.

## Releasing an update

Edit the files in this folder, bump `pkgver` (or `pkgrel`) in `PKGBUILD`, and run `./install.sh` again.

## Upgrading from the old name

This project used to be called `cachyos-installer`. Running `./install.sh` removes the old
package and moves `~/.config/cachyos-installer` to `~/.config/gunner-installer`, so your own
program list and icons carry over.

## programs.json fields

`id`, `name`, `description`, `category`, `source` (`aur`, `repo` or `flatpak`), `package`, and optionally
`launch`, `cli` (true for command-line tools, which hides the Launch button), `icon` (file or URL), `icon_repo`, and `download_page` (for programs the vendor ships as a
`.flatpak` file instead of on Flathub). `category` is one of Gaming, Internet, Development,
Multimedia, Office, Security, Utilities or System (anything else, or nothing, is shown under "Other").
If you keep your own copy in `~/.config/gunner-installer/`, add `category` to its entries to get them
grouped on the Install tab.

## Versioning

Semantic Versioning: new features bump the minor version, bug fixes bump the patch version.
See `CHANGELOG.md`. The version is set once, in `gunner_installer.py`; run `gunner-installer --version` to see it.

## Setup notes for some programs

* Tailscale: run `sudo systemctl enable --now tailscaled`, then `sudo tailscale up`.
* KDE Connect: open TCP and UDP ports 1714-1764 if you use a firewall.
* lsfg-vk: needs Lossless Scaling from Steam (for `Lossless.dll`).
* xemu and Unreal Tournament 2004: you need to provide your own BIOS / game files.

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

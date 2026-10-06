# Changelog

Gunner Installer uses Semantic Versioning (MAJOR.MINOR.PATCH): a new feature bumps the
minor version (1.1.0 -> 1.2.0), a bug fix bumps the patch version (1.1.0 -> 1.1.1).
The version lives in one place, `__version__` in `gunner_installer.py`; the PKGBUILD reads it.
Check the installed version with `gunner-installer --version`.

Each version opens with a short summary paragraph, followed by the sections that apply:
Added (new features and programs), Updated (changed items, written as name (old) -> (new))
and Patched (fixes). Every item gets its own bullet.

## 1.4.0

The category filter moves into a left-hand sidebar in the style of a software center, with a Discover section and an icon for each category.

### Added

* Left sidebar on the Install tab with Discover and Categories sections
* Category icons from your icon theme

### Updated

* Category filter (row of chips above the cards) -> (sidebar list on the left)
* Default window size (860 x 680) -> (1020 x 680)

## 1.3.0

A more compact Install tab: shorter cards in three columns, so more programs fit on screen.

### Updated

* Install tab program cards (2 columns, 64 px icons, 104 px minimum height) -> (3 columns, 48 px icons, 64 px minimum height)
* Card summaries (full wrapped text) -> (up to two lines with an ellipsis, full text on hover)
* Card status (sentence under the summary) -> (short badge beside the name, full text on hover)

## 1.2.3

A formatting update to the changelog. The app itself is unchanged.

### Patched

* changelog format to use Added, Updated and Patched sections with plain bullets

## 1.2.2

A wording update to the changelog. The app itself is unchanged.

### Patched

* changelog format so new features start with "Add", patches start with "Patch", and each version opens with a summary paragraph

## 1.2.1

A formatting fix to the changelog. The app itself is unchanged.

### Patched

* changelog so every new item has its own bullet

## 1.2.0

Four new programs join the catalog.

### Added

* Bitwarden
* LocalSend
* Yubico Authenticator
* Proton VPN

## 1.1.0

Categories and search make the Install tab easier to browse as the catalog grows.

### Added

* Category filter chips on the Install tab, driven by a new `category` field in `programs.json`
* Search bar on the Install tab that matches name, id, description and category
* Ticked-program count on the "Install selected" button

## 1.0.0

The first stable release: install, update and manage a curated list of programs from one KDE Plasma app, packaged as a normal pacman package.

### Added

* Card-style Install tab
* Manage tab with launch, update and uninstall
* Update checks
* paru/yay check that offers to install them on first run
* Automatic program icons
* Optional-dependency dialog
* Packaging as the `gunner-installer` pacman package with a menu entry and icon
* CurseForge
* Amethyst Mod Manager
* ClamUI
* Vesktop

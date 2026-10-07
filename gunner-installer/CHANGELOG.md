# Changelog

Gunner Installer uses Semantic Versioning (MAJOR.MINOR.PATCH): a new feature bumps the
minor version (1.1.0 -> 1.2.0), a bug fix bumps the patch version (1.1.0 -> 1.1.1).
The version lives in one place, `__version__` in `gunner_installer.py`; the PKGBUILD reads it.
Check the installed version with `gunner-installer --version`.

Each version opens with a short summary paragraph, followed by the sections that apply:
Added (new features and programs), Updated (changed items, written as name (old) -> (new))
and Patched (fixes). Every item gets its own bullet.

## 1.7.1

Installing JDownloader could get stuck compiling Qt documentation, because its optional
dependency phantomjs pulled qt5-webkit and qt5-doc from the AUR. AUR-only optional
dependencies are now skipped, and JDownloader is installed from the official repos.

### Updated

* JDownloader (AUR) -> (repo)

### Patched

* install of JDownloader getting stuck building qt5-doc, by skipping AUR-only optional
  dependencies such as phantomjs

## 1.7.0

Eighteen new programs join the catalog, from office tools and emulators to game launchers. Flatpak installs are now more reliable, and command-line tools no longer get a Launch button.

### Added

* lsfg-vk
* FileZilla
* Heroic Games Launcher
* LibreOffice
* Prism Launcher
* VLC
* Thunderbird
* Tailscale
* KDE Connect
* Remmina
* 7-Zip
* Vintage Story
* yt-dlp
* RetroArch
* 2009scape
* xemu
* Unreal Tournament 2004 Launcher
* Space Cadet Pinball
* Optional `cli` field in `programs.json` for command-line tools
* Automatic Flatpak install when a selected program needs it

### Updated

* Flathub Flatpak installs (system-wide, Flathub remote assumed) -> (per-user, Flathub remote added automatically)
* Flatpak update checks (default installation only) -> (default and per-user installations)

## 1.6.1

Uninstalling repo and AUR programs could fail with repeated "Sorry, try again" password errors. It now asks for your password through the system's own polkit dialog.

### Patched

* uninstall of repo and AUR programs failing with repeated password errors, now using the polkit (pkexec) password dialog

## 1.6.0

The official Hytale Launcher joins the catalog, along with support for programs that are distributed as a .flatpak file on the vendor's own site instead of Flathub.

### Added

* Hytale Launcher
* Install flow for vendor .flatpak files (open the official download page, then choose the downloaded file)
* Optional `download_page` field in `programs.json` for programs distributed that way

## 1.5.0

Nine new programs join the catalog, covering browsers, downloads and game launchers.

### Added

* JDownloader
* qBittorrent
* Faugus Launcher
* Lutris
* Steam
* Tor Browser
* Firefox
* Waterfox
* Brave

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

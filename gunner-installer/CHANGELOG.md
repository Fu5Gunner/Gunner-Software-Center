# Changelog

Gunner Installer uses Semantic Versioning (MAJOR.MINOR.PATCH): a new feature bumps the
minor version (1.1.0 -> 1.2.0), a bug fix bumps the patch version (1.1.0 -> 1.1.1).
The version lives in one place, `__version__` in `gunner_installer.py`; the PKGBUILD reads it.
Check the installed version with `gunner-installer --version`.

## 1.1.0
- Categories: filter chips on the Install tab, driven by a new `category` field in `programs.json`.
- Search bar on the Install tab (name, id, description and category).
- "Install selected" button shows how many programs are ticked.

## 1.0.0
- First stable release: card-style Install tab, Manage tab (launch, update, uninstall),
  update checks, paru/yay check and install, automatic program icons, dependency dialog.
- Packaged as the `gunner-installer` pacman package with a menu entry and icon.
- Catalog: CurseForge, Amethyst Mod Manager, ClamUI, Vesktop.

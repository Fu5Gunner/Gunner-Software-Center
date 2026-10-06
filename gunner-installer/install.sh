#!/usr/bin/env bash
# Build and install the Gunner Installer as a normal pacman package.
#   ./install.sh              build + install (or upgrade)
#   ./install.sh --uninstall  remove it again
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ "$EUID" -eq 0 ]; then
  echo "Run this as your normal user, not root (it asks for sudo when needed)." >&2
  exit 1
fi
command -v pacman >/dev/null || { echo "pacman not found: this is for CachyOS/Arch." >&2; exit 1; }

if [ "${1:-}" = "--uninstall" ]; then
  sudo pacman -Rns gunner-installer
  exit 0
fi

# Coming from the old "cachyos-installer" name: remove that package and keep your settings.
if pacman -Qq cachyos-installer >/dev/null 2>&1; then
  echo "Removing the old 'cachyos-installer' package (it was renamed to gunner-installer)..."
  sudo pacman -Rns cachyos-installer
fi
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"
if [ -d "$cfg/cachyos-installer" ] && [ ! -e "$cfg/gunner-installer" ]; then
  mv "$cfg/cachyos-installer" "$cfg/gunner-installer"
  echo "Moved your settings to $cfg/gunner-installer"
fi

sudo pacman -S --needed base-devel
makepkg -si "$@"
echo
echo "Installed. Launch it from the application menu ('Gunner Installer') or run: gunner-installer"

#!/usr/bin/env python3
"""Gunner Installer (KDE Plasma / PyQt6).

Installs programs listed in programs.json using paru/yay (repo + AUR) or flatpak.
Required dependencies are resolved automatically by the package manager.
Optional ("recommended") dependencies are looked up and offered in a dialog,
pre-ticked, and installed as dependencies (--asdeps).

Requires: python-pyqt6, paru (ships with CachyOS) or yay, kdialog (for the
password prompt; part of a normal KDE Plasma install).
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from urllib.parse import quote, urljoin, urlparse

from PyQt6.QtCore import (
    QProcess, QProcessEnvironment, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout,
    QWidget,
)

__version__ = "1.6.1"  # Semantic Versioning: new features bump MINOR, bug fixes bump PATCH
APP_DIR = Path(__file__).resolve().parent  # where the app (and its default list) is installed
USER_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gunner-installer"
# A programs.json in ~/.config/gunner-installer/ overrides the one shipped with the app,
# so you can edit your list without touching (read-only) system files.
PROGRAMS_FILE = (USER_DIR / "programs.json"
                 if (USER_DIR / "programs.json").is_file() else APP_DIR / "programs.json")
ICON_DIRS = (USER_DIR / "icons", APP_DIR / "icons")
CACHE_DIR = Path.home() / ".cache" / "gunner-installer" / "icons"
ICON_SIZE = 48
COLUMNS = 3
CATEGORIES = ["Gaming", "Internet", "Development", "Multimedia",
              "Office", "Security", "Utilities", "System"]


# Icon-theme names for the sidebar entries (Breeze provides all of these on Plasma).
CATEGORY_ICONS = {
    "All": "view-list-icons", "Gaming": "applications-games",
    "Internet": "applications-internet", "Development": "applications-development",
    "Multimedia": "applications-multimedia", "Office": "applications-office",
    "Security": "security-high", "Utilities": "applications-utilities",
    "System": "applications-system", "Other": "applications-other",
}


def program_category(program):
    return program.get("category") or "Other"


def program_matches(program, category, text):
    """True if the program is in the category ("All" = any) and contains every search word."""
    if category != "All" and program_category(program) != category:
        return False
    haystack = " ".join([program["name"], program["id"], program.get("description", ""),
                         program_category(program)]).lower()
    return all(word in haystack for word in text.lower().split())
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def find_helper():
    for name in ("paru", "yay"):
        if shutil.which(name):
            return name
    return None


HELPERS = {"paru": "paru-bin", "yay": "yay-bin"}  # name -> AUR fallback package


def helper_install_cmd(name):
    """Shell command: try the repos first, fall back to building the -bin AUR package."""
    aur = HELPERS[name]
    return [
        "sh", "-c",
        f'sudo -A pacman -S --needed --noconfirm {name} || {{ '
        'sudo -A pacman -S --needed --noconfirm base-devel git && '
        'd=$(mktemp -d) && '
        f'git clone https://aur.archlinux.org/{aur}.git "$d/{aur}" && '
        f'cd "$d/{aur}" && makepkg -f --noconfirm && '
        'sudo -A pacman -U --noconfirm "$(ls *.pkg.tar.zst | grep -v -- -debug | head -n1)"; }',
    ]


def review_flags(helper):
    # Skip PKGBUILD review prompts (needed for unattended installs).
    if helper == "paru":
        return ["--skipreview"]
    return ["--answerdiff", "None", "--answerclean", "None"]


def make_askpass():
    """Tiny sudo askpass helper that shows a KDE password dialog."""
    path = Path(tempfile.mkdtemp(prefix="cachy-askpass-")) / "askpass.sh"
    path.write_text(
        '#!/bin/sh\n'
        'exec kdialog --title "Gunner Installer" '
        '--password "Password required to install packages"\n'
    )
    path.chmod(0o700)
    return path


def get_optdeps(helper, pkg):
    """Return [(name, description)] of not-yet-installed optional deps."""
    try:
        out = subprocess.run(
            [helper, "-Si", pkg], capture_output=True, text=True, timeout=60
        ).stdout
    except Exception:
        return []
    deps, capture = [], False
    for line in out.splitlines():
        if re.match(r"^Optional Deps\s*:", line):
            capture, value = True, line.split(":", 1)[1].strip()
        elif capture and line.startswith(" "):
            value = line.strip()
        else:
            capture = False
            continue
        if not value or value == "None" or "[installed]" in value:
            continue
        name, _, desc = value.partition(":")
        name = re.split(r"[<>=]", name.strip())[0]
        if name:
            deps.append((name, desc.strip()))
    return deps


class OptDepsDialog(QDialog):
    def __init__(self, program, deps, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Recommended dependencies for {program}")
        self.boxes = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{program} lists these optional dependencies.\n"
            "Untick anything you don't want."))
        for name, desc in deps:
            box = QCheckBox(f"{name} — {desc}" if desc else name)
            box.setChecked(True)
            box.dep_name = name
            self.boxes.append(box)
            layout.addWidget(box)
        buttons = QDialogButtonBox()
        buttons.addButton("Install selected", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Skip optional", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        if self.exec() != QDialog.DialogCode.Accepted:
            return []
        return [b.dep_name for b in self.boxes if b.isChecked()]


STYLE = """
QFrame#card {
    background: palette(base);
    border: 2px solid palette(midlight);
    border-radius: 12px;
}
QFrame#card:hover { border-color: palette(mid); }
QFrame#card[selected="true"] {
    border-color: palette(highlight);
    background: palette(alternate-base);
}
QLabel#cardTitle { font-size: 14pt; font-weight: bold; }
QLabel#cardStatus[kind="update"] { color: palette(highlight); font-weight: bold; }
QLabel#programTitle { font-size: 11pt; font-weight: bold; }
QLabel#cardSummary { font-size: 9pt; }
QLabel#cardBadge { font-size: 8pt; }
QLabel#cardBadge[kind="update"] { color: palette(highlight); font-weight: bold; }
QListWidget#sidebar { border: none; background: transparent; outline: 0; }
QListWidget#sidebar::item { padding: 6px 8px; border-radius: 6px; }
QListWidget#sidebar::item:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
}
"""


def placeholder_pixmap(name, size=ICON_SIZE):
    """Rounded coloured square with the program's first letter."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor.fromHsv(sum(map(ord, name)) % 360, 150, 190))
    painter.drawRoundedRect(0, 0, size, size, 14, 14)
    painter.setPen(Qt.GlobalColor.white)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(size // 2)
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, name[:1].upper())
    painter.end()
    return pm


def fit(pm, size=ICON_SIZE):
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


def local_icon(program):
    """Explicit local 'icon' path, or icons/<id>.(png|svg|webp|jpg)."""
    candidates = []
    icon = program.get("icon", "")
    if icon and not icon.startswith(("http://", "https://")):
        candidates += [USER_DIR / icon, APP_DIR / icon]
    for folder in ICON_DIRS:
        for ext in ("png", "svg", "webp", "jpg"):
            candidates.append(folder / f"{program['id']}.{ext}")
    for path in candidates:
        if path.is_file():
            pm = QPixmap(str(path))
            if not pm.isNull():
                return fit(pm)
    return None


BAD_ICON_WORDS = ("screenshot", "splash", "title-bar", "titlebar", "banner",
                  "preview", "wiki", "docs", "test", "game")


def pick_icon_path(paths, program):
    """Choose the most likely app icon from a list of repo file paths (or None)."""
    skip = {"manager", "mod", "the", "app"}
    tokens = {t for t in re.split(r"[^a-z0-9]+", f"{program['id']} {program['name']}".lower())
              if len(t) > 2 and t not in skip}
    best, best_score = None, 0.0
    for path in paths:
        low = path.lower()
        stem, _, ext = low.rsplit("/", 1)[-1].rpartition(".")
        if ext not in ("png", "svg", "webp", "jpg", "jpeg"):
            continue
        if any(w in low for w in BAD_ICON_WORDS):
            continue
        score = 0.0
        if any(t in stem for t in tokens):
            score += 5
        if "icon" in low:
            score += 3
        if stem in ("icon", "logo", "app-icon"):
            score += 2
        if ext == "svg":
            score += 1
        score -= low.count("/") * 0.1
        if score >= 5 and score > best_score:
            best, best_score = path, score
    return best


def cached_icon(program):
    """An icon previously downloaded for this program (see icon / icon_repo)."""
    if CACHE_DIR.is_dir():
        for f in CACHE_DIR.glob(f"{program['id']}.*"):
            pm = QPixmap(str(f))
            if not pm.isNull():
                return fit(pm)
    return None


def installed_package_icon(pkg):
    """Icon of an installed pacman package, via the Icon= line of its .desktop file."""
    for line in sh(["pacman", "-Ql", pkg], timeout=15).splitlines():
        path = line.split(" ", 1)[-1].strip()
        if not (path.endswith(".desktop") and "/applications/" in path):
            continue
        icon = ""
        try:
            for entry in Path(path).read_text(errors="replace").splitlines():
                if entry.startswith("Icon="):
                    icon = entry[5:].strip()
                    break
        except OSError:
            continue
        if not icon:
            continue
        if os.path.isabs(icon):
            pm = QPixmap(icon)
            if not pm.isNull():
                return fit(pm)
        else:
            themed = QIcon.fromTheme(icon)
            if not themed.isNull():
                return themed.pixmap(ICON_SIZE, ICON_SIZE)
    return None


def real_icon(program):
    """Icon from the installed app / system theme, or None."""
    if program.get("source", "aur") != "flatpak":
        pm = installed_package_icon(program["package"])
        if pm:
            return pm
    for name in (program["package"], program["id"]):
        themed = QIcon.fromTheme(name)
        if not themed.isNull():
            return themed.pixmap(ICON_SIZE, ICON_SIZE)
    return None


def pick_site_icon(html, base):
    """Best <link rel=...icon> URL from a web page (or None)."""
    best, best_score = None, 0.0
    for tag in re.findall(r"<link\b[^>]*>", html, re.I):
        rel = re.search(r'rel\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        href = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if not rel or not href:
            continue
        rel_l = rel.group(1).lower()
        if "icon" not in rel_l or "mask" in rel_l or href.group(1).startswith("data:"):
            continue
        url = urljoin(base, href.group(1).strip())
        score = 10.0 if "apple-touch-icon" in rel_l else 5.0
        size = re.search(r'sizes\s*=\s*["\'](\d+)x\d+', tag, re.I)
        if size:
            score += min(int(size.group(1)), 512) / 100
        ext = Path(urlparse(url).path).suffix.lower()
        if ext == ".svg":
            score += 3
        elif ext == ".ico":
            score -= 3
        if score > best_score:
            best, best_score = url, score
    return best


def elide_to_lines(fm, text, width, lines):
    """Word-wrap text into at most `lines` lines of `width` px, ending with an ellipsis if cut."""
    words = text.split()
    out = []
    for n in range(lines):
        line = ""
        while words and fm.horizontalAdvance((line + " " + words[0]).strip()) <= width:
            line = (line + " " + words.pop(0)).strip()
        if words and (n == lines - 1 or not line):
            line = fm.elidedText((line + " " + " ".join(words)).strip(),
                                 Qt.TextElideMode.ElideRight, width)
            words = []
        if line:
            out.append(line)
        if not words:
            break
    return "\n".join(out)


class SummaryLabel(QLabel):
    """Text limited to a few lines with an ellipsis; the full text shows on hover."""

    def __init__(self, text, lines=2, name="cardSummary"):
        super().__init__(text)
        self.full, self.max_lines, self._width = text, lines, 0
        self.setObjectName(name)
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.fontMetrics().lineSpacing() * lines)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != self._width:
            self._width = event.size().width()
            self.ensurePolished()
            fm = self.fontMetrics()
            self.setFixedHeight(fm.lineSpacing() * self.max_lines)
            self.setText(elide_to_lines(fm, self.full, self._width - 2, self.max_lines))


class ProgramCard(QFrame):
    """Clickable card: icon, name, summary and a checkbox."""
    changed = pyqtSignal()

    def __init__(self, program):
        super().__init__()
        self.program = program
        self.setObjectName("card")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)

        title = SummaryLabel(program["name"], 1, "programTitle")
        summary = SummaryLabel(program.get("description", ""))
        self.status = QLabel()
        self.status.setObjectName("cardBadge")
        self.status.hide()

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(title, 1)
        head.addWidget(self.status)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addLayout(head)
        text.addWidget(summary)

        self.check = QCheckBox()
        self.check.toggled.connect(self._refresh)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addLayout(text, 1)
        row.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_icon(self, pixmap):
        self.icon_label.setPixmap(pixmap)

    def set_status(self, text, kind=""):
        """Short badge beside the name; the full text is the tooltip."""
        self.status.setText(("Update" if kind == "update" else "Installed") if text else "")
        self.status.setToolTip(text)
        self.status.setProperty("kind", kind)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setVisible(bool(text))

    def isChecked(self):
        return self.check.isChecked()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.check.toggle()

    def _refresh(self):
        self.setProperty("selected", self.check.isChecked())
        self.style().unpolish(self)
        self.style().polish(self)
        self.changed.emit()


UPDATE_LINE = re.compile(r"^(\S+)\s+(\S+)\s+->\s+(\S+)")


def sh(cmd, timeout=240):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


class UpstreamFinder(QThread):
    """Finds a program's upstream web page (from package metadata) in the background."""
    done = pyqtSignal(object)

    def __init__(self, program, helper):
        super().__init__()
        self.program, self.helper = program, helper

    def run(self):
        p = self.program
        if p.get("source", "aur") == "flatpak":
            self.done.emit({"flathub": p["package"]})
            return
        out = sh([self.helper or "pacman", "-Si", p["package"]], timeout=90)
        m = re.search(r"^URL\s*:\s*(\S+)", out, re.M)
        self.done.emit({"url": m.group(1)} if m else {})


class UpdateChecker(QThread):
    """Detects which listed programs are installed (with versions) and, optionally,
    whether they have updates.

    Emits (results, note, checked_updates). results maps program id ->
    {"version": str, "update": None | (old_version, new_version)} for installed programs.
    """
    done = pyqtSignal(object, str, bool)

    def __init__(self, programs, helper, with_updates=True):
        super().__init__()
        self.programs, self.helper, self.with_updates = programs, helper, with_updates

    @staticmethod
    def parse(text, into):
        for line in text.splitlines():
            m = UPDATE_LINE.match(line.strip())
            if m:
                into[m.group(1)] = (m.group(2), m.group(3))

    def run(self):
        note = ""
        versions = {}
        for line in sh(["pacman", "-Q"]).splitlines():
            parts = line.split()
            if len(parts) >= 2:
                versions[parts[0]] = parts[1]

        updates = {}
        if self.with_updates:
            if shutil.which("checkupdates"):  # pacman-contrib: safe, uses a temp db copy
                self.parse(sh(["checkupdates"]), updates)
            elif self.helper:
                self.parse(sh([self.helper, "-Qu"]), updates)
                note = ("pacman-contrib (checkupdates) not found; repo results use your "
                        "local package database and may be stale.")
            if self.helper:
                self.parse(sh([self.helper, "-Qua"]), updates)  # AUR

        flat_versions, flat_updates = {}, {}
        if shutil.which("flatpak"):
            for line in sh(["flatpak", "list", "--app",
                            "--columns=application,version"]).splitlines():
                parts = line.split("\t")
                if parts and parts[0].strip():
                    flat_versions[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else ""
            if self.with_updates:
                for line in sh(["flatpak", "remote-ls", "--updates", "--app",
                                "--columns=application,version"]).splitlines():
                    parts = line.split()
                    if parts:
                        flat_updates[parts[0]] = ("", parts[1] if len(parts) > 1 else "")

        results = {}
        for p in self.programs:
            pkg = p["package"]
            if p.get("source", "aur") == "flatpak":
                if pkg in flat_versions:
                    results[p["id"]] = {"version": flat_versions[pkg],
                                        "update": flat_updates.get(pkg)}
            elif pkg in versions:
                results[p["id"]] = {"version": versions[pkg], "update": updates.get(pkg)}
        self.done.emit(results, note, self.with_updates)


class ManageRow(QFrame):
    """One installed program on the Manage tab: icon, name, version, actions."""

    def __init__(self, program, info, on_launch, on_update, on_uninstall):
        super().__init__()
        self.setObjectName("card")
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setScaledContents(True)

        title = QLabel(program["name"])
        title.setObjectName("cardTitle")
        version = info.get("version")
        detail = QLabel(f"Version {version}" if version else "Installed")
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(title)
        text.addWidget(detail)
        if info.get("update"):
            old, new = info["update"]
            status = QLabel(f"Update available: {old} → {new}" if old
                            else f"Update available: {new}")
            status.setObjectName("cardStatus")
            status.setProperty("kind", "update")
            text.addWidget(status)

        launch = QPushButton("Launch")
        launch.clicked.connect(lambda _=False: on_launch())
        buttons = [launch]
        if info.get("update"):
            update = QPushButton("Update")
            update.clicked.connect(lambda _=False: on_update())
            buttons.append(update)
        uninstall = QPushButton("Uninstall")
        uninstall.clicked.connect(lambda _=False: on_uninstall())
        buttons.append(uninstall)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(14)
        row.addWidget(self.icon_label)
        row.addLayout(text, 1)
        for b in buttons:
            row.addWidget(b)

    def set_icon(self, pixmap):
        self.icon_label.setPixmap(pixmap)


class Installer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gunner Installer")
        self.resize(1020, 680)
        self.net = QNetworkAccessManager(self)
        self.net_tried = set()  # (program id, helper) pairs whose icon lookup already ran
        self.finders = []       # keeps UpstreamFinder threads alive
        self.helper = find_helper()
        self.askpass = None
        self.steps, self.failed, self.proc, self.after = [], set(), None, None

        try:
            self.programs = json.loads(PROGRAMS_FILE.read_text())
        except Exception as e:
            self.programs = []
            QMessageBox.critical(self, "Error", f"Could not read {PROGRAMS_FILE}:\n{e}")

        root = QWidget()
        layout = QVBoxLayout(root)
        install_tab = QWidget()
        install_page = QHBoxLayout(install_tab)
        install_layout = QVBoxLayout()  # right-hand side: search, cards, install button
        self.category = "All"
        self.build_sidebar()
        install_page.addWidget(self.sidebar)
        install_page.addLayout(install_layout, 1)
        install_layout.addWidget(QLabel("Select the programs to install:"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search programs…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        install_layout.addWidget(self.search)


        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(12)
        self.cards = []
        for p in self.programs:
            card = ProgramCard(p)
            card.changed.connect(self.update_install_button)
            self.cards.append(card)
            self.load_icon(p, card)
        for col in range(COLUMNS):
            grid.setColumnStretch(col, 1)
        self.grid = grid
        self.empty_label = QLabel("No programs match your search.", grid_host)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(grid_host)
        install_layout.addWidget(self.scroll, 1)

        self.button = QPushButton("Install selected")
        self.button.clicked.connect(self.install_selected)
        install_layout.addWidget(self.button)

        manage_tab = QWidget()
        manage_outer = QVBoxLayout(manage_tab)
        top = QHBoxLayout()
        top.addWidget(QLabel("Programs installed from this app:"), 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_installed)
        self.update_button = QPushButton("Check for updates")
        self.update_button.clicked.connect(self.check_updates)
        top.addWidget(self.refresh_button)
        top.addWidget(self.update_button)
        manage_outer.addLayout(top)
        manage_host = QWidget()
        self.manage_layout = QVBoxLayout(manage_host)
        self.manage_layout.setSpacing(10)
        self.manage_scroll = QScrollArea()
        self.manage_scroll.setWidgetResizable(True)
        self.manage_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.manage_scroll.setWidget(manage_host)
        manage_outer.addWidget(self.manage_scroll, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(install_tab, "Install")
        self.tabs.addTab(manage_tab, "Manage")
        layout.addWidget(self.tabs, 3)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("monospace"))
        layout.addWidget(self.output, 2)
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)
        self.apply_filter()
        self.update_install_button()
        QTimer.singleShot(0, self.check_helpers)

    # ---- helpers -------------------------------------------------------
    def log(self, text):
        self.output.appendPlainText(text.rstrip("\n"))

    def categories(self):
        used = {program_category(p) for p in self.programs}
        return [c for c in CATEGORIES if c in used] + sorted(used - set(CATEGORIES))

    def build_sidebar(self):
        """Left-hand list in the style of a software center: Discover, then Categories."""
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(190)
        self.sidebar.setIconSize(QSize(18, 18))
        for title, names in (("Discover", ["All"]), ("Categories", self.categories())):
            header = QListWidgetItem(title)
            header.setFlags(Qt.ItemFlag.NoItemFlags)  # a label, not selectable
            font = header.font()
            font.setBold(True)
            font.setPointSize(8)
            header.setFont(font)
            header.setForeground(self.palette().placeholderText())
            header.setSizeHint(QSize(0, 30))
            self.sidebar.addItem(header)
            for name in names:
                item = QListWidgetItem(
                    QIcon.fromTheme(CATEGORY_ICONS.get(name, "applications-other")),
                    "All Applications" if name == "All" else name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.sidebar.addItem(item)
                if name == "All":
                    self.sidebar.setCurrentItem(item)
        self.sidebar.currentItemChanged.connect(self.sidebar_changed)

    def sidebar_changed(self, item, _previous):
        if item is not None and item.data(Qt.ItemDataRole.UserRole):
            self.set_category(item.data(Qt.ItemDataRole.UserRole))

    def set_category(self, name):
        self.category = name
        self.apply_filter()

    def apply_filter(self):
        """Show only the cards matching the search text and category, packed from the top."""
        text = self.search.text()
        self.grid.removeWidget(self.empty_label)
        self.empty_label.hide()
        for card in self.cards:
            self.grid.removeWidget(card)
        shown = 0
        for card in self.cards:
            if program_matches(card.program, self.category, text):
                self.grid.addWidget(card, shown // COLUMNS, shown % COLUMNS)
                card.show()
                shown += 1
            else:
                card.hide()
        if not shown:
            self.grid.addWidget(self.empty_label, 0, 0, 1, COLUMNS)
            self.empty_label.show()
        for row in range(len(self.cards) // COLUMNS + 3):
            self.grid.setRowStretch(row, 0)
        self.grid.setRowStretch(max((shown + COLUMNS - 1) // COLUMNS, 1), 1)

    def update_install_button(self):
        count = sum(1 for card in self.cards if card.isChecked())
        self.button.setText(f"Install selected ({count})" if count else "Install selected")

    def load_icon(self, program, card):
        """Icon order: local file > cached download > installed app/theme icon >
        automatic lookup from the package's upstream (GitHub repo, Flathub or website)."""
        pm = local_icon(program) or cached_icon(program) or real_icon(program)
        if pm:
            card.set_icon(pm)
            return
        card.set_icon(placeholder_pixmap(program["name"]))
        key = (program["id"], self.helper or "")
        if key in self.net_tried:
            return
        self.net_tried.add(key)
        url = program.get("icon", "")
        if url.startswith(("http://", "https://")):
            self.fetch_icon(program, card, url)
        elif program.get("icon_repo"):
            self.discover_repo_icon(program, card, program["icon_repo"])
        elif program.get("download_page"):
            self.discover_site_icon(program, card, program["download_page"])
        else:
            finder = UpstreamFinder(program, self.helper)
            finder.done.connect(
                lambda info, p=program, c=card: self.upstream_found(p, c, info))
            self.finders.append(finder)
            finder.start()

    def http_get(self, url, handler, accept=None):
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader,
                      "Mozilla/5.0 (X11; Linux x86_64) gunner-installer")
        if accept:
            req.setRawHeader(b"Accept", accept.encode())
        reply = self.net.get(req)
        reply.finished.connect(lambda r=reply: self._reply_done(r, handler))

    @staticmethod
    def _reply_done(reply, handler):
        ok = reply.error() == QNetworkReply.NetworkError.NoError
        data = bytes(reply.readAll()) if ok else b""
        reply.deleteLater()
        handler(ok, data)

    def fetch_icon(self, program, card, url):
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix not in (".png", ".svg", ".webp", ".jpg", ".jpeg", ".ico"):
            suffix = ".png"
        cache = CACHE_DIR / f"{program['id']}{suffix}"

        def done(ok, data):
            pm = QPixmap()
            if not ok or not pm.loadFromData(data):
                return
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(data)
            except OSError:
                pass
            try:
                card.set_icon(fit(pm))
            except RuntimeError:  # widget was rebuilt/deleted meanwhile
                pass

        self.http_get(url, done)

    def upstream_found(self, program, card, info):
        if info.get("flathub"):
            self.discover_flathub_icon(program, card, info["flathub"])
            return
        url = info.get("url", "")
        m = re.match(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)", url)
        if m:
            name = m.group(2)
            if name.endswith(".git"):
                name = name[:-4]
            self.discover_repo_icon(program, card, f"{m.group(1)}/{name}")
        elif url:
            self.discover_site_icon(program, card, url)
        else:
            self.log(f"No upstream URL found for {program['name']}; using a placeholder icon.")

    def discover_repo_icon(self, program, card, repo):
        """Look through the project's GitHub repo for its app icon."""
        def done(ok, data):
            paths = []
            if ok:
                try:
                    tree = json.loads(data.decode()).get("tree", [])
                    paths = [t["path"] for t in tree if t.get("type") == "blob"]
                except Exception:
                    pass
            path = pick_icon_path(paths, program)
            if path:
                self.log(f"Icon for {program['name']}: using {path} from {repo}")
                self.fetch_icon(program, card,
                                f"https://raw.githubusercontent.com/{repo}/HEAD/{quote(path)}")
            else:
                self.log(f"No icon found in {repo} for {program['name']}; set \"icon\" "
                         "to an image URL in programs.json if you want one.")

        self.http_get(f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1",
                      done, accept="application/vnd.github+json")

    def discover_site_icon(self, program, card, site):
        """Use the icon a project's web page advertises (apple-touch-icon / favicon)."""
        def done(ok, data):
            icon = pick_site_icon(data.decode(errors="replace"), site) if ok else None
            if icon:
                self.log(f"Icon for {program['name']}: using {icon}")
                self.fetch_icon(program, card, icon)
            else:
                self.log(f"Couldn't get an icon from {site} for {program['name']}.")

        self.http_get(site, done, accept="text/html")

    def discover_flathub_icon(self, program, card, appid):
        def done(ok, data):
            icon = None
            if ok:
                try:
                    value = json.loads(data.decode()).get("icon")
                    if isinstance(value, str) and value.startswith("http"):
                        icon = value
                except Exception:
                    pass
            self.fetch_icon(program, card, icon or
                            f"https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{appid}.png")

        self.http_get(f"https://flathub.org/api/v2/appstream/{appid}", done)

    def set_busy(self, busy):
        self.tabs.setEnabled(not busy)
        self.progress.setRange(0, 0 if busy else 1)

    def ensure_askpass(self):
        if not shutil.which("kdialog"):
            QMessageBox.warning(
                self, "kdialog not found",
                "The password prompt needs kdialog:\nsudo pacman -S kdialog")
            return False
        if self.askpass is None:
            self.askpass = make_askpass()
        return True

    # ---- AUR helper check ----------------------------------------------
    def check_helpers(self):
        missing = [h for h in HELPERS if not shutil.which(h)]
        if not missing:
            self.refresh_installed()
            return
        answer = QMessageBox.question(
            self, "AUR helpers missing",
            f"Not installed: {', '.join(missing)}.\n\n"
            "Install them now? (Needs your password and an internet connection.)")
        if answer != QMessageBox.StandardButton.Yes:
            self.log("Skipped installing " + ", ".join(missing) +
                     ". Repo/AUR installs need paru or yay; Flatpak installs still work.")
            self.refresh_installed()
            return
        if not self.ensure_askpass():
            self.refresh_installed()
            return
        self.set_busy(True)
        self.failed.clear()
        self.steps = [(f"helper-{h}", f"Install {h}", helper_install_cmd(h)) for h in missing]
        self.after = self.helpers_done
        self.run_next()

    def helpers_done(self):
        self.helper = find_helper()
        for h in HELPERS:
            state = "installed" if shutil.which(h) else "NOT installed"
            self.log(f"{h}: {state}")
        self.refresh_installed()

    # ---- update flow ---------------------------------------------------
    def refresh_installed(self):
        """Quick scan of which listed programs are installed (no update lookup)."""
        self._scan(with_updates=False)

    def check_updates(self):
        self.log("\nChecking for updates…")
        self._scan(with_updates=True)

    def _scan(self, with_updates):
        if not self.programs:
            return
        self.set_busy(True)
        self.checker = UpdateChecker(self.programs, self.helper, with_updates)
        self.checker.done.connect(self.scan_finished)
        self.checker.start()

    def scan_finished(self, results, note, checked):
        self.set_busy(False)
        if note and checked:
            self.log(note)
        pending = []
        for p, card in zip(self.programs, self.cards):
            info = results.get(p["id"])
            if info is not None:
                self.load_icon(p, card)  # installed apps may now have a real icon
            if info is None:
                card.set_status("")
            elif info["update"]:
                old, new = info["update"]
                card.set_status(f"Update available: {old} → {new}" if old
                                else f"Update available: {new}", "update")
                pending.append(p)
            else:
                card.set_status("Installed · up to date" if checked else "Installed", "ok")
        self.rebuild_manage(results)
        if not checked:
            return
        if not results:
            self.log("None of the listed programs are installed yet.")
        elif not pending:
            self.log("Everything is up to date.")
        else:
            self.log("Updates available: " + ", ".join(p["name"] for p in pending))
            self.offer_updates(pending)

    def rebuild_manage(self, results):
        while self.manage_layout.count():
            item = self.manage_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        shown = 0
        for p in self.programs:
            info = results.get(p["id"])
            if info is None:
                continue
            row = ManageRow(
                p, info,
                lambda p=p: self.launch_program(p),
                lambda p=p: self.offer_updates([p]),
                lambda p=p: self.uninstall_program(p),
            )
            self.load_icon(p, row)
            self.manage_layout.addWidget(row)
            shown += 1
        if not shown:
            empty = QLabel("None of the programs from this app are installed yet.\n"
                           "Use the Install tab to add some.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.manage_layout.addWidget(empty)
        self.manage_layout.addStretch(1)

    def launch_program(self, p):
        if p.get("source", "aur") == "flatpak":
            cmd = ["flatpak", "run", p["package"]]
        else:
            cmd = shlex.split(p.get("launch", p["id"]))
            if not cmd or not shutil.which(cmd[0]):
                QMessageBox.warning(
                    self, "Can't launch",
                    f"Couldn't find '{cmd[0] if cmd else p['id']}'.\n"
                    'Set a "launch" command for this program in programs.json.')
                return
        try:
            subprocess.Popen(cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log(f"Launched {p['name']}")
        except OSError as e:
            QMessageBox.warning(self, "Can't launch", str(e))

    def uninstall_program(self, p):
        name = p["name"]
        flat = p.get("source", "aur") == "flatpak"
        detail = ("the Flatpak app" if flat else
                  "the package and any dependencies no other program needs")
        if QMessageBox.question(
                self, "Uninstall",
                f"Uninstall {name}?\n\nThis removes {detail}.",
        ) != QMessageBox.StandardButton.Yes:
            return
        if flat:
            cmd = ["flatpak", "uninstall", "-y", "--noninteractive", p["package"]]
        else:
            # pkexec shows the system's own (polkit) password dialog and handles retries.
            if not shutil.which("pkexec"):
                QMessageBox.warning(self, "pkexec not found",
                                    "Uninstalling needs polkit:\nsudo pacman -S polkit")
                return
            cmd = ["pkexec", "pacman", "-Rns", "--noconfirm", p["package"]]
        self.set_busy(True)
        self.failed.clear()
        self.steps = [(name, f"Uninstall {name}", cmd)]
        self.after = self.refresh_installed
        self.run_next()

    def offer_updates(self, pending):
        native = [p for p in pending if p.get("source", "aur") != "flatpak"]
        repo = any(p.get("source", "aur") == "repo" for p in native)
        text = "Updates are available for:\n  " + "\n  ".join(p["name"] for p in pending)
        if repo:
            text += ("\n\nOfficial-repo packages can only be updated safely with a full "
                     "system upgrade, so that will run too.")
        text += "\n\nUpdate now?"
        if QMessageBox.question(self, "Updates available", text) != QMessageBox.StandardButton.Yes:
            return
        self.start_updates(pending)

    def start_updates(self, pending):
        native = [p for p in pending if p.get("source", "aur") != "flatpak"]
        flat = [p for p in pending if p.get("source", "aur") == "flatpak"]
        repo = any(p.get("source", "aur") == "repo" for p in native)
        if native and not self.helper:
            QMessageBox.critical(self, "Missing tool", "Install paru or yay first.")
            return
        if not self.ensure_askpass():
            return
        steps = []
        if native:
            flags = ["--noconfirm", "--sudoflags", "-A"] + review_flags(self.helper)
            if repo:
                steps.append(("system", "Full system upgrade", [self.helper, "-Syu"] + flags))
            else:
                for p in native:
                    steps.append((p["name"], f"Update {p['name']}",
                                  [self.helper, "-S"] + flags + [p["package"]]))
        for p in flat:
            steps.append((p["name"], f"Update {p['name']}",
                          ["flatpak", "update", "-y", "--noninteractive", p["package"]]))
        self.set_busy(True)
        self.failed.clear()
        self.steps = steps
        self.after = self.check_updates  # re-check afterwards to refresh versions
        self.run_next()

    # ---- install flow --------------------------------------------------
    def pick_bundle(self, program):
        """For programs shipped as a .flatpak file on the vendor's site (not on Flathub):
        open the official download page, or let the user choose the file they downloaded."""
        name = program["name"]
        if not shutil.which("flatpak"):
            QMessageBox.warning(self, "Flatpak missing",
                                f"{name} is installed with Flatpak.\nInstall it first: sudo pacman -S flatpak")
            return None
        box = QMessageBox(self)
        box.setWindowTitle(f"Install {name}")
        box.setText(f"{name} isn't on Flathub. The official .flatpak file is on the vendor's site:\n"
                    f"{program['download_page']}\n\nOnly download it from there.")
        choose = box.addButton("Choose downloaded file…", QMessageBox.ButtonRole.AcceptRole)
        page = box.addButton("Open download page", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is page:
            QDesktopServices.openUrl(QUrl(program["download_page"]))
            self.log(f"Opened {program['download_page']}. Download the .flatpak file, "
                     f"then install {name} again and choose it.")
        elif clicked is choose:
            path, _ = QFileDialog.getOpenFileName(
                self, f"Choose the {name} .flatpak file", str(Path.home() / "Downloads"),
                "Flatpak bundles (*.flatpak)")
            return path or None
        return None

    def install_selected(self):
        chosen = [p for p, card in zip(self.programs, self.cards) if card.isChecked()]
        if not chosen:
            return
        needs_helper = any(p.get("source", "aur") != "flatpak" for p in chosen)
        if needs_helper and not self.helper:
            QMessageBox.critical(self, "Missing tool", "Install paru or yay first.")
            return
        if not self.ensure_askpass():
            return

        self.set_busy(True)
        self.failed.clear()
        steps = []
        for p in chosen:
            name, pkg = p["name"], p["package"]
            if p.get("source", "aur") == "flatpak":
                if p.get("download_page"):  # the vendor ships a .flatpak file, not on Flathub
                    bundle = self.pick_bundle(p)
                    if bundle:
                        steps.append((name, f"Add the Flathub remote for {name}",
                                      ["flatpak", "remote-add", "--user", "--if-not-exists", "flathub",
                                       "https://dl.flathub.org/repo/flathub.flatpakrepo"]))
                        steps.append((name, f"Install {name}",
                                      ["flatpak", "install", "--user", "-y", "--noninteractive", bundle]))
                    continue
                steps.append((name, f"Install {name}",
                              ["flatpak", "install", "-y", "--noninteractive", "flathub", pkg]))
                continue
            base = [self.helper, "-S", "--needed", "--noconfirm",
                    "--sudoflags", "-A"] + review_flags(self.helper)
            steps.append((name, f"Install {name}", base + [pkg]))
            self.log(f"Looking up recommended dependencies for {name}…")
            QApplication.processEvents()
            deps = get_optdeps(self.helper, pkg)
            if deps:
                picked = OptDepsDialog(name, deps, self).selected()
                if picked:
                    steps.append((name, f"Recommended dependencies for {name}",
                                  base + ["--asdeps"] + picked))
        if not steps:
            self.set_busy(False)
            self.log("Nothing to install.")
            return
        self.steps = steps
        self.run_next()

    def run_next(self):
        while self.steps and self.steps[0][0] in self.failed:
            skipped = self.steps.pop(0)
            self.log(f"Skipping: {skipped[1]} (earlier step failed)")
        if not self.steps:
            self.set_busy(False)
            if self.failed:
                self.log("\nFinished with errors: " + ", ".join(sorted(self.failed)))
            else:
                self.log("\nAll done.")
            if self.after:
                callback, self.after = self.after, None
                callback()
            return
        self.current = self.steps.pop(0)
        group, label, cmd = self.current
        self.log(f"\n=== {label} ===\n$ {' '.join(cmd)}")

        env = QProcessEnvironment.systemEnvironment()
        env.insert("SUDO_ASKPASS", str(self.askpass))
        self.proc = QProcess(self)
        self.proc.setProcessEnvironment(env)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.read_output)
        self.proc.finished.connect(self.on_finished)
        self.proc.start(cmd[0], cmd[1:])

    def read_output(self):
        text = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        text = ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "\n")
        if text.strip():
            self.log(text)

    def on_finished(self, code, _status):
        if code != 0:
            self.failed.add(self.current[0])
            self.log(f"!! {self.current[1]} failed (exit code {code})")
        else:
            self.log(f"OK: {self.current[1]}")
        self.run_next()

    def closeEvent(self, event):
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
        event.accept()


def main():
    if "--version" in sys.argv:
        print(f"Gunner Installer {__version__}")
        return 0
    app = QApplication(sys.argv)
    app.setDesktopFileName("gunner-installer")  # lets Plasma match the window to its launcher
    icon = QIcon.fromTheme("gunner-installer")
    if icon.isNull() and (APP_DIR / "gunner-installer.svg").is_file():
        icon = QIcon(str(APP_DIR / "gunner-installer.svg"))
    app.setWindowIcon(icon)
    if os.geteuid() == 0:
        QMessageBox.critical(None, "Don't run as root",
                             "Run this as your normal user; it asks for your password when needed.")
        return 1
    window = Installer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

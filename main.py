from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

import image
import monitor
import theme


LOG = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _theme_root() -> Path:
    return _repo_root() / "pypaper"


@dataclass(frozen=True)
class UiConfig:
    thumb_size: QtCore.QSize = QtCore.QSize(220, 120)
    button_padding: int = 8


class MonitorRow(QtWidgets.QWidget):
    clicked = QtCore.Signal(str, str)  # monitor_name, image_path

    def __init__(
        self,
        monitor_name: str,
        *,
        config: UiConfig,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._monitor_name = monitor_name
        self._config = config

        self._label = QtWidgets.QLabel(monitor_name)
        self._label.setMinimumWidth(110)
        self._label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft
        )

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._content = QtWidgets.QWidget()
        self._h = QtWidgets.QHBoxLayout(self._content)
        self._h.setContentsMargins(0, 0, 0, 0)
        self._h.setSpacing(10)
        self._scroll.setWidget(self._content)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self._label)
        layout.addWidget(self._scroll, 1)

    @property
    def monitor_name(self) -> str:
        return self._monitor_name

    def clear(self) -> None:
        for btn in list(self._group.buttons()):
            self._group.removeButton(btn)
            btn.setParent(None)
            btn.deleteLater()

        while self._h.count():
            item = self._h.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def set_images(
        self,
        images: list[Path],
        *,
        icon_provider: "IconProvider",
        checked_source: Path | None,
    ) -> None:
        self.clear()

        if not images:
            empty = QtWidgets.QLabel("(no images)")
            empty.setStyleSheet("color: #6b7280;")
            self._h.addWidget(empty)
            self._h.addStretch(1)
            return

        for p in images:
            btn = QtWidgets.QToolButton()
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setIcon(icon_provider.icon_for(p))
            btn.setIconSize(self._config.thumb_size)
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setAutoRaise(False)
            btn.setStyleSheet(
                "QToolButton {"
                "  border: 1px solid #d1d5db;"
                "  border-radius: 10px;"
                "  background: #ffffff;"
                "  padding: 4px;"
                "}"
                "QToolButton:hover { border-color: #9ca3af; }"
                "QToolButton:checked { border: 2px solid #111827; }"
            )
            w = self._config.thumb_size.width() + self._config.button_padding
            h = self._config.thumb_size.height() + self._config.button_padding
            btn.setFixedSize(w, h)

            if checked_source is not None and p.resolve() == checked_source.resolve():
                btn.setChecked(True)

            btn.clicked.connect(
                lambda _=False, path=p: self.clicked.emit(self._monitor_name, str(path))
            )

            self._group.addButton(btn)
            self._h.addWidget(btn)

        self._h.addStretch(1)


class IconProvider:
    def __init__(self, *, thumb_size: QtCore.QSize):
        self._thumb_size = thumb_size
        self._cache: dict[Path, QtGui.QIcon] = {}

    def icon_for(self, path: Path) -> QtGui.QIcon:
        path = path.resolve()
        cached = self._cache.get(path)
        if cached is not None:
            return cached

        reader = QtGui.QImageReader(str(path))
        img = reader.read()

        if img.isNull():
            pix = QtGui.QPixmap(self._thumb_size)
            pix.fill(QtGui.QColor("#f3f4f6"))
            painter = QtGui.QPainter(pix)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            painter.setPen(QtGui.QColor("#6b7280"))
            painter.drawRect(pix.rect().adjusted(2, 2, -2, -2))
            painter.drawText(
                pix.rect().adjusted(8, 8, -8, -8),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                path.stem[:32],
            )
            painter.end()
            icon = QtGui.QIcon(pix)
        else:
            pix = QtGui.QPixmap.fromImage(img)
            scaled = pix.scaled(
                self._thumb_size,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            if scaled.size() != self._thumb_size:
                canvas = QtGui.QPixmap(self._thumb_size)
                canvas.fill(QtGui.QColor("#ffffff"))
                painter = QtGui.QPainter(canvas)
                x = (self._thumb_size.width() - scaled.width()) // 2
                y = (self._thumb_size.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
                painter.end()
                scaled = canvas

            icon = QtGui.QIcon(scaled)

        self._cache[path] = icon
        return icon


class WallpaperWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pypaper")

        self._config = UiConfig()
        self._icons = IconProvider(thumb_size=self._config.thumb_size)

        self._theme_root = _theme_root()
        self._loaded_dir = image.default_loaded_dir()
        self._state_path = self._loaded_dir / "state.json"

        self._themes = theme.list_themes(self._theme_root)
        self._monitors = monitor.get_monitors()

        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._theme_combo.addItems(self._themes)
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Theme:"))
        top.addWidget(self._theme_combo)
        top.addStretch(1)

        self._rows_container = QtWidgets.QWidget()
        self._rows_layout = QtWidgets.QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(16)

        self._rows_scroll = QtWidgets.QScrollArea()
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._rows_scroll.setWidget(self._rows_container)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.addLayout(top)
        layout.addWidget(self._rows_scroll, 1)

        self._rows: dict[str, MonitorRow] = {}
        self._build_rows()
        self._rebuild_buttons()

        if not self._themes:
            QtWidgets.QMessageBox.warning(
                self,
                "No themes",
                f"No themes found under {self._theme_root}.",
            )

    def _build_rows(self) -> None:
        for name in self._monitors:
            row = MonitorRow(name, config=self._config)
            row.clicked.connect(self._on_image_clicked)
            self._rows[name] = row
            self._rows_layout.addWidget(row)

        self._rows_layout.addStretch(1)

    def _current_theme(self) -> str:
        return self._theme_combo.currentText().strip()

    def _checked_source_for(self, monitor_name: str, theme_name: str) -> Path | None:
        try:
            state = image.load_state(self._state_path)
        except Exception:
            return None

        mon = state.get("monitors", {}).get(monitor_name)
        if not isinstance(mon, dict):
            return None
        if mon.get("theme") != theme_name:
            return None
        src = mon.get("source_path")
        if not isinstance(src, str) or not src:
            return None
        return Path(src)

    def _rebuild_buttons(self) -> None:
        theme_name = self._current_theme()
        images_in_theme = (
            theme.list_images(self._theme_root / theme_name) if theme_name else []
        )

        for mon_name, row in self._rows.items():
            checked = self._checked_source_for(mon_name, theme_name)
            row.set_images(
                images_in_theme,
                icon_provider=self._icons,
                checked_source=checked,
            )

    @QtCore.Slot(str)
    def _on_theme_changed(self, _theme_name: str) -> None:
        self._rebuild_buttons()

    @QtCore.Slot(str, str)
    def _on_image_clicked(self, monitor_name: str, image_path: str) -> None:
        theme_name = self._current_theme()
        if not theme_name:
            return

        src = Path(image_path)
        try:
            loaded_path = image.apply_wallpaper(
                monitor=monitor_name,
                theme=theme_name,
                src=src,
                loaded_dir=self._loaded_dir,
                state_path=self._state_path,
            )
        except Exception as e:
            LOG.exception("Failed to apply wallpaper")
            QtWidgets.QMessageBox.critical(
                self,
                "Failed to apply wallpaper",
                f"Monitor: {monitor_name}\nImage: {src}\n\n{e}",
            )
            return

        LOG.info("Applied wallpaper monitor=%s path=%s", monitor_name, loaded_path)


def main(argv: list[str]) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    app = QtWidgets.QApplication(argv)
    app.setApplicationName("pypaper")

    w = WallpaperWindow()
    w.resize(1200, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

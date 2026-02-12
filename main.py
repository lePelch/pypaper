from __future__ import annotations

import logging
import os
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


DATA_ROOT = Path(os.environ.get("PYPAPER_DATA_ROOT", str(_repo_root() / "pypaper")))
THEME_ROOT = DATA_ROOT
LOADED_DIR = DATA_ROOT / "Loaded"
STATE_PATH = LOADED_DIR / "state.json"


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

    def set_label_text(self, text: str) -> None:
        self._label.setText(text)

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

        self._theme_root = THEME_ROOT
        self._loaded_dir = LOADED_DIR
        self._state_path = STATE_PATH
        self._loaded_dir.mkdir(parents=True, exist_ok=True)

        self._themes = theme.list_themes(self._theme_root)
        self._monitors = monitor.get_monitors()
        self._sort_monitors()

        self._theme_combo = QtWidgets.QComboBox()
        self._theme_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._theme_combo.addItems(self._themes)
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)

        self._mapping_btn = QtWidgets.QPushButton("Mapping...")
        self._mapping_btn.clicked.connect(self._open_mapping_dialog)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Theme:"))
        top.addWidget(self._theme_combo)
        top.addWidget(self._mapping_btn)
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
        self._refresh_row_labels()
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

    def _clear_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        self._rows.clear()

    def _sort_monitors(self) -> None:
        mapping = self._mapping()

        def key(name: str) -> tuple[int, int, str]:
            slot = mapping.get(name)
            if isinstance(slot, int) and slot > 0:
                return (0, slot, "")
            return (1, 0, name.casefold())

        self._monitors.sort(key=key)

    def _current_theme(self) -> str:
        return self._theme_combo.currentText().strip()

    def _mapping(self) -> dict[str, int]:
        return image.get_mapping(self._state_path)

    def _refresh_row_labels(self) -> None:
        mapping = self._mapping()
        for mon_name, row in self._rows.items():
            slot = mapping.get(mon_name)
            if isinstance(slot, int) and slot > 0:
                row.set_label_text(f"Monitor {slot}")
            else:
                row.set_label_text("Monitor (unmapped)")

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

    @QtCore.Slot()
    def _open_mapping_dialog(self) -> None:
        dlg = MappingDialog(
            monitors=self._monitors,
            loaded_dir=self._loaded_dir,
            state_path=self._state_path,
            parent=self,
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._sort_monitors()
            self._clear_rows()
            self._build_rows()
            self._refresh_row_labels()
            self._rebuild_buttons()

    @QtCore.Slot(str, str)
    def _on_image_clicked(self, monitor_name: str, image_path: str) -> None:
        theme_name = self._current_theme()
        if not theme_name:
            return

        mapping = self._mapping()
        slot = mapping.get(monitor_name)
        if not isinstance(slot, int) or slot <= 0:
            self._open_mapping_dialog()
            mapping = self._mapping()
            slot = mapping.get(monitor_name)
            if not isinstance(slot, int) or slot <= 0:
                return

        src = Path(image_path)
        try:
            loaded_path = image.apply_wallpaper(
                monitor=monitor_name,
                slot=slot,
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


class MappingDialog(QtWidgets.QDialog):
    def __init__(
        self,
        *,
        monitors: list[str],
        loaded_dir: Path,
        state_path: Path,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Monitor mapping")
        self.setModal(True)

        self._monitors = list(monitors)
        self._loaded_dir = loaded_dir
        self._state_path = state_path
        self._slot_max = max(1, len(self._monitors))

        self._error = QtWidgets.QLabel("")
        self._error.setStyleSheet("color: #b91c1c;")

        self._table = QtWidgets.QTableWidget(len(self._monitors), 3)
        self._table.setHorizontalHeaderLabels(["Monitor", "Slot", "File"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)

        self._slot_boxes: dict[str, QtWidgets.QComboBox] = {}

        existing = image.get_mapping(self._state_path)
        for row, mon in enumerate(self._monitors):
            mon_item = QtWidgets.QTableWidgetItem(mon)
            self._table.setItem(row, 0, mon_item)

            slot_box = QtWidgets.QComboBox()
            slot_box.addItem("")
            for i in range(1, self._slot_max + 1):
                slot_box.addItem(str(i))

            slot = existing.get(mon)
            if isinstance(slot, int) and 1 <= slot <= self._slot_max:
                slot_box.setCurrentText(str(slot))

            slot_box.currentTextChanged.connect(self._on_slots_changed)
            self._slot_boxes[mon] = slot_box
            self._table.setCellWidget(row, 1, slot_box)

            file_item = QtWidgets.QTableWidgetItem("")
            self._table.setItem(row, 2, file_item)

        self._autofill = QtWidgets.QPushButton("Auto-fill")
        self._autofill.clicked.connect(self._on_autofill)
        self._clear = QtWidgets.QPushButton("Clear")
        self._clear.clicked.connect(self._on_clear)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        tools = QtWidgets.QHBoxLayout()
        tools.addWidget(self._autofill)
        tools.addWidget(self._clear)
        tools.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(
            QtWidgets.QLabel(
                f"Assign a slot (1..{self._slot_max}) to each monitor. Slots must be unique."
            )
        )
        layout.addLayout(tools)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

        self._on_slots_changed()

    def _row_for_monitor(self, monitor_name: str) -> int:
        try:
            return self._monitors.index(monitor_name)
        except ValueError:
            return -1

    def _set_row_highlight(self, row: int, *, bad: bool) -> None:
        if row < 0:
            return
        color = QtGui.QColor("#fee2e2") if bad else QtGui.QColor("#00000000")
        for col in (0, 2):
            item = self._table.item(row, col)
            if item is not None:
                item.setBackground(color)
        slot_box = self._table.cellWidget(row, 1)
        if isinstance(slot_box, QtWidgets.QComboBox):
            if bad:
                slot_box.setStyleSheet("QComboBox { background: #fee2e2; }")
            else:
                slot_box.setStyleSheet("")

    @QtCore.Slot()
    def _on_autofill(self) -> None:
        for i, mon in enumerate(self._monitors, start=1):
            self._slot_boxes[mon].setCurrentText(str(i))

    @QtCore.Slot()
    def _on_clear(self) -> None:
        for mon in self._monitors:
            self._slot_boxes[mon].setCurrentText("")

    @QtCore.Slot()
    def _on_slots_changed(self) -> None:
        # Update file column and validate.
        selected: dict[str, int] = {}
        duplicates: set[str] = set()
        used: dict[int, str] = {}
        missing: set[str] = set()

        for mon in self._monitors:
            txt = self._slot_boxes[mon].currentText().strip()
            if not txt:
                missing.add(mon)
                continue
            try:
                slot = int(txt)
            except ValueError:
                missing.add(mon)
                continue
            if not (1 <= slot <= self._slot_max):
                missing.add(mon)
                continue

            if slot in used:
                duplicates.add(mon)
                duplicates.add(used[slot])
            else:
                used[slot] = mon
            selected[mon] = slot

        for mon in self._monitors:
            row = self._row_for_monitor(mon)
            file_item = self._table.item(row, 2)
            slot = selected.get(mon)
            if file_item is not None:
                if slot is None:
                    file_item.setText("(unset)")
                else:
                    file_item.setText(str(self._loaded_dir / f"monitor_{slot}.png"))

            bad = (mon in missing) or (mon in duplicates)
            self._set_row_highlight(row, bad=bad)

        if duplicates:
            self._error.setText("Slots must be unique.")
            self._ok_btn.setEnabled(False)
            return
        if missing:
            self._error.setText("Every monitor must have a slot.")
            self._ok_btn.setEnabled(False)
            return

        self._error.setText("")
        self._ok_btn.setEnabled(True)

    @QtCore.Slot()
    def _on_accept(self) -> None:
        self._on_slots_changed()
        if not self._ok_btn.isEnabled():
            return

        mapping: dict[str, int] = {}
        for mon in self._monitors:
            txt = self._slot_boxes[mon].currentText().strip()
            mapping[mon] = int(txt)

        image.set_mapping(self._state_path, mapping)
        self.accept()


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

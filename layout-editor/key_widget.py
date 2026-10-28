"""KeyWidget: one D200 key in the editor (image preview, selection, drag & drop).

Placed in main_window.ui as promoted QLabel ("KeyWidget"); the main window sets
`index` after loading and reacts to the signals. The widget itself never
touches the layout data, it only reports what the user did.
"""

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from config import KEY_SIZE, WIDE_INDEX

MIME_TYPE = "application/x-d200-key"
WIDE_WIDTH = KEY_SIZE * 458 // 196


class KeyWidget(QLabel):
    """Preview of one key; drag it onto another key to swap both."""

    clicked = Signal(int)
    swapped = Signal(int, int)               # source index, target index
    menu_requested = Signal(int, QPoint)     # index, global position

    # --------------------------------------------------------------------------
    def __init__(self, parent=None):
        """Create an empty key; size and drag behaviour follow from `index`."""
        super().__init__(parent)
        self._index = -1
        self._drag_start = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.menu_requested.emit(self._index, self.mapToGlobal(pos)))
        self.set_selected(False)

    # --------------------------------------------------------------------------
    @property
    def index(self) -> int:
        """Button index in the layout (0-12 keys, 13 wide display)."""
        return self._index

    # --------------------------------------------------------------------------
    @index.setter
    def index(self, value: int) -> None:
        """Set the index; the wide display gets its wider size and takes no drops."""
        self._index = value
        self.setFixedSize(WIDE_WIDTH if value == WIDE_INDEX else KEY_SIZE, KEY_SIZE)
        self.setAcceptDrops(value != WIDE_INDEX)

    # --------------------------------------------------------------------------
    def set_image(self, path: str | None) -> None:
        """Show an image file scaled to the key size, or a dark empty key."""
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            self.clear()
        else:
            self.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))

    # --------------------------------------------------------------------------
    def set_selected(self, selected: bool) -> None:
        """Mark the key as the one shown in the properties panel."""
        border = "#3daee9" if selected else "#404040"
        self.setStyleSheet(f"background: black; border: 2px solid {border}; border-radius: 8px;")

    # --------------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        """Select the key and remember where a possible drag starts."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.clicked.emit(self._index)
        super().mousePressEvent(event)

    # --------------------------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        """Start dragging once the mouse moved far enough (not for the wide display)."""
        if (self._drag_start is None or self._index == WIDE_INDEX
                or (event.position().toPoint() - self._drag_start).manhattanLength() < QApplication.startDragDistance()):
            return
        self._drag_start = None
        mime = QMimeData()
        mime.setData(MIME_TYPE, str(self._index).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        if self.pixmap() and not self.pixmap().isNull():
            drag.setPixmap(self.pixmap().scaled(KEY_SIZE // 2, KEY_SIZE // 2))
        drag.exec(Qt.DropAction.MoveAction)

    # --------------------------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        """Accept only keys of this editor."""
        if event.mimeData().hasFormat(MIME_TYPE):
            event.acceptProposedAction()

    # --------------------------------------------------------------------------
    def dropEvent(self, event) -> None:
        """Report the swap; the main window exchanges the buttons."""
        source = int(bytes(event.mimeData().data(MIME_TYPE)).decode())
        if source != self._index:
            self.swapped.emit(source, self._index)
        event.acceptProposedAction()

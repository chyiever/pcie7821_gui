"""
Reusable plot interaction helpers.

This module provides a custom ViewBox with:
- left-drag rectangle zoom
- Shift + left-drag horizontal pan
- mouse wheel zoom
- right-click "View All" restore entry
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QAction, QMenu
import pyqtgraph as pg


class ZoomablePlotViewBox(pg.ViewBox):
    """ViewBox with stable rectangle-zoom behavior for realtime plots."""

    sigManualRangeChange = pyqtSignal()
    sigViewAllRequested = pyqtSignal()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("enableMenu", False)
        super().__init__(*args, **kwargs)
        self.setMouseMode(self.RectMode)

    def wheelEvent(self, ev, axis=None):
        super().wheelEvent(ev, axis=axis)
        self.sigManualRangeChange.emit()

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.LeftButton and (ev.modifiers() & Qt.ShiftModifier):
            last_pos = self.mapToView(ev.lastPos())
            current_pos = self.mapToView(ev.pos())
            delta = last_pos - current_pos
            self.translateBy(x=delta.x(), y=0.0)
            ev.accept()
            self.sigManualRangeChange.emit()
            return

        super().mouseDragEvent(ev, axis=axis)
        if ev.button() == Qt.LeftButton and ev.isFinish():
            self.sigManualRangeChange.emit()

    def mouseClickEvent(self, ev):
        if ev.button() != Qt.RightButton:
            super().mouseClickEvent(ev)
            return

        menu = QMenu()
        view_all_action = QAction("View All", menu)
        menu.addAction(view_all_action)
        selected = menu.exec_(QCursor.pos())
        if selected is view_all_action:
            self.sigViewAllRequested.emit()
        ev.accept()

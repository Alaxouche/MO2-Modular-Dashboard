# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional

def resolve_preview_path(rel: str) -> Path:
    rel = (rel or "").strip().replace("\\", "/")
    base = Path(__file__).resolve().parent.parent
    if "/" in rel:
        p = (base / rel)
        if p.exists():
            return p
        if "previews/" in rel:
            alt = base / rel.replace("previews/", "preview/", 1)
            if alt.exists():
                return alt
        return p
    p1 = base / "previews" / rel
    if p1.exists():
        return p1
    p2 = base / "preview" / rel
    return p2 if p2.exists() else p1

# QLabel spécialisé pour affichage redimensionné avec fondu
def ScaledPreviewLabelFactory(parent=None):
    try:
        from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
        from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
        from PyQt6.QtGui import QPixmap
        _qt6 = True
    except Exception:
        from PyQt5.QtWidgets import QLabel, QGraphicsOpacityEffect
        from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
        from PyQt5.QtGui import QPixmap
        _qt6 = False

    class _ScaledPreviewLabel(QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            except Exception:
                self.setAlignment(Qt.AlignCenter)
            self._pixmap_src: Optional[QPixmap] = None
            self.setMinimumSize(360, 200)
            self._fx = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._fx)
            self._fade = QPropertyAnimation(self._fx, b"opacity", self)
            self._fade.setDuration(180)
            try:
                self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
            except Exception:
                self._fade.setEasingCurve(QEasingCurve.InOutQuad)

        def _start_fade(self):
            try:
                self._fade.stop()
                self._fx.setOpacity(0.0)
                self._fade.setStartValue(0.0)
                self._fade.setEndValue(1.0)
                self._fade.start()
            except Exception:
                pass

        def set_source_pixmap(self, pm: Optional[QPixmap]):
            self._pixmap_src = pm
            self._rescale()
            self._start_fade()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._rescale()

        def _rescale(self):
            if self._pixmap_src and not self._pixmap_src.isNull():
                try:
                    aspect = Qt.AspectRatioMode.KeepAspectRatio
                    smooth = Qt.TransformationMode.SmoothTransformation
                except Exception:
                    aspect = Qt.KeepAspectRatio
                    smooth = Qt.SmoothTransformation
                scaled = self._pixmap_src.scaled(self.size(), aspect, smooth)
                self.setPixmap(scaled)
                self.setText("")
            else:
                self.setPixmap(QPixmap())
                if not self.text():
                    self.setText("Preview unavailable")

    return _ScaledPreviewLabel(parent)

"""Video surface with a persistent badge saying what is playing.

QVideoWidget renders into a native child window that other widgets cannot be drawn over,
so frames arrive through a QVideoSink and are painted here, badge included.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPaintEvent
from PySide6.QtMultimedia import QVideoFrame, QVideoSink
from PySide6.QtWidgets import QSizePolicy, QWidget

from radio_video.ui import theme
from radio_video.ui.icons import IconName
from radio_video.ui.widgets.badge import BadgeTone, badge_size, paint_badge
from radio_video.ui.widgets.painting import antialiased, fill_rounded, follow_theme

BADGE_INSET = 12
# Subtitle text height: the picture height divided by this.
SUBTITLE_LINES = 18
RADIUS = 4


class VideoCanvas(QWidget):
    def __init__(
        self, badge_text: str, badge_icon: IconName = "Eye", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._badge_text = badge_text
        self._badge_icon: IconName = badge_icon
        self._image = QImage()
        self._subtitle = ""
        self.sink = QVideoSink(self)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.sink.subtitleTextChanged.connect(self.set_subtitle)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(badge_text)
        follow_theme(self)

    def has_frame(self) -> bool:
        return not self._image.isNull()

    def show_image(self, image: QImage) -> None:
        """Show a still frame, for the UI gallery."""
        self._image = image
        self.update()

    def clear(self) -> None:
        self._image = QImage()
        self._subtitle = ""
        self.update()

    @property
    def subtitle(self) -> str:
        return self._subtitle

    def set_subtitle(self, text: str) -> None:
        if text != self._subtitle:
            self._subtitle = text
            self.update()

    def _on_frame(self, frame: QVideoFrame) -> None:
        if frame.isValid():
            self._image = frame.toImage()
            self.update()

    def _paint_subtitle(self, painter: QPainter, picture: QRectF) -> None:
        """White text on a dark band near the bottom of the picture, as players show it."""
        font = QFont(painter.font())
        font.setPixelSize(max(14, round(picture.height() / SUBTITLE_LINES)))
        painter.setFont(font)
        room = picture.adjusted(picture.width() * 0.08, 0, -picture.width() * 0.08, 0)
        flags = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom) | int(
            Qt.TextFlag.TextWordWrap
        )
        bounds = painter.boundingRect(room, flags, self._subtitle)
        bounds.moveBottom(picture.bottom() - picture.height() * 0.06)
        band = bounds.adjusted(-10, -4, 10, 4)
        painter.fillRect(band, QColor(0, 0, 0, 170))
        painter.setPen(QColor("white"))
        painter.drawText(bounds, flags, self._subtitle)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(640, 360)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, 90)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = antialiased(self)
        p = theme.palette()
        rect = QRectF(self.rect())
        fill_rounded(painter, rect, RADIUS, p.video)
        if not self._image.isNull():
            image_size = self._image.size().toSizeF()
            scaled = image_size.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(0, 0, scaled.width(), scaled.height())
            target.moveCenter(rect.center())
            painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(target, self._image)
            if self._subtitle:
                self._paint_subtitle(painter, target)
        size = badge_size(self._badge_text, BadgeTone.ACCENT, self._badge_icon)
        paint_badge(
            painter,
            QRectF(BADGE_INSET, BADGE_INSET, size.width(), size.height()),
            self._badge_text,
            BadgeTone.ACCENT,
            self._badge_icon,
        )

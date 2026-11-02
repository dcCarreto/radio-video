from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from radio_video.models.media import MediaInfo, StreamInfo, StreamType
from radio_video.utils.formatting import (
    format_bitrate,
    format_duration,
    format_frame_rate,
    format_size,
)

STREAM_COLUMNS = ("#", "Type", "Codec", "Details", "Language", "Title")


def stream_type_label(stream: StreamInfo) -> str:
    if stream.is_attached_picture:
        return "Cover art"
    return stream.type.value.capitalize()


def stream_details(stream: StreamInfo) -> str:
    parts: list[str] = []
    if stream.type is StreamType.VIDEO:
        if stream.width and stream.height:
            parts.append(f"{stream.width}×{stream.height}")
        if stream.frame_rate and not stream.is_attached_picture:
            parts.append(format_frame_rate(stream.frame_rate))
        if stream.pixel_format:
            parts.append(stream.pixel_format)
        if stream.display_aspect_ratio:
            parts.append(f"DAR {stream.display_aspect_ratio}")
    elif stream.type is StreamType.AUDIO:
        if stream.sample_rate:
            parts.append(f"{stream.sample_rate / 1000:g} kHz")
        if stream.channel_layout:
            parts.append(stream.channel_layout)
        elif stream.channels:
            parts.append(f"{stream.channels} ch")
    if stream.bit_rate:
        parts.append(format_bitrate(stream.bit_rate))
    return " · ".join(parts)


def codec_label(stream: StreamInfo) -> str:
    codec = stream.codec_name or "unknown"
    return f"{codec} ({stream.profile})" if stream.profile else codec


class MediaInfoView(QWidget):
    """Read-only summary of an analyzed media file."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_label = QLabel()
        font = self.file_label.font()
        font.setPointSizeF(font.pointSizeF() * 1.3)
        font.setBold(True)
        self.file_label.setFont(font)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.container_label = QLabel()
        self.duration_label = QLabel()
        self.size_label = QLabel()
        self.bitrate_label = QLabel()
        self.title_label = QLabel()

        summary = QFormLayout()
        summary.addRow("Container:", self.container_label)
        summary.addRow("Duration:", self.duration_label)
        summary.addRow("Size:", self.size_label)
        summary.addRow("Bitrate:", self.bitrate_label)
        summary.addRow("Title:", self.title_label)

        self.streams = QTreeWidget()
        self.streams.setHeaderLabels(STREAM_COLUMNS)
        self.streams.setRootIsDecorated(False)
        self.streams.setUniformRowHeights(True)
        self.streams.setAlternatingRowColors(True)
        header = self.streams.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.file_label)
        layout.addLayout(summary)
        layout.addWidget(QLabel("Streams:"))
        layout.addWidget(self.streams, stretch=1)

    def set_media(self, info: MediaInfo) -> None:
        self.file_label.setText(info.path.name)
        self.file_label.setToolTip(str(info.path))
        self.container_label.setText(info.format_long_name or info.format_name)
        self.duration_label.setText(format_duration(info.duration))
        self.size_label.setText(format_size(info.size))
        self.bitrate_label.setText(format_bitrate(info.bit_rate))
        self.title_label.setText(info.tags.get("title", "—"))

        self.streams.clear()
        for stream in info.streams:
            item = QTreeWidgetItem(
                [
                    str(stream.index),
                    stream_type_label(stream),
                    codec_label(stream),
                    stream_details(stream),
                    stream.language or "",
                    stream.title or "",
                ]
            )
            if stream.codec_long_name:
                item.setToolTip(2, stream.codec_long_name)
            self.streams.addTopLevelItem(item)

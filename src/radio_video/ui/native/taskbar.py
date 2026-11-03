"""Progress on the taskbar button through ITaskbarList3 (Windows 7 and later).

Qt 6 removed QWinTaskbarButton, so the COM interface is called through ctypes. Every call is
best effort: failures are logged and ignored.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import uuid
from enum import IntEnum
from typing import Any

from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

CLSID_TASKBAR_LIST = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
IID_TASKBAR_LIST3 = "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"
CLSCTX_INPROC_SERVER = 0x1

# Vtable slots: IUnknown (0-2), ITaskbarList (3-7), ITaskbarList2 (8), ITaskbarList3 (9-).
SLOT_RELEASE = 2
SLOT_HR_INIT = 3
SLOT_SET_PROGRESS_VALUE = 9
SLOT_SET_PROGRESS_STATE = 10
PROGRESS_TOTAL = 1000


class TaskbarState(IntEnum):
    NONE = 0x0
    INDETERMINATE = 0x1
    NORMAL = 0x2
    ERROR = 0x4
    PAUSED = 0x8


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> _Guid:
        value = uuid.UUID(text)
        guid = cls()
        guid.data1, guid.data2, guid.data3 = value.fields[0], value.fields[1], value.fields[2]
        for index, byte in enumerate(value.bytes[8:]):
            guid.data4[index] = byte
        return guid


class TaskbarProgress:
    """Shows conversion progress on the window's taskbar button; red on failure."""

    def __init__(self, window: QWidget) -> None:
        self._window = window
        self._pointer: ctypes.c_void_p | None = None
        if sys.platform == "win32":
            self._pointer = self._create()

    @property
    def available(self) -> bool:
        return self._pointer is not None

    def _create(self) -> ctypes.c_void_p | None:
        if sys.platform != "win32":  # also tells type checkers on other platforms
            return None
        try:
            ole32 = ctypes.WinDLL("ole32")
            pointer = ctypes.c_void_p()
            result = ole32.CoCreateInstance(
                ctypes.byref(_Guid.parse(CLSID_TASKBAR_LIST)),
                None,
                CLSCTX_INPROC_SERVER,
                ctypes.byref(_Guid.parse(IID_TASKBAR_LIST3)),
                ctypes.byref(pointer),
            )
            if result != 0 or not pointer.value:
                logger.debug("ITaskbarList3 is not available: 0x%08x", result & 0xFFFFFFFF)
                return None
            self._call(pointer, SLOT_HR_INIT, [])
            return pointer
        except OSError:
            logger.debug("Could not create ITaskbarList3", exc_info=True)
            return None

    @staticmethod
    def _call(pointer: ctypes.c_void_p, slot: int, args: list[Any]) -> int:
        if sys.platform != "win32":
            return -1
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        argtypes: list[Any] = [ctypes.c_void_p, *(type(arg) for arg in args)]
        function = ctypes.WINFUNCTYPE(ctypes.c_long, *argtypes)(vtable[slot])
        return int(function(pointer, *args))

    def _hwnd(self) -> ctypes.c_void_p:
        return ctypes.c_void_p(int(self._window.winId()))

    def set_state(self, state: TaskbarState) -> None:
        if self._pointer is None:
            return
        self._call(self._pointer, SLOT_SET_PROGRESS_STATE, [self._hwnd(), ctypes.c_int(state)])

    def set_fraction(self, fraction: float) -> None:
        if self._pointer is None:
            return
        value = ctypes.c_ulonglong(round(min(max(fraction, 0.0), 1.0) * PROGRESS_TOTAL))
        self._call(
            self._pointer,
            SLOT_SET_PROGRESS_VALUE,
            [self._hwnd(), value, ctypes.c_ulonglong(PROGRESS_TOTAL)],
        )

    def close(self) -> None:
        if self._pointer is not None:
            self._call(self._pointer, SLOT_RELEASE, [])
            self._pointer = None

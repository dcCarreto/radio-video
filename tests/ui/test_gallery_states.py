from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from radio_video.ui import gallery_states
from radio_video.ui.dialogs.about_dialog import AboutDialog
from radio_video.ui.dialogs.failed_dialog import FailedDialog
from radio_video.ui.dialogs.quit_dialog import QuitDialog


@pytest.mark.parametrize("size", ["l", "s"])
@pytest.mark.parametrize("state", gallery_states.STATES, ids=lambda state: state.key)
def test_every_design_state_builds_and_captures(
    qapp: QApplication, state: gallery_states.GalleryState, size: str
) -> None:
    window = gallery_states.build(state, size)
    try:
        image = gallery_states.capture(window)
        assert image.size() == window.size()
        expected_dialog = {"failed": FailedDialog, "quit": QuitDialog, "about": AboutDialog}
        if state.key in expected_dialog:
            assert isinstance(window.open_dialog, expected_dialog[state.key])
    finally:
        window.discard_for_gallery()

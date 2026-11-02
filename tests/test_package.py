import re

import radio_video


def test_version_is_semantic() -> None:
    assert re.match(r"^\d+\.\d+\.\d+", radio_video.__version__)


def test_app_name() -> None:
    assert radio_video.APP_NAME == "Radio/Video"

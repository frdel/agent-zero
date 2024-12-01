from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

PROPS = (
    "user_data_dir",
    "user_config_dir",
    "user_cache_dir",
    "user_state_dir",
    "user_log_dir",
    "user_documents_dir",
    "user_downloads_dir",
    "user_pictures_dir",
    "user_videos_dir",
    "user_music_dir",
    "user_runtime_dir",
    "site_data_dir",
    "site_config_dir",
    "site_cache_dir",
    "site_runtime_dir",
)


@pytest.fixture(params=PROPS)
def func(request: SubRequest) -> str:
    return cast(str, request.param)


@pytest.fixture(params=PROPS)
def func_path(request: SubRequest) -> str:
    prop = cast(str, request.param)
    return prop.replace("_dir", "_path")


@pytest.fixture()
def props() -> tuple[str, ...]:
    return PROPS

# Copyright (C) 2019 QuantStack and the Mamba contributors.
# Copyright (C) 2022 Anaconda, Inc
# Copyright (C) 2023 conda
# SPDX-License-Identifier: BSD-3-Clause

# TODO: Temporarily vendored from mamba.utils v0.19 on 2021.12.02
# Decide what to do with it when we split into a plugin
# 2022.02.15: updated vendored parts to v0.21.2
# 2022.11.14: only keeping channel prioritization and context initialization logic now
# 2024.09.24: parameterize init_api_context

from __future__ import annotations

import logging
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import libmambapy as api
from conda.base.constants import ChannelPriority
from conda.base.context import context
from conda.common.compat import on_win

if TYPE_CHECKING:
    from .index import _ChannelRepoInfo


log = logging.getLogger(f"conda.{__name__}")


@lru_cache(maxsize=1)
def mamba_version():
    return version("libmambapy")


def _get_base_url(url, name=None):
    tmp = url.rsplit("/", 1)[0]
    if name:
        if tmp.endswith(name):
            return tmp.rsplit("/", 1)[0]
    return tmp


def set_channel_priorities(index: dict[str, _ChannelRepoInfo], has_priority: bool = None):
    """
    This function was part of mamba.utils.load_channels originally.
    We just split it to reuse it a bit better.
    """
    if not index:
        return index

    if has_priority is None:
        has_priority = context.channel_priority in [
            ChannelPriority.STRICT,
            ChannelPriority.FLEXIBLE,
        ]

    subprio_index = len(index)
    if has_priority:
        # max channel priority value is the number of unique channels
        channel_prio = len({info.channel.canonical_name for info in index.values()})
        current_channel = next(iter(index.values())).channel.canonical_name

    for info in index.values():
        # add priority here
        if has_priority:
            if info.channel.canonical_name != current_channel:
                channel_prio -= 1
                current_channel = info.channel.canonical_name
            priority = channel_prio
        else:
            priority = 0
        if has_priority:
            # NOTE: -- this is the whole reason we are vendoring this file --
            # We are patching this from 0 to 1, starting with mamba 0.19
            # Otherwise, test_create::test_force_remove fails :shrug:
            subpriority = 1
        else:
            subpriority = subprio_index
            subprio_index -= 1

        if not context.json:
            log.debug(
                "Channel: %s, platform: %s, prio: %s : %s",
                info.channel,
                info.channel.subdir,
                priority,
                subpriority,
            )
        info.repo.set_priority(priority, subpriority)

    return index


def init_api_context(
    channels: Iterable[str] | None = None,
    platform: str = None,
    target_prefix: str = None,
) -> api.Context:
    # This function has to be called BEFORE 1st initialization of the context
    api.Context.use_default_signal_handler(False)
    api_ctx = api.Context()

    # Output params
    api_ctx.output_params.json = context.json
    api_ctx.output_params.quiet = context.quiet
    api_ctx.output_params.verbosity = context.verbosity
    api_ctx.set_verbosity(context.verbosity)
    if api_ctx.output_params.json:
        api.cancel_json_output()

    # Prefix params
    api_ctx.prefix_params.conda_prefix = context.conda_prefix
    api_ctx.prefix_params.root_prefix = context.root_prefix
    if on_win and target_prefix == "/":
        # workaround for strange bug in libmamba transforming "/"" into "\\conda-bld" :shrug:
        target_prefix = Path.cwd().parts[0]
    target_prefix = target_prefix if target_prefix is not None else context.target_prefix
    api_ctx.prefix_params.target_prefix = target_prefix

    # Networking params -- we always operate offline from libmamba's perspective
    api_ctx.remote_fetch_params.user_agent = context.user_agent
    api_ctx.local_repodata_ttl = context.local_repodata_ttl
    api_ctx.offline = True
    api_ctx.use_index_cache = True

    # General params
    api_ctx.add_pip_as_python_dependency = context.add_pip_as_python_dependency
    api_ctx.always_yes = context.always_yes
    api_ctx.dry_run = context.dry_run
    api_ctx.envs_dirs = context.envs_dirs
    api_ctx.pkgs_dirs = context.pkgs_dirs
    api_ctx.use_lockfiles = False
    api_ctx.use_only_tar_bz2 = context.use_only_tar_bz2

    # Channels and platforms
    api_ctx.platform = platform if platform is not None else context.subdir
    api_ctx.channels = list(channels) if channels is not None else context.channels
    api_ctx.channel_alias = str(_get_base_url(context.channel_alias.url(with_credentials=True)))

    RESERVED_NAMES = {"local", "defaults"}
    additional_custom_channels = {}
    for el in context.custom_channels:
        if context.custom_channels[el].canonical_name not in RESERVED_NAMES:
            additional_custom_channels[el] = _get_base_url(
                context.custom_channels[el].url(with_credentials=True), el
            )
    api_ctx.custom_channels = additional_custom_channels

    additional_custom_multichannels = {}
    for el in context.custom_multichannels:
        if el not in RESERVED_NAMES:
            additional_custom_multichannels[el] = []
            for c in context.custom_multichannels[el]:
                additional_custom_multichannels[el].append(
                    _get_base_url(c.url(with_credentials=True))
                )
    api_ctx.custom_multichannels = additional_custom_multichannels

    api_ctx.default_channels = [
        _get_base_url(x.url(with_credentials=True)) for x in context.default_channels
    ]

    api_ctx.conda_build_local_paths = list(context.conda_build_local_paths)

    if context.channel_priority is ChannelPriority.STRICT:
        api_ctx.channel_priority = api.ChannelPriority.kStrict
    elif context.channel_priority is ChannelPriority.FLEXIBLE:
        api_ctx.channel_priority = api.ChannelPriority.kFlexible
    elif context.channel_priority is ChannelPriority.DISABLED:
        api_ctx.channel_priority = api.ChannelPriority.kDisabled

    return api_ctx

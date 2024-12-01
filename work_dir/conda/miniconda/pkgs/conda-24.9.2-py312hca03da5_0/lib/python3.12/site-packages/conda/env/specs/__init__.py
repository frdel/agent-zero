# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ...deprecations import deprecated
from ...exceptions import (
    EnvironmentFileExtensionNotValid,
    EnvironmentFileNotFound,
    SpecNotFound,
)
from ...gateways.connection.session import CONDA_SESSION_SCHEMES
from .requirements import RequirementsSpec
from .yaml_file import YamlFileSpec

if TYPE_CHECKING:
    from typing import Type, Union

    FileSpecTypes = Union[Type[YamlFileSpec], Type[RequirementsSpec]]
    SpecTypes = Union[YamlFileSpec, RequirementsSpec]


def get_spec_class_from_file(filename: str) -> FileSpecTypes:
    """
    Determine spec class to use from the provided ``filename``

    :raises EnvironmentFileExtensionNotValid | EnvironmentFileNotFound:
    """
    # Check extensions
    all_valid_exts = {*YamlFileSpec.extensions, *RequirementsSpec.extensions}
    _, ext = os.path.splitext(filename)

    # First check if file exists and test the known valid extension for specs
    file_exists = (
        os.path.isfile(filename) or filename.split("://", 1)[0] in CONDA_SESSION_SCHEMES
    )
    if file_exists:
        if ext == "" or ext not in all_valid_exts:
            raise EnvironmentFileExtensionNotValid(filename)
        elif ext in YamlFileSpec.extensions:
            return YamlFileSpec
        elif ext in RequirementsSpec.extensions:
            return RequirementsSpec
    raise EnvironmentFileNotFound(filename=filename)


@deprecated.argument("24.7", "25.3", "remote_definition")
def detect(
    name: str | None = None,
    filename: str | None = None,
    directory: str | None = None,
) -> SpecTypes:
    """
    Return the appropriate spec type to use.

    :raises SpecNotFound: Raised if no suitable spec class could be found given the input
    :raises EnvironmentFileExtensionNotValid | EnvironmentFileNotFound:
    """
    if filename is not None:
        spec_class = get_spec_class_from_file(filename)
        spec = spec_class(name=name, filename=filename, directory=directory)
        if spec.can_handle():
            return spec

    raise SpecNotFound(spec.msg)

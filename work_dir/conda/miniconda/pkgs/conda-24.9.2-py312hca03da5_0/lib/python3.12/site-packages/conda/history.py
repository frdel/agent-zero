# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools interfacing with conda's history file."""

from __future__ import annotations

import codecs
import logging
import os
import re
import sys
import time
import warnings
from ast import literal_eval
from errno import EACCES, EPERM, EROFS
from itertools import islice
from operator import itemgetter
from os.path import isdir, isfile, join
from textwrap import dedent

from . import __version__ as CONDA_VERSION
from .auxlib.ish import dals
from .base.constants import DEFAULTS_CHANNEL_NAME
from .base.context import context
from .common.compat import ensure_text_type, open_utf8
from .common.iterators import groupby_to_dict as groupby
from .common.path import paths_equal
from .core.prefix_data import PrefixData
from .exceptions import CondaHistoryError, NotWritableError
from .gateways.disk.update import touch
from .models.dist import dist_str_to_quad
from .models.match_spec import MatchSpec
from .models.version import VersionOrder, version_relation_re

log = logging.getLogger(__name__)


class CondaHistoryWarning(Warning):
    pass


def write_head(fo):
    fo.write("==> {} <==\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    fo.write("# cmd: {}\n".format(" ".join(ensure_text_type(s) for s in sys.argv)))
    fo.write(
        "# conda version: {}\n".format(".".join(islice(CONDA_VERSION.split("."), 3)))
    )


def is_diff(content):
    return any(s.startswith(("-", "+")) for s in content)


def pretty_diff(diff):
    added = {}
    removed = {}
    for s in diff:
        fn = s[1:]
        name, version, _, channel = dist_str_to_quad(fn)
        if channel != DEFAULTS_CHANNEL_NAME:
            version += f" ({channel})"
        if s.startswith("-"):
            removed[name.lower()] = version
        elif s.startswith("+"):
            added[name.lower()] = version
    changed = set(added) & set(removed)
    for name in sorted(changed):
        yield f" {name}  {{{removed[name]} -> {added[name]}}}"
    for name in sorted(set(removed) - changed):
        yield f"-{name}-{removed[name]}"
    for name in sorted(set(added) - changed):
        yield f"+{name}-{added[name]}"


def pretty_content(content):
    if is_diff(content):
        return pretty_diff(content)
    else:
        return iter(sorted(content))


class History:
    com_pat = re.compile(r"#\s*cmd:\s*(.+)")
    spec_pat = re.compile(r"#\s*(\w+)\s*specs:\s*(.+)?")
    conda_v_pat = re.compile(r"#\s*conda version:\s*(.+)")

    def __init__(self, prefix):
        self.prefix = prefix
        self.meta_dir = join(prefix, "conda-meta")
        self.path = join(self.meta_dir, "history")

    def __enter__(self):
        self.init_log_file()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.update()

    def init_log_file(self):
        touch(self.path, True)

    def file_is_empty(self):
        return os.stat(self.path).st_size == 0

    def update(self) -> None:
        """Update the history file (creating a new one if necessary)."""
        try:
            try:
                last = set(self.get_state())
            except CondaHistoryError as e:
                warnings.warn(f"Error in {self.path}: {e}", CondaHistoryWarning)
                return
            pd = PrefixData(self.prefix)
            curr = {prefix_rec.dist_str() for prefix_rec in pd.iter_records()}
            self.write_changes(last, curr)
        except OSError as e:
            if e.errno in (EACCES, EPERM, EROFS):
                raise NotWritableError(self.path, e.errno)
            else:
                raise

    def parse(self) -> list[tuple[str, set[str], list[str]]]:
        """Parse the history file.

        Return a list of tuples(datetime strings, set of distributions/diffs, comments).

        Comments appearing before the first section header (e.g. ``==> 2024-01-01 00:00:00 <==``)
        in the history file will be ignored.
        """
        res = []
        if not isfile(self.path):
            return res
        sep_pat = re.compile(r"==>\s*(.+?)\s*<==")
        with open_utf8(self.path) as f:
            lines = f.read().splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = sep_pat.match(line)
            if m:
                res.append((m.group(1), set(), []))
            elif line.startswith("#") and res:
                res[-1][2].append(line)
            elif res:
                res[-1][1].add(line)
        return res

    @staticmethod
    def _parse_old_format_specs_string(specs_string):
        """
        Parse specifications string that use conda<4.5 syntax.

        Examples
        --------
          - "param >=1.5.1,<2.0'"
          - "python>=3.5.1,jupyter >=1.0.0,<2.0,matplotlib >=1.5.1,<2.0"
        """
        specs = []
        for spec in specs_string.split(","):
            # If the spec starts with a version qualifier, then it actually belongs to the
            # previous spec. But don't try to join if there was no previous spec.
            if version_relation_re.match(spec) and specs:
                specs[-1] = ",".join([specs[-1], spec])
            else:
                specs.append(spec)
        return specs

    @classmethod
    def _parse_comment_line(cls, line):
        """
        Parse comment lines in the history file.

        These lines can be of command type or action type.

        Examples
        --------
          - "# cmd: /scratch/mc3/bin/conda install -c conda-forge param>=1.5.1,<2.0"
          - "# install specs: python>=3.5.1,jupyter >=1.0.0,<2.0,matplotlib >=1.5.1,<2.0"
        """
        item = {}
        m = cls.com_pat.match(line)
        if m:
            argv = m.group(1).split()
            if argv[0].endswith("conda"):
                argv[0] = "conda"
            item["cmd"] = argv

        m = cls.conda_v_pat.match(line)
        if m:
            item["conda_version"] = m.group(1)

        m = cls.spec_pat.match(line)
        if m:
            action, specs_string = m.groups()
            specs_string = specs_string or ""
            item["action"] = action

            if specs_string.startswith("["):
                specs = literal_eval(specs_string)
            elif "[" not in specs_string:
                specs = History._parse_old_format_specs_string(specs_string)

            specs = [spec for spec in specs if spec and not spec.endswith("@")]

            if specs and action in ("update", "install", "create"):
                item["update_specs"] = item["specs"] = specs
            elif specs and action in ("remove", "uninstall"):
                item["remove_specs"] = item["specs"] = specs
            elif specs and action in ("neutered",):
                item["neutered_specs"] = item["specs"] = specs

        return item

    def get_user_requests(self):
        """Return a list of user requested items.

        Each item is a dict with the following keys:
        'date': the date and time running the command
        'cmd': a list of argv of the actual command which was run
        'action': install/remove/update
        'specs': the specs being used
        """
        res = []
        for dt, unused_cont, comments in self.parse():
            item = {"date": dt}
            for line in comments:
                comment_items = self._parse_comment_line(line)
                item.update(comment_items)

            if "cmd" in item:
                res.append(item)

            dists = groupby(itemgetter(0), unused_cont)
            item["unlink_dists"] = dists.get("-", ())
            item["link_dists"] = dists.get("+", ())

        conda_versions_from_history = tuple(
            x["conda_version"] for x in res if "conda_version" in x
        )
        if conda_versions_from_history and not context.allow_conda_downgrades:
            minimum_conda_version = sorted(
                conda_versions_from_history, key=VersionOrder
            )[-1]
            minimum_major_minor = ".".join(islice(minimum_conda_version.split("."), 2))
            current_major_minor = ".".join(islice(CONDA_VERSION.split("."), 2))
            if VersionOrder(current_major_minor) < VersionOrder(minimum_major_minor):
                message = dals(
                    """
                This environment has previously been operated on by a conda version that's newer
                than the conda currently being used. A newer version of conda is required.
                  target environment location: %(target_prefix)s
                  current conda version: %(conda_version)s
                  minimum conda version: %(minimum_version)s
                """
                ) % {
                    "target_prefix": self.prefix,
                    "conda_version": CONDA_VERSION,
                    "minimum_version": minimum_major_minor,
                }
                if not paths_equal(self.prefix, context.root_prefix):
                    message += dedent(
                        """
                    Update conda and try again.
                        $ conda install -p "%(base_prefix)s" "conda>=%(minimum_version)s"
                    """
                    ) % {
                        "base_prefix": context.root_prefix,
                        "minimum_version": minimum_major_minor,
                    }
                message += dedent(
                    """
                To work around this restriction, one can also set the config parameter
                'allow_conda_downgrades' to False at their own risk.
                """
                )

                # TODO: we need to rethink this.  It's fine as a warning to try to get users
                #    to avoid breaking their system.  However, right now it is preventing
                #    normal conda operation after downgrading conda.
                # raise CondaUpgradeError(message)

        return res

    def get_requested_specs_map(self):
        # keys are package names and values are specs
        spec_map = {}
        for request in self.get_user_requests():
            remove_specs = (MatchSpec(spec) for spec in request.get("remove_specs", ()))
            for spec in remove_specs:
                spec_map.pop(spec.name, None)
            update_specs = (MatchSpec(spec) for spec in request.get("update_specs", ()))
            spec_map.update((s.name, s) for s in update_specs)
            # here is where the neutering takes effect, overriding past values
            neutered_specs = (
                MatchSpec(spec) for spec in request.get("neutered_specs", ())
            )
            spec_map.update((s.name, s) for s in neutered_specs)

        # Conda hasn't always been good about recording when specs have been removed from
        # environments.  If the package isn't installed in the current environment, then we
        # shouldn't try to force it here.
        prefix_recs = {_.name for _ in PrefixData(self.prefix).iter_records()}
        return {name: spec for name, spec in spec_map.items() if name in prefix_recs}

    def construct_states(self):
        """Return a list of tuples(datetime strings, set of distributions)."""
        res = []
        cur = set()
        for dt, cont, unused_com in self.parse():
            if not is_diff(cont):
                cur = cont
            else:
                for s in cont:
                    if s.startswith("-"):
                        cur.discard(s[1:])
                    elif s.startswith("+"):
                        cur.add(s[1:])
                    else:
                        raise CondaHistoryError(f"Did not expect: {s}")
            res.append((dt, cur.copy()))
        return res

    def get_state(self, rev=-1):
        """Return the state, i.e. the set of distributions, for a given revision.

        Defaults to latest (which is the same as the current state when
        the log file is up-to-date).

        Returns a list of dist_strs.
        """
        states = self.construct_states()
        if not states:
            return set()
        times, pkgs = zip(*states)
        return pkgs[rev]

    def print_log(self):
        for i, (date, content, unused_com) in enumerate(self.parse()):
            print("%s  (rev %d)" % (date, i))
            for line in pretty_content(content):
                print(f"    {line}")
            print()

    def object_log(self):
        result = []
        for i, (date, content, unused_com) in enumerate(self.parse()):
            # Based on Mateusz's code; provides more details about the
            # history event
            event = {
                "date": date,
                "rev": i,
                "install": [],
                "remove": [],
                "upgrade": [],
                "downgrade": [],
            }
            added = {}
            removed = {}
            if is_diff(content):
                for pkg in content:
                    name, version, build, channel = dist_str_to_quad(pkg[1:])
                    if pkg.startswith("+"):
                        added[name.lower()] = (version, build, channel)
                    elif pkg.startswith("-"):
                        removed[name.lower()] = (version, build, channel)

                changed = set(added) & set(removed)
                for name in sorted(changed):
                    old = removed[name]
                    new = added[name]
                    details = {
                        "old": "-".join((name,) + old),
                        "new": "-".join((name,) + new),
                    }

                    if new > old:
                        event["upgrade"].append(details)
                    else:
                        event["downgrade"].append(details)

                for name in sorted(set(removed) - changed):
                    event["remove"].append("-".join((name,) + removed[name]))

                for name in sorted(set(added) - changed):
                    event["install"].append("-".join((name,) + added[name]))
            else:
                for pkg in sorted(content):
                    event["install"].append(pkg)
            result.append(event)
        return result

    def write_changes(self, last_state, current_state):
        if not isdir(self.meta_dir):
            os.makedirs(self.meta_dir)
        with codecs.open(self.path, mode="ab", encoding="utf-8") as fo:
            write_head(fo)
            for fn in sorted(last_state - current_state):
                fo.write(f"-{fn}\n")
            for fn in sorted(current_state - last_state):
                fo.write(f"+{fn}\n")

    def write_specs(self, remove_specs=(), update_specs=(), neutered_specs=()):
        remove_specs = [str(MatchSpec(s)) for s in remove_specs]
        update_specs = [str(MatchSpec(s)) for s in update_specs]
        neutered_specs = [str(MatchSpec(s)) for s in neutered_specs]
        if any((update_specs, remove_specs, neutered_specs)):
            with codecs.open(self.path, mode="ab", encoding="utf-8") as fh:
                if remove_specs:
                    fh.write(f"# remove specs: {remove_specs}\n")
                if update_specs:
                    fh.write(f"# update specs: {update_specs}\n")
                if neutered_specs:
                    fh.write(f"# neutered specs: {neutered_specs}\n")


if __name__ == "__main__":
    from pprint import pprint

    # Don't use in context manager mode---it augments the history every time
    h = History(sys.prefix)
    pprint(h.get_user_requests())
    print(h.get_requested_specs_map())

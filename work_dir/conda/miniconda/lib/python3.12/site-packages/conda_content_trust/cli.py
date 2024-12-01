# Copyright (C) 2019 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
This module provides the CLI interface for conda-content-trust.
This is intended to provide a command-line signing and metadata update
interface.
"""
from argparse import ArgumentParser
from copy import deepcopy
from json import dumps

from . import __version__
from . import authentication as cct_authentication
from . import root_signing as cct_root_signing
from . import signing as cct_signing
from .common import (
    CCT_Error,
    PrivateKey,
    is_gpg_fingerprint,
    is_hex_key,
    load_metadata_from_file,
    write_metadata_to_file,
)


def cli(args=None):
    parser = ArgumentParser(
        description="Signing and verification tools for Conda",
        conflict_handler="resolve",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        help="Show the conda-content-trust version number and exit.",
        version="conda-content-trust %s" % __version__,
    )

    # Create separate parsers for the subcommands.
    sp = parser.add_subparsers(title="subcommands", dest="subcommand_name")

    # subcommand: sign-artifacts

    p_signrepo = sp.add_parser(
        "sign-artifacts",
        help=(
            "Given a repodata.json "
            "file, produce signatures over the metadata for each artifact listed, "
            "and update the repodata.json file with their individual signatures."
        ),
    )
    p_signrepo.add_argument(
        "repodata_fname",
        help=(
            "the filename of a repodata.json file from "
            "which to retrieve metadata for individual artifacts."
        ),
    )
    p_signrepo.add_argument(
        "private_key_fname",
        help=(
            "the filename of a file containing a "
            "hex string representation of an ed25519 private key to be used "
            "to sign each artifact's metadata"
        ),
    )

    # subcommand: verify-metadata

    p_verifymd = sp.add_parser(
        "verify-metadata",
        help=(
            "Uses the first (trusted) metadata file "
            "to verify the second (not yet trusted) metadata file.  For "
            "example, "
            '"conda-content-trust verify-metadata 4.root.json 5.root.json"'
            " to verify version 5 of root based on version 4 of root, or "
            '"conda-content-trust verify-metadata 4.root.json key_mgr.json" '
            "to verify key manager metadata based on version 4 of root."
        ),
    )
    p_verifymd.add_argument(
        "trusted_metadata_filename",
        help=(
            "the filename of the "
            "already-trusted metadata file that sets the rules for verifying "
            "the untrusted metadata file"
        ),
    )
    p_verifymd.add_argument(
        "untrusted_metadata_filename",
        help=("the filename of the " "(untrusted) metadata file to verify"),
    )

    # subcommand: modify-metadata

    p_modifymd = sp.add_parser(
        "modify-metadata",
        help=(
            "Interactive metadata modification.  Use "
            "this to produce a new version of a metadata file (like root.json "
            "or key_mgr.json), or correct an error in an unpublished metadata "
            "file, or review and sign a metadata file.  This increments "
            "version number / timestamp, reports changes on console, etc. For "
            'example, "conda-content-trust modify-metadata 8.root.json" '
            "for assistance in "
            "producing a new version of root (version 9) using version 8."
        ),
    )
    p_modifymd.add_argument(
        "metadata_filename",
        help=("the filename of the existing metadata " "file to modify"),
    )

    # If we're missing optional requirements for the next few options, note
    # that in their help strings.
    opt_reqs_str = ""
    if not cct_root_signing.SSLIB_AVAILABLE:
        opt_reqs_str = (
            "[Unavailable]: Requires optional "
            "dependencies: securesystemslib and gpg.  "
        )

    # subcommand: gpg-key-lookup
    p_gpglookup = sp.add_parser(
        "gpg-key-lookup",
        help=(
            opt_reqs_str
            + "Given the OpenPGP fingerprint of an ed25519-type OpenPGP key, fetch "
            "the actual ed25519 public key value of the underlying key."
        ),
    )
    p_gpglookup.add_argument(
        "gpg_key_fingerprint",
        help=(
            "the 40-hex-character key fingerprint (long keyid) for the "
            "OpenPGP/GPG key that you want to sign something with.  Do not "
            'add prefix "0x".'
        ),
    )

    # subcommand: gpg-sign

    p_gpgsign = sp.add_parser(
        "gpg-sign",
        help=(
            opt_reqs_str + "Sign a given "
            "piece of metadata using GPG instead of the usual signing "
            "mechanisms.  Takes an OpenPGP key fingerprint and a filename."
        ),
    )
    p_gpgsign.add_argument(
        "gpg_key_fingerprint",
        help=(
            "the 40-hex-character key fingerprint (long keyid) for the "
            "OpenPGP/GPG key that you want to sign something with.  Do not "
            'add prefix "0x".'
        ),
    )
    p_gpgsign.add_argument(
        "filename", help=("the filename of the file that will be signed")
    )

    args = parser.parse_args(args)

    if args.subcommand_name == "gpg-sign":
        # TODO: Validate arguments.

        # Strip any whitespace from the key fingerprint and lowercase it.
        # GPG pops out keys in a variety of whitespace arrangements and cases,
        # so this is necessary for convenience.
        gpg_key_fingerprint = "".join(args.gpg_key_fingerprint.split()).lower()

        cct_root_signing.sign_root_metadata_via_gpg(args.filename, gpg_key_fingerprint)

    elif args.subcommand_name == "sign-artifacts":
        with open(args.private_key_fname) as key_fobj:
            # Lower-case the hex string and ignore any whitespace before and
            # after it (in case someone adds some).
            private_key_hex = key_fobj.read().strip().lower()

        if not is_hex_key(private_key_hex):
            print(
                "ABORTED.  Expected key file to contain only a hex string "
                "representation of an ed25519 key.  It does not."
            )
            return

        cct_signing.sign_all_in_repodata(args.repodata_fname, args.private_key_hex)

    elif args.subcommand_name == "gpg-key-lookup":
        gpg_key_fingerprint = "".join(args.gpg_key_fingerprint.split()).lower()
        keyval = cct_root_signing.fetch_keyval_from_gpg(gpg_key_fingerprint)
        print("Underlying ed25519 public key value: " + str(keyval))

    elif args.subcommand_name == "modify-metadata":
        # `conda-content-trust update-metadata <metadata file to produce new version of>`

        # underlying functions: build_delegating_metadata,
        # load_metadata_from_file

        # given a metadata file, increment the version number and timestamps,
        # reporting the changes on the console

        # strip signatures

        # indicate what signatures are required

        # ask if the user wants to sign; query for the key hex or fname;
        # ideally, offer this functionality for both root and non-root keys.
        # For root metadata, we can (and should) also report which keys are
        # expected / still needed in order for the metadata to be verifiable
        # according to the old metadata and the new metadata

        old_metadata = load_metadata_from_file(args.metadata_filename)

        # new_metadata = cct_metadata_construction.interactive_modify_metadata(old_metadata)
        # if new_metadata is not None and new_metadata:
        #     write_metadata_to_file(new_metadata, args.metadata_filename)

        interactive_modify_metadata(old_metadata)

    elif args.subcommand_name == "verify-metadata":
        # `conda-content-trust verify-metadata <trusted delegating metadata> <untrusted
        # metadata> <(optional) role name>`

        # underlying functions: cct_authentication.verify_delegation,
        # load_metadata_from_file

        # takes two metadata files, the first being a trusted file that should
        # provide the verification criteria (expected keys and expected number
        # of keys) for the second file.  This should support root-root
        # verification (root chaining as currently implemented in
        # conda-content-trust) and delegation from one metadata type to another
        # (e.g. root to key_mgr)

        # conveys to the user whether or not the file is trusted, and for what
        # role.  e.g., would convey that the first file is (e.g.) a root
        # metadata file, that it provides a delegation to <role name>, and that
        # the <untrusted metadata> file provides <role name> and is signed
        # appropriately based on what the root metadata file requires of that
        # delegation.

        untrusted_metadata = load_metadata_from_file(args.untrusted_metadata_filename)

        trusted_metadata = load_metadata_from_file(args.trusted_metadata_filename)

        # TODO✅: Argument validation via the check_format_* calls.

        metadata_type = untrusted_metadata["signed"]["type"]

        if metadata_type == "root":
            # Verifying root has additional steps beyond verify_delegation.
            try:
                cct_authentication.verify_root(trusted_metadata, untrusted_metadata)
                print("Root metadata verification successful.")
                return 0  # success

            except CCT_Error as e:
                errorcode = 10
                errorstring = str(e)

        else:
            # Verifying anything other than root just uses verify_delegation
            # directly.
            try:
                cct_authentication.verify_delegation(
                    delegation_name=metadata_type,
                    untrusted_delegated_metadata=untrusted_metadata,
                    trusted_delegating_metadata=trusted_metadata,
                )
                print("Metadata verification successful.")
                return 0  # success

            except CCT_Error as e:
                errorcode = 20
                errorstring = str(e)

        # We should only get here if verification failed.
        print(
            "Verification of untrusted metadata failed.  Metadata "
            'type was "' + metadata_type + '".  Error reads:\n  "' + errorstring + '"'
        )
        return errorcode  # failure; exit code

    else:
        parser.print_help()


def interactive_modify_metadata(metadata):
    """ """

    # Update version if there is a version.
    # Update timestamp if there is a timestamp.
    #
    # Show metadata contents ('signed') -- pprint?
    #    indicate updated version/timestamp
    #
    # Changes phase:
    #    Prompt to
    #       (m) modify a value, (a) add a new entry, (d) delete an entry,
    #       (r) revert to original, (f) finish and sign ((move on to signing
    #       prompts))
    #
    # Signing phase:
    #   Show metadata again, ask if metadata looks right
    #   Show what keys the original was signed by and ask if those should be
    #     the keys used for the new version.
    #        ((Later: if root, vet against contents of new and old root versions))
    #   Prompt for key (raw key file, raw key data, or gpg key fingerprint)
    #   Sign using the given key (gpg if gpg, else normal signing mechanism).
    #   Write (making sure not to overwrite, and -- if root -- making sure to
    #     prepend "<version>." to root.json file.

    initial_metadata = metadata
    metadata = deepcopy(initial_metadata)

    try:
        import pygments
        import pygments.formatters
        import pygments.lexers
    except ImportError:
        print(
            "interactive modify-metadata mode employs pygments for syntax "
            "highlighting, if pygments is available.  pygments was not "
            "found, so the JSON contents will be... uglier than they "
            "would otherwise be.  If you would like syntax highlighting "
            "and prettier printing of JSON, you may install pygments."
        )
        pygments = None
        from pprint import pprint

    # Build the modification options and prompt.
    def promptfor(s):
        return input(F_INSTRUCT + "\n----- Please provide " + s + ENDC + ": ")

    def fn_write():
        fname = promptfor("a filename to save this metadata as")
        print("Writing to file....")
        write_metadata_to_file(metadata, fname)
        print("Modified metadata written!")
        return 1

    def fn_abort():
        # TODO✅: Ask to confirm.
        print(RED + BOLD + "\nAborting!\n" + ENDC)
        return 1

    def fn_addsig():
        if not cct_root_signing.SSLIB_AVAILABLE:
            print(
                F_OPTS + "Signing.  " + RED + "Please ABORT (control-c) if "
                "the metadata above is not EXACTLY what you want to sign!" + ENDC
            )
        key = promptfor(
            "a key: either:\n     - a 40-character-hex-string GPG PUBLIC "
            "key fingerprint\n"
            "       for GPG keys (e.g. root YubiKeys), or \n     - a "
            "64-character-hex-string PRIVATE key value for normal "
            "keys.\n\n     Whitespace will be removed and characters will "
            "be lowercased.\n     Key"
        )
        key = "".join(key.split()).lower()

        if is_hex_key(key):
            private_key = PrivateKey.from_hex(key)
            cct_signing.sign_signable(metadata, private_key)
            print(F_OPTS + "\n\n--- Successfully signed!  Please save." + ENDC)

        elif is_gpg_fingerprint(key):
            try:
                cct_root_signing.sign_root_metadata_dict_via_gpg(metadata, key)
            except:
                print(
                    F_OPTS
                    + "\n\n--- "
                    + RED
                    + "Signing FAILED."
                    + F_OPTS
                    + "  Do you have this key loaded in GPG on "
                    "this system?"
                )
            else:
                print(F_OPTS + "\n\n--- Successfully signed!  Please save." + ENDC)

        else:
            print(F_OPTS + RED + "Unable to recognize key.  Please try again." + ENDC)
        return 0

    def fn_remsig():
        return 0

    def fn_update():
        return 0

    def fn_adddel():
        return 0

    def fn_remdel():
        return 0

    def fn_thresh():
        delegation = promptfor(
            "a delegation name (one of the entries in the"
            '\n     "delegations" dictionary in the metadata above).  '
            "This will\n     be the delegation whose threshold number of "
            "required keys we\n     will change."
        )
        if delegation not in metadata["signed"]["delegations"]:
            print(
                F_OPTS + "\n\n--- " + RED + "Unable to find that delegation."
                "  Please try again." + ENDC
            )
            return 0

        new_thresh = promptfor(
            "a new threshold value.  The current value is "
            + str(metadata["signed"]["delegations"][delegation]["threshold"])
        )

        try:
            new_thresh = int(new_thresh)
            assert new_thresh >= 1
        except:
            print(
                F_OPTS + "\n--- " + RED + "Invalid value.  Expecting integer "
                "greater than or equal to 1.  Please try again." + ENDC
            )
            return 0

        metadata["signed"]["delegations"][delegation]["threshold"] = new_thresh

        print(F_OPTS + "\n--- Threshold successfully updated." + ENDC)

        return 0

    def fn_addkey():
        return 0

    def fn_remkey():
        return 0

    options = {
        0: [fn_write, "Done: write and save metadata"],
        1: [fn_abort, "Abort: discard changes -- abort without writing"],
        2: [fn_addsig, "Add a signature (sign with a key you have)"],
        3: [fn_remsig, "Remove a signature"],
        4: [fn_update, "Update any top-level dictionary entry"],
        5: [fn_adddel, "Add a delegation"],
        6: [fn_remdel, "Remove a delegation"],
        7: [fn_thresh, "Change the threshold number of keys for a delegation"],
        8: [fn_addkey, "Add an authorized key to a delegation"],
        9: [fn_remkey, "Remove an authorized key from a delegation"],
    }

    option_text = (
        F_INSTRUCT + "\n--- Please choose an operation by entering its "
        "number\n" + ENDC
    )
    for index in options:
        option_text += (
            "    "
            + F_LABEL
            + str(index)
            + ENDC
            + ": "
            + options[index][1]
            + ENDC
            + "\n"
        )

    done = False
    while not done:
        print(
            F_OPTS
            + BOLD
            + "\n\n---------------------\n--- Current metadata:\n---------------------\n"
            + ENDC
        )

        if pygments is not None:
            formatted_metadata = dumps(metadata, sort_keys=True, indent=4)
            print(
                pygments.highlight(
                    formatted_metadata.encode("utf-8"),
                    pygments.lexers.JsonLexer(),
                    pygments.formatters.TerminalFormatter(),
                )
            )
        else:
            pprint(metadata)

        print(option_text)
        selected = input(F_OPTS + "Choice: " + ENDC)
        try:
            selected = int(selected)
        except:
            print(RED + BOLD + "\nInvalid entry.  Try again.\n" + ENDC)
            continue
        if selected not in options:
            print(RED + BOLD + "\nInvalid entry.  Try again.\n" + ENDC)
            continue

        print(F_OPTS + '\nChose "' + options[selected][1] + '"' + ENDC)

        done = options[selected][0]()  # Run the func associated with the option.

    # Pull modified from debugging script
    # Pull modified from debugging script
    # Pull modified from debugging script


# Basic text formatting string constants
PINK = "\033[95m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
ENDC = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"

# Complete formats
F_LABEL = ENDC + UNDERLINE + BOLD + PINK
F_INSTRUCT = ENDC + BOLD + PINK
F_OPTS = ENDC + GREEN


if __name__ == "__main__":
    import sys

    exit_status = cli(sys.argv[1:])
    sys.exit(exit_status)

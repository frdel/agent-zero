from conda import plugins


def pre_command_patcher(command):
    try:
        from . import patch  # noqa

        patch.main(plugin=True)
    except Exception as exc:  # pragma: nocover
        print("Error loading anaconda-anon-usage:", exc)


@plugins.hookimpl
def conda_pre_commands():
    yield plugins.CondaPreCommand(
        name="anaconda-anon-usage",
        action=pre_command_patcher,
        run_for={
            "info",
            "config",
            "install",
            "create",
            "uninstall",
            "env_create",
            "search",
        },  # which else?
    )

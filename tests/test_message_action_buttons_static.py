from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_message_action_buttons_are_not_text_selectable() -> None:
    css = PROJECT_ROOT.joinpath(
        "webui",
        "components",
        "messages",
        "action-buttons",
        "simple-action-buttons.css",
    ).read_text(encoding="utf-8")

    block = css[css.index(".step-action-buttons {"):css.index("}", css.index(".step-action-buttons {"))]
    assert "user-select: none;" in block


def test_streaming_updates_keep_action_button_nodes_mounted() -> None:
    actions = PROJECT_ROOT.joinpath(
        "webui",
        "components",
        "messages",
        "action-buttons",
        "simple-action-buttons.js",
    ).read_text(encoding="utf-8")
    messages = PROJECT_ROOT.joinpath("webui", "js", "messages.js").read_text(
        encoding="utf-8"
    )

    assert "existing.__actionHandler = button.__actionHandler" in actions
    assert "syncActionButtons(stepActionBtns, actionButtons);" in messages
    assert "syncActionButtons(container, actionButtons);" in messages
    assert 'stepActionBtns.textContent = "";' not in messages


def test_show_less_hover_reveal_reserves_layout_space() -> None:
    css = PROJECT_ROOT.joinpath(
        "webui",
        "components",
        "messages",
        "action-buttons",
        "simple-action-buttons.css",
    ).read_text(encoding="utf-8")

    reserved = css[
        css.index(
            ".device-pointer\n  .message.message-collapsible.has-overflow.expanded\n  > .step-action-buttons\n  .show-less-btn {"
        ) :
    ]
    block = reserved[: reserved.index("}")]
    assert "display: inline-flex;" in block
    assert "opacity: 0;" in block

    hover = reserved[reserved.index(".has-overflow.expanded:hover") :]
    hover_block = hover[: hover.index("}")]
    assert "display:" not in hover_block
    assert "opacity: 1;" in hover_block


def test_sync_action_buttons_never_reinserts_mounted_buttons() -> None:
    actions = PROJECT_ROOT.joinpath(
        "webui",
        "components",
        "messages",
        "action-buttons",
        "simple-action-buttons.js",
    ).read_text(encoding="utf-8")

    assert "if (current === button && current.isConnected) return;" in actions
    assert (
        "next.forEach((button) => container.insertBefore(button, anchor || null));"
        not in actions
    )

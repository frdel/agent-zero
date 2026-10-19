from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_running_chat_bubble_morphs_and_rotates_on_a_1500ms_cycle() -> None:
    chats_list = (
        PROJECT_ROOT / "webui/components/sidebar/chats/chats-list.html"
    ).read_text(encoding="utf-8")

    assert ".chats-list-container .project-color-ball.heartbeat" in chats_list
    assert (
        "animation: chat-working-bubble 1500ms ease-in-out infinite;" in chats_list
    )
    assert "@keyframes chat-working-bubble" in chats_list
    assert "border-radius: 0;" in chats_list
    assert "transform: rotate(45deg) scale(0.9);" in chats_list
    assert "transform: rotate(405deg) scale(0.9);" in chats_list
    assert "transform: rotate(405deg) scale(1);" in chats_list


def test_chat_and_task_rows_reclaim_left_space_without_shifting_headers() -> None:
    chats_list = (
        PROJECT_ROOT / "webui/components/sidebar/chats/chats-list.html"
    ).read_text(encoding="utf-8")
    left_sidebar = (
        PROJECT_ROOT / "webui/components/sidebar/left-sidebar.html"
    ).read_text(encoding="utf-8")

    assert "margin-inline-start: calc(0px - var(--spacing-md));" not in chats_list
    assert left_sidebar.count(
        "margin-inline-start: calc(0px - var(--spacing-sm));"
    ) == 2
    assert left_sidebar.count("width: calc(100% + var(--spacing-sm));") == 2
    assert (
        "#chats-section .section-header-row,\n"
        "    #extensions-section .section-header {\n"
        "      margin-inline-start: var(--spacing-sm);"
    ) in left_sidebar
    assert "flex: 1 1 auto;" in chats_list
    assert "min-width: 0;" in chats_list
    assert "padding: var(--spacing-xs);" in chats_list


def test_only_visible_chat_actions_take_width() -> None:
    chats_list = (
        PROJECT_ROOT / "webui/components/sidebar/chats/chats-list.html"
    ).read_text(encoding="utf-8")

    assert ".device-pointer .chat-container .chat-list-action-btn" in chats_list
    assert (
        ".device-touch .chat-container:not(.chat-selected) .chat-list-action-btn"
        in chats_list
    )
    assert ".device-pointer .chat-container:hover .chat-list-action-btn" in chats_list
    assert (
        ".device-touch .chat-container.chat-selected .chat-list-action-btn"
        in chats_list
    )

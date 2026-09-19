from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_chat_rows_have_hover_scoped_overflow_actions() -> None:
    html = (
        PROJECT_ROOT / "webui/components/sidebar/chats/chat-tree.html"
    ).read_text(encoding="utf-8")

    assert html.count('aria-label="More chat actions"') == 1
    assert '<x-component path="sidebar/chats/chat-tree.html"></x-component>' in html
    assert 'class="btn-icon-action chat-list-action-btn"' in html
    assert '<x-icon name="more_vert"></x-icon>' in html
    assert html.count("$store.sidebar.rowMenuToggle(") == 1


def test_task_rows_have_overflow_actions_after_standard_buttons() -> None:
    html = (
        PROJECT_ROOT / "plugins/_scheduler/webui/sidebar/tasks-list.html"
    ).read_text(encoding="utf-8")

    delete_button = html.index('title="Delete task"')
    menu_button = html.index('aria-label="More task actions"')
    assert delete_button < menu_button
    assert "$store.sidebar.rowMenuToggle(`task:${task.id}`" in html


def test_sidebar_uses_one_fixed_row_menu_with_standard_close_behavior() -> None:
    html = (
        PROJECT_ROOT / "webui/components/sidebar/left-sidebar.html"
    ).read_text(encoding="utf-8")
    store = (
        PROJECT_ROOT / "webui/components/sidebar/sidebar-store.js"
    ).read_text(encoding="utf-8")

    assert 'class="dropdown-menu sidebar-row-actions-menu"' in html
    assert '<x-extension id="sidebar-row-actions-menu"></x-extension>' in html
    assert '@click.window="$store.sidebar.rowMenuClick(' in html
    assert '@keydown.escape.window="$store.sidebar.rowMenuClose()"' in html
    assert "Rename Chat" not in html
    assert "position: fixed;" in html
    assert "z-index: 9999;" in html
    assert "rowMenuOpenId" in store
    assert "if (this.rowMenuOpenId === id)" in store
    assert "const openUp = spaceAbove > spaceBelow;" in store
    assert "maxHeight:" in store


def test_pin_plugin_contributes_the_menu_action_and_list_ordering() -> None:
    extension = (
        PROJECT_ROOT
        / "plugins/_pin_to_top/extensions/webui/sidebar-row-actions-menu/pin-to-top.html"
    ).read_text(encoding="utf-8")
    plugin_store = (
        PROJECT_ROOT / "plugins/_pin_to_top/webui/pin-to-top-store.js"
    ).read_text(encoding="utf-8")
    sidebar_store = (
        PROJECT_ROOT / "webui/components/sidebar/sidebar-store.js"
    ).read_text(encoding="utf-8")

    assert "'Unpin from Top' : 'Pin to Top'" in extension
    assert "'keep_off' : 'push_pin'" in extension
    assert "registerRowListExtension" in plugin_store
    assert "MutationObserver" not in plugin_store
    assert "applyContexts =" not in plugin_store
    assert "applyTasks =" not in plugin_store
    assert "registerRowListExtension(kind, name, extension)" in sidebar_store
    assert "hasRowDividerBefore(kind, item, index, rows)" in sidebar_store


def test_chat_naming_plugin_contributes_rename_action_and_standard_modal() -> None:
    extension = (
        PROJECT_ROOT
        / "plugins/_chat_naming/extensions/webui/sidebar-row-actions-menu/rename.html"
    ).read_text(encoding="utf-8")
    modal = (
        PROJECT_ROOT / "plugins/_chat_naming/webui/rename.html"
    ).read_text(encoding="utf-8")
    store = (
        PROJECT_ROOT / "plugins/_chat_naming/webui/chat-naming-store.js"
    ).read_text(encoding="utf-8")

    assert "'Rename Task' : 'Rename Chat'" in extension
    assert 'data-modal-footer' in modal
    assert "chat-naming-secondary-actions" in modal
    assert "Settings" in modal
    assert "btn btn-ok" in modal
    assert "btn btn-cancel" in modal
    assert 'openModal(MODAL_PATH)' in store
    assert 'store.openConfig(' in store
    assert 'item?.project?.name' in store
    assert 'item?.agent_profile' in store
    assert 'callJsonApi(`/plugins/${PLUGIN_ID}/chat_name`' in store

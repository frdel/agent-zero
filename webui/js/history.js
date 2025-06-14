import { getContext } from "../index.js";

export async function openHistoryModal() {
    try {
        const hist = await window.sendJsonData("/history_get", { context: getContext() });
        // const data = JSON.stringify(hist.history, null, 4);
        const data = hist.history
        const size = hist.tokens
        const title = window.i18n.t('history.title', "History ~{size} tokens", { size: size });
        const description = window.i18n.t('history.description', "Conversation history visible to the LLM. History is compressed to fit into the context window over time.");
        await showEditorModal(data, "markdown", title, description);
    } catch (e) {
        window.toastFetchError(window.i18n.t('history.fetchError', "Error fetching history"), e);
        return
    }
}

export async function openCtxWindowModal() {
    try {
        const win = await window.sendJsonData("/ctx_window_get", { context: getContext() });
        const data = win.content
        const size = win.tokens
        const title = window.i18n.t('contextWindow.title', "Context window ~{size} tokens", { size: size });
        const description = window.i18n.t('contextWindow.description', "Data passed to the LLM during last interaction. Contains system message, conversation history and RAG.");
        await showEditorModal(data, "markdown", title, description);
    } catch (e) {
        window.toastFetchError(window.i18n.t('contextWindow.fetchError', "Error fetching context"), e);
        return
    }
}

async function showEditorModal(data, type = "json", title, description = "") {
    // Generate the HTML with JSON Viewer container
    const html = `<div id="json-viewer-container"></div>`;

    // Open the modal with the generated HTML
    await window.genericModalProxy.openModal(title, description, html, ["history-viewer"]);

    // Initialize the JSON Viewer after the modal is rendered
    const container = document.getElementById("json-viewer-container");
    if (container) {
        const editor = ace.edit("json-viewer-container");

        const dark = localStorage.getItem('darkMode')
        if (dark != "false") {
            editor.setTheme("ace/theme/github_dark");
        } else {
            editor.setTheme("ace/theme/tomorrow");
        }

        editor.session.setMode("ace/mode/" + type);
        editor.setValue(data);
        editor.clearSelection();
        // editor.session.$toggleFoldWidget(5, {})
    }
}

window.openHistoryModal = openHistoryModal;
window.openCtxWindowModal = openCtxWindowModal;

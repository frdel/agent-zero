// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../../resource.mjs";
import * as AssistantsAPI from "./assistants.mjs";
import * as ChatAPI from "./chat/chat.mjs";
import * as ThreadsAPI from "./threads/threads.mjs";
import * as VectorStoresAPI from "./vector-stores/vector-stores.mjs";
export class Beta extends APIResource {
    constructor() {
        super(...arguments);
        this.vectorStores = new VectorStoresAPI.VectorStores(this._client);
        this.chat = new ChatAPI.Chat(this._client);
        this.assistants = new AssistantsAPI.Assistants(this._client);
        this.threads = new ThreadsAPI.Threads(this._client);
    }
}
(function (Beta) {
    Beta.VectorStores = VectorStoresAPI.VectorStores;
    Beta.VectorStoresPage = VectorStoresAPI.VectorStoresPage;
    Beta.Chat = ChatAPI.Chat;
    Beta.Assistants = AssistantsAPI.Assistants;
    Beta.AssistantsPage = AssistantsAPI.AssistantsPage;
    Beta.Threads = ThreadsAPI.Threads;
})(Beta || (Beta = {}));
//# sourceMappingURL=beta.mjs.map
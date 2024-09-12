// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../resource.mjs";
export class Moderations extends APIResource {
    /**
     * Classifies if text is potentially harmful.
     */
    create(body, options) {
        return this._client.post('/moderations', { body, ...options });
    }
}
(function (Moderations) {
})(Moderations || (Moderations = {}));
//# sourceMappingURL=moderations.mjs.map
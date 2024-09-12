"use strict";
// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
Object.defineProperty(exports, "__esModule", { value: true });
exports.Moderations = void 0;
const resource_1 = require("../resource.js");
class Moderations extends resource_1.APIResource {
    /**
     * Classifies if text is potentially harmful.
     */
    create(body, options) {
        return this._client.post('/moderations', { body, ...options });
    }
}
exports.Moderations = Moderations;
(function (Moderations) {
})(Moderations = exports.Moderations || (exports.Moderations = {}));
//# sourceMappingURL=moderations.js.map
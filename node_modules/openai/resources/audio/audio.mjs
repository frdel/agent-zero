// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../../resource.mjs";
import * as SpeechAPI from "./speech.mjs";
import * as TranscriptionsAPI from "./transcriptions.mjs";
import * as TranslationsAPI from "./translations.mjs";
export class Audio extends APIResource {
    constructor() {
        super(...arguments);
        this.transcriptions = new TranscriptionsAPI.Transcriptions(this._client);
        this.translations = new TranslationsAPI.Translations(this._client);
        this.speech = new SpeechAPI.Speech(this._client);
    }
}
(function (Audio) {
    Audio.Transcriptions = TranscriptionsAPI.Transcriptions;
    Audio.Translations = TranslationsAPI.Translations;
    Audio.Speech = SpeechAPI.Speech;
})(Audio || (Audio = {}));
//# sourceMappingURL=audio.mjs.map
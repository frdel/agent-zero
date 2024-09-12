import { APIResource } from "../../resource.js";
import * as AudioAPI from "./audio.js";
import * as SpeechAPI from "./speech.js";
import * as TranscriptionsAPI from "./transcriptions.js";
import * as TranslationsAPI from "./translations.js";
export declare class Audio extends APIResource {
    transcriptions: TranscriptionsAPI.Transcriptions;
    translations: TranslationsAPI.Translations;
    speech: SpeechAPI.Speech;
}
export type AudioModel = 'whisper-1';
export declare namespace Audio {
    export import AudioModel = AudioAPI.AudioModel;
    export import Transcriptions = TranscriptionsAPI.Transcriptions;
    export import Transcription = TranscriptionsAPI.Transcription;
    export import TranscriptionCreateParams = TranscriptionsAPI.TranscriptionCreateParams;
    export import Translations = TranslationsAPI.Translations;
    export import Translation = TranslationsAPI.Translation;
    export import TranslationCreateParams = TranslationsAPI.TranslationCreateParams;
    export import Speech = SpeechAPI.Speech;
    export import SpeechModel = SpeechAPI.SpeechModel;
    export import SpeechCreateParams = SpeechAPI.SpeechCreateParams;
}
//# sourceMappingURL=audio.d.ts.map
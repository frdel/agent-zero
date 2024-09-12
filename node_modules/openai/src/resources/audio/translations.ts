// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../resource';
import * as Core from '../../core';
import * as TranslationsAPI from './translations';
import * as AudioAPI from './audio';

export class Translations extends APIResource {
  /**
   * Translates audio into English.
   */
  create(body: TranslationCreateParams, options?: Core.RequestOptions): Core.APIPromise<Translation> {
    return this._client.post('/audio/translations', Core.multipartFormRequestOptions({ body, ...options }));
  }
}

export interface Translation {
  text: string;
}

export interface TranslationCreateParams {
  /**
   * The audio file object (not file name) translate, in one of these formats: flac,
   * mp3, mp4, mpeg, mpga, m4a, ogg, wav, or webm.
   */
  file: Core.Uploadable;

  /**
   * ID of the model to use. Only `whisper-1` (which is powered by our open source
   * Whisper V2 model) is currently available.
   */
  model: (string & {}) | AudioAPI.AudioModel;

  /**
   * An optional text to guide the model's style or continue a previous audio
   * segment. The
   * [prompt](https://platform.openai.com/docs/guides/speech-to-text/prompting)
   * should be in English.
   */
  prompt?: string;

  /**
   * The format of the transcript output, in one of these options: `json`, `text`,
   * `srt`, `verbose_json`, or `vtt`.
   */
  response_format?: string;

  /**
   * The sampling temperature, between 0 and 1. Higher values like 0.8 will make the
   * output more random, while lower values like 0.2 will make it more focused and
   * deterministic. If set to 0, the model will use
   * [log probability](https://en.wikipedia.org/wiki/Log_probability) to
   * automatically increase the temperature until certain thresholds are hit.
   */
  temperature?: number;
}

export namespace Translations {
  export import Translation = TranslationsAPI.Translation;
  export import TranslationCreateParams = TranslationsAPI.TranslationCreateParams;
}

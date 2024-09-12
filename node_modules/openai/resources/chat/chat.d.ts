import { APIResource } from "../../resource.js";
import * as ChatAPI from "./chat.js";
import * as CompletionsAPI from "./completions.js";
export declare class Chat extends APIResource {
    completions: CompletionsAPI.Completions;
}
export type ChatModel = 'gpt-4o' | 'gpt-4o-2024-05-13' | 'gpt-4o-2024-08-06' | 'gpt-4o-mini' | 'gpt-4o-mini-2024-07-18' | 'gpt-4-turbo' | 'gpt-4-turbo-2024-04-09' | 'gpt-4-0125-preview' | 'gpt-4-turbo-preview' | 'gpt-4-1106-preview' | 'gpt-4-vision-preview' | 'gpt-4' | 'gpt-4-0314' | 'gpt-4-0613' | 'gpt-4-32k' | 'gpt-4-32k-0314' | 'gpt-4-32k-0613' | 'gpt-3.5-turbo' | 'gpt-3.5-turbo-16k' | 'gpt-3.5-turbo-0301' | 'gpt-3.5-turbo-0613' | 'gpt-3.5-turbo-1106' | 'gpt-3.5-turbo-0125' | 'gpt-3.5-turbo-16k-0613';
export declare namespace Chat {
    export import ChatModel = ChatAPI.ChatModel;
    export import Completions = CompletionsAPI.Completions;
    export import ChatCompletion = CompletionsAPI.ChatCompletion;
    export import ChatCompletionAssistantMessageParam = CompletionsAPI.ChatCompletionAssistantMessageParam;
    export import ChatCompletionChunk = CompletionsAPI.ChatCompletionChunk;
    export import ChatCompletionContentPart = CompletionsAPI.ChatCompletionContentPart;
    export import ChatCompletionContentPartImage = CompletionsAPI.ChatCompletionContentPartImage;
    export import ChatCompletionContentPartRefusal = CompletionsAPI.ChatCompletionContentPartRefusal;
    export import ChatCompletionContentPartText = CompletionsAPI.ChatCompletionContentPartText;
    export import ChatCompletionFunctionCallOption = CompletionsAPI.ChatCompletionFunctionCallOption;
    export import ChatCompletionFunctionMessageParam = CompletionsAPI.ChatCompletionFunctionMessageParam;
    export import ChatCompletionMessage = CompletionsAPI.ChatCompletionMessage;
    export import ChatCompletionMessageParam = CompletionsAPI.ChatCompletionMessageParam;
    export import ChatCompletionMessageToolCall = CompletionsAPI.ChatCompletionMessageToolCall;
    export import ChatCompletionNamedToolChoice = CompletionsAPI.ChatCompletionNamedToolChoice;
    export import ChatCompletionRole = CompletionsAPI.ChatCompletionRole;
    export import ChatCompletionStreamOptions = CompletionsAPI.ChatCompletionStreamOptions;
    export import ChatCompletionSystemMessageParam = CompletionsAPI.ChatCompletionSystemMessageParam;
    export import ChatCompletionTokenLogprob = CompletionsAPI.ChatCompletionTokenLogprob;
    export import ChatCompletionTool = CompletionsAPI.ChatCompletionTool;
    export import ChatCompletionToolChoiceOption = CompletionsAPI.ChatCompletionToolChoiceOption;
    export import ChatCompletionToolMessageParam = CompletionsAPI.ChatCompletionToolMessageParam;
    export import ChatCompletionUserMessageParam = CompletionsAPI.ChatCompletionUserMessageParam;
    /**
     * @deprecated ChatCompletionMessageParam should be used instead
     */
    export import CreateChatCompletionRequestMessage = CompletionsAPI.CreateChatCompletionRequestMessage;
    export import ChatCompletionCreateParams = CompletionsAPI.ChatCompletionCreateParams;
    export import CompletionCreateParams = CompletionsAPI.CompletionCreateParams;
    export import ChatCompletionCreateParamsNonStreaming = CompletionsAPI.ChatCompletionCreateParamsNonStreaming;
    export import CompletionCreateParamsNonStreaming = CompletionsAPI.CompletionCreateParamsNonStreaming;
    export import ChatCompletionCreateParamsStreaming = CompletionsAPI.ChatCompletionCreateParamsStreaming;
    export import CompletionCreateParamsStreaming = CompletionsAPI.CompletionCreateParamsStreaming;
}
//# sourceMappingURL=chat.d.ts.map
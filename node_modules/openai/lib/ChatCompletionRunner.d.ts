import { type ChatCompletionMessageParam, type ChatCompletionCreateParamsNonStreaming } from 'openai/resources/chat/completions';
import { type RunnableFunctions, type BaseFunctionsArgs, RunnableTools } from "./RunnableFunction.js";
import { AbstractChatCompletionRunner, AbstractChatCompletionRunnerEvents, RunnerOptions } from "./AbstractChatCompletionRunner.js";
import OpenAI from 'openai/index';
import { AutoParseableTool } from 'openai/lib/parser';
export interface ChatCompletionRunnerEvents extends AbstractChatCompletionRunnerEvents {
    content: (content: string) => void;
}
export type ChatCompletionFunctionRunnerParams<FunctionsArgs extends BaseFunctionsArgs> = Omit<ChatCompletionCreateParamsNonStreaming, 'functions'> & {
    functions: RunnableFunctions<FunctionsArgs>;
};
export type ChatCompletionToolRunnerParams<FunctionsArgs extends BaseFunctionsArgs> = Omit<ChatCompletionCreateParamsNonStreaming, 'tools'> & {
    tools: RunnableTools<FunctionsArgs> | AutoParseableTool<any, true>[];
};
export declare class ChatCompletionRunner<ParsedT = null> extends AbstractChatCompletionRunner<ChatCompletionRunnerEvents, ParsedT> {
    /** @deprecated - please use `runTools` instead. */
    static runFunctions(client: OpenAI, params: ChatCompletionFunctionRunnerParams<any[]>, options?: RunnerOptions): ChatCompletionRunner<null>;
    static runTools<ParsedT>(client: OpenAI, params: ChatCompletionToolRunnerParams<any[]>, options?: RunnerOptions): ChatCompletionRunner<ParsedT>;
    _addMessage(this: ChatCompletionRunner<ParsedT>, message: ChatCompletionMessageParam, emit?: boolean): void;
}
//# sourceMappingURL=ChatCompletionRunner.d.ts.map
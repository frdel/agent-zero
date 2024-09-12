// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../../../../resource.mjs";
import { isRequestOptions } from "../../../../core.mjs";
import * as StepsAPI from "./steps.mjs";
import { CursorPage } from "../../../../pagination.mjs";
export class Steps extends APIResource {
    retrieve(threadId, runId, stepId, query = {}, options) {
        if (isRequestOptions(query)) {
            return this.retrieve(threadId, runId, stepId, {}, query);
        }
        return this._client.get(`/threads/${threadId}/runs/${runId}/steps/${stepId}`, {
            query,
            ...options,
            headers: { 'OpenAI-Beta': 'assistants=v2', ...options?.headers },
        });
    }
    list(threadId, runId, query = {}, options) {
        if (isRequestOptions(query)) {
            return this.list(threadId, runId, {}, query);
        }
        return this._client.getAPIList(`/threads/${threadId}/runs/${runId}/steps`, RunStepsPage, {
            query,
            ...options,
            headers: { 'OpenAI-Beta': 'assistants=v2', ...options?.headers },
        });
    }
}
export class RunStepsPage extends CursorPage {
}
(function (Steps) {
    Steps.RunStepsPage = StepsAPI.RunStepsPage;
})(Steps || (Steps = {}));
//# sourceMappingURL=steps.mjs.map
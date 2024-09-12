// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../../../resource.mjs";
import { isRequestOptions } from "../../../core.mjs";
import * as CheckpointsAPI from "./checkpoints.mjs";
import { CursorPage } from "../../../pagination.mjs";
export class Checkpoints extends APIResource {
    list(fineTuningJobId, query = {}, options) {
        if (isRequestOptions(query)) {
            return this.list(fineTuningJobId, {}, query);
        }
        return this._client.getAPIList(`/fine_tuning/jobs/${fineTuningJobId}/checkpoints`, FineTuningJobCheckpointsPage, { query, ...options });
    }
}
export class FineTuningJobCheckpointsPage extends CursorPage {
}
(function (Checkpoints) {
    Checkpoints.FineTuningJobCheckpointsPage = CheckpointsAPI.FineTuningJobCheckpointsPage;
})(Checkpoints || (Checkpoints = {}));
//# sourceMappingURL=checkpoints.mjs.map
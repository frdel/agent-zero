// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
import { APIResource } from "../../resource.mjs";
import * as JobsAPI from "./jobs/jobs.mjs";
export class FineTuning extends APIResource {
    constructor() {
        super(...arguments);
        this.jobs = new JobsAPI.Jobs(this._client);
    }
}
(function (FineTuning) {
    FineTuning.Jobs = JobsAPI.Jobs;
    FineTuning.FineTuningJobsPage = JobsAPI.FineTuningJobsPage;
    FineTuning.FineTuningJobEventsPage = JobsAPI.FineTuningJobEventsPage;
})(FineTuning || (FineTuning = {}));
//# sourceMappingURL=fine-tuning.mjs.map
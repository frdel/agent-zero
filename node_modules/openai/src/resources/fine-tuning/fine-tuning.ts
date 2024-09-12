// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import { APIResource } from '../../resource';
import * as JobsAPI from './jobs/jobs';

export class FineTuning extends APIResource {
  jobs: JobsAPI.Jobs = new JobsAPI.Jobs(this._client);
}

export namespace FineTuning {
  export import Jobs = JobsAPI.Jobs;
  export import FineTuningJob = JobsAPI.FineTuningJob;
  export import FineTuningJobEvent = JobsAPI.FineTuningJobEvent;
  export import FineTuningJobIntegration = JobsAPI.FineTuningJobIntegration;
  export import FineTuningJobWandbIntegration = JobsAPI.FineTuningJobWandbIntegration;
  export import FineTuningJobWandbIntegrationObject = JobsAPI.FineTuningJobWandbIntegrationObject;
  export import FineTuningJobsPage = JobsAPI.FineTuningJobsPage;
  export import FineTuningJobEventsPage = JobsAPI.FineTuningJobEventsPage;
  export import JobCreateParams = JobsAPI.JobCreateParams;
  export import JobListParams = JobsAPI.JobListParams;
  export import JobListEventsParams = JobsAPI.JobListEventsParams;
}

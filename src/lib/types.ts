export interface Workflow {
  description: string;
  steps: Array<{
    observation: string;
    reasoning: string;
    action: string;
  }>;
}
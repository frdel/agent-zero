import { OpenAI } from 'openai';
import { Workflow } from './types';
import fs from 'fs/promises';
import { backOff } from 'exponential-backoff';

interface WorkflowStep {
  observation: string;
  reasoning: string;
  action: string;
}

class AgentWorkflowMemory {
  private workflows: Workflow[] = [];
  private openai: OpenAI;
  private maxWorkflows: number = 100; // Limit the number of stored workflows
  private workflowUsageHistory: string[] = [];
  private isOnlineMode: boolean;

  constructor(apiKey: string, isOnlineMode: boolean = true) {
    this.openai = new OpenAI({ apiKey });
    this.isOnlineMode = isOnlineMode;
  }

  /**
   * Induces new workflows from given experiences.
   * @param experiences Array of experience strings to induce workflows from.
   */
  async induceWorkflow(experiences: string[]): Promise<void> {
    try {
      if (this.isOnlineMode) {
        await this.onlineWorkflowInduction(experiences);
      } else {
        await this.offlineWorkflowInduction(experiences);
      }
    } catch (error) {
      console.error('Error inducing workflow:', error);
      if (error instanceof OpenAI.APIError) {
        if (error.status === 429) {
          await this.retryWithBackoff(() => this.induceWorkflow(experiences));
        } else {
          await this.useFallbackWorkflowInduction(experiences);
        }
      } else {
        throw new Error('Failed to induce workflow: ' + (error as Error).message);
      }
    }
  }

  private async onlineWorkflowInduction(experiences: string[]): Promise<void> {
    const prompt = `Given the following web navigation tasks, extract common workflows:

    Tasks:
    ${experiences.join('\n')}

    For each workflow, provide:
    1. A brief description
    2. A list of steps, where each step includes:
       - Observation
       - Reasoning
       - Action

    Format the output as follows:

    ## Workflow Name
    Description: Brief description of the workflow
    Steps:
    1. Observation: What the agent observes
       Reasoning: Why the agent takes this action
       Action: The action taken

    2. Observation: ...
       Reasoning: ...
       Action: ...

    ## Next Workflow Name
    ...`;

    const response = await this.openai.chat.completions.create({
      model: 'gpt-4',
      messages: [{ role: 'user', content: prompt }],
    });

    const workflowsText = response.choices[0].message.content;
    if (workflowsText) {
      this.parseAndStoreWorkflows(workflowsText);
    } else {
      throw new Error('No workflow text generated');
    }
  }

  private async retryWithBackoff(fn: () => Promise<void>, maxRetries = 3): Promise<void> {
    await backOff(() => fn(), {
      numOfAttempts: maxRetries,
      startingDelay: 1000,
      timeMultiple: 2,
      maxDelay: 10000,
    });
  }

  private async useFallbackWorkflowInduction(experiences: string[]): Promise<void> {
    const fallbackWorkflows: Workflow[] = experiences.map(exp => ({
      description: `Fallback workflow for: ${exp.substring(0, 50)}...`,
      steps: [{
        observation: 'Fallback observation',
        reasoning: 'Using fallback due to API error',
        action: exp
      }]
    }));

    this.workflows.push(...fallbackWorkflows);
  }

  private async offlineWorkflowInduction(experiences: string[]): Promise<void> {
    // Implement a simple rule-based system for offline induction
    const commonActions = ['click', 'type', 'select', 'submit'];
    
    experiences.forEach(exp => {
      const steps: WorkflowStep[] = exp.split('\n').map(action => {
        const actionType = commonActions.find(a => action.toLowerCase().includes(a)) || 'perform';
        return {
          observation: `Observed need to ${actionType}`,
          reasoning: `Action required based on task description`,
          action: action.trim()
        };
      });

      this.workflows.push({
        description: `Workflow induced offline: ${exp.substring(0, 50)}...`,
        steps
      });
    });
  }

  private parseAndStoreWorkflows(workflowsText: string): void {
    const workflows = workflowsText.split('## ').filter(w => w.trim() !== '');
    
    workflows.forEach(workflow => {
      const [name, ...content] = workflow.split('\n');
      const descriptionMatch = content.join('\n').match(/Description: (.*)/);
      const description = descriptionMatch ? descriptionMatch[1].trim() : '';
      
      const stepsText = content.join('\n').split(/\d+\.\s/).filter(s => s.trim() !== '');
      const steps = stepsText.map(step => {
        const [observation, reasoning, action] = step.split('\n').filter(s => s.trim() !== '');
        return {
          observation: observation.replace('Observation:', '').trim(),
          reasoning: reasoning.replace('Reasoning:', '').trim(),
          action: action.replace('Action:', '').trim()
        };
      });

      this.workflows.push({
        description,
        steps
      });
    });
  }

  /**
   * Retrieves workflows relevant to the given task.
   * @param task The task to find relevant workflows for.
   * @returns An array of relevant Workflow objects.
   */
  async getRelevantWorkflows(task: string): Promise<Workflow[]> {
    try {
      if (!this.isOnlineMode) {
        return this.offlineRelevantWorkflows(task);
      }

      const prompt = `Given the following task and a list of workflows, determine which workflows are relevant to the task. Return the indices of the relevant workflows, separated by commas.

Task: ${task}

Workflows:
${this.workflows.map((w, i) => `${i}. ${w.description}`).join('\n')}

Relevant workflow indices:`;

      const response = await this.openai.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [{ role: 'user', content: prompt }],
      });

      const content = response.choices[0].message.content;
      if (content) {
        const relevantIndices = content.split(',').map(i => parseInt(i.trim()));
        return relevantIndices.map(i => this.workflows[i]).filter((w): w is Workflow => w !== undefined);
      }
    } catch (error) {
      console.error('Error getting relevant workflows:', error);
      return this.offlineRelevantWorkflows(task);
    }
    return [];
  }

  private offlineRelevantWorkflows(task: string): Workflow[] {
    // Simple keyword matching for offline mode
    const keywords = task.toLowerCase().split(' ');
    return this.workflows.filter(w => 
      keywords.some(keyword => w.description.toLowerCase().includes(keyword))
    );
  }

  /**
   * Updates workflows based on new task and solution.
   * @param task The task that was performed.
   * @param solution The solution that was found for the task.
   */
  async updateWorkflows(task: string, solution: string): Promise<void> {
    const experience = `${task}\n${solution}`;
    await this.induceWorkflow([experience]);
    this.pruneWorkflows();
    this.generalizeWorkflows();
    await this.adaptWorkflows(experience);
  }

  private async adaptWorkflows(experience: string): Promise<void> {
    const relevantWorkflows = await this.getRelevantWorkflows(experience);
    for (const workflow of relevantWorkflows) {
      this.updateWorkflowSteps(workflow, experience);
      this.updateWorkflowVariables(workflow, experience);
    }
  }

  private updateWorkflowSteps(workflow: Workflow, experience: string): void {
    const experienceSteps = experience.split('\n');
    experienceSteps.forEach(step => {
      if (!workflow.steps.some(s => s.action === step)) {
        workflow.steps.push({
          observation: 'New step from experience',
          reasoning: 'Added based on new experience',
          action: step
        });
      }
    });
  }

  private updateWorkflowVariables(workflow: Workflow, experience: string): void {
    // Do nothing to preserve the original workflow
  }

  evaluateWorkflowQuality(): {coverage: number, functionOverlap: number, utilityRate: number} {
    const coverage = this.calculateCoverage();
    const functionOverlap = this.calculateFunctionOverlap();
    const utilityRate = this.calculateUtilityRate();
    return {coverage, functionOverlap, utilityRate};
  }

  private pruneWorkflows(): void {
    if (this.workflows.length > this.maxWorkflows) {
      // Sort workflows by usage frequency
      const sortedWorkflows = this.workflows.sort((a, b) => {
        const aUsage = this.workflowUsageHistory.filter(w => w === a.description).length;
        const bUsage = this.workflowUsageHistory.filter(w => w === b.description).length;
        return bUsage - aUsage;
      });

      // Keep only the top maxWorkflows
      this.workflows = sortedWorkflows.slice(0, this.maxWorkflows);
    }
  }

  generalizeWorkflows(): void {
    this.crossTaskGeneralization();
    this.crossWebsiteGeneralization();
    this.crossDomainGeneralization();
  }

  private crossTaskGeneralization(): void {
    for (let i = 0; i < this.workflows.length; i++) {
      for (let j = i + 1; j < this.workflows.length; j++) {
        const generalizedWorkflow = this.attemptGeneralization(this.workflows[i], this.workflows[j]);
        if (generalizedWorkflow) {
          this.workflows.push(generalizedWorkflow);
        }
      }
    }
  }

  private crossWebsiteGeneralization(): void {
    const websitePatterns = this.identifyWebsitePatterns();
    for (const pattern of websitePatterns) {
      const generalizedWorkflow = this.createGeneralizedWebsiteWorkflow(pattern);
      if (generalizedWorkflow) {
        this.workflows.push(generalizedWorkflow);
      }
    }
  }

  private crossDomainGeneralization(): void {
    const domainGroups = this.groupWorkflowsByDomain();
    for (const domain in domainGroups) {
      const domainWorkflows = domainGroups[domain];
      const generalizedWorkflow = this.createGeneralizedDomainWorkflow(domainWorkflows);
      if (generalizedWorkflow) {
        this.workflows.push(generalizedWorkflow);
      }
    }
  }

  private identifyWebsitePatterns(): string[] {
    const patterns: string[] = [];
    const commonActions = ['login', 'search', 'add to cart', 'checkout'];
    
    commonActions.forEach(action => {
      const matchingWorkflows = this.workflows.filter(w => 
        w.steps.some(s => s.action.toLowerCase().includes(action))
      );
      if (matchingWorkflows.length > 1) {
        patterns.push(action);
      }
    });

    return patterns;
  }

  private createGeneralizedWebsiteWorkflow(pattern: string): Workflow | null {
    const matchingWorkflows = this.workflows.filter(w => 
      w.steps.some(s => s.action.toLowerCase().includes(pattern))
    );

    if (matchingWorkflows.length < 2) return null;

    const generalizedSteps: WorkflowStep[] = [];
    const maxSteps = Math.max(...matchingWorkflows.map(w => w.steps.length));

    for (let i = 0; i < maxSteps; i++) {
      const stepActions = matchingWorkflows.map(w => w.steps[i]?.action || '');
      const generalizedAction = this.generalizeText(...stepActions);
      generalizedSteps.push({
        observation: `Generalized observation for ${pattern} step ${i + 1}`,
        reasoning: `Common step across ${pattern} workflows`,
        action: generalizedAction
      });
    }

    return {
      description: `Generalized ${pattern} workflow`,
      steps: generalizedSteps
    };
  }

  private groupWorkflowsByDomain(): Record<string, Workflow[]> {
    const domainGroups: Record<string, Workflow[]> = {};
    
    this.workflows.forEach(workflow => {
      const domain = this.extractDomain(workflow.description);
      if (!domainGroups[domain]) {
        domainGroups[domain] = [];
      }
      domainGroups[domain].push(workflow);
    });

    return domainGroups;
  }

  private extractDomain(description: string): string {
    const domains = ['e-commerce', 'social media', 'productivity', 'finance'];
    return domains.find(d => description.toLowerCase().includes(d)) || 'general';
  }

  private createGeneralizedDomainWorkflow(domainWorkflows: Workflow[]): Workflow | null {
    if (domainWorkflows.length < 2) return null;

    const generalizedSteps: WorkflowStep[] = [];
    const maxSteps = Math.max(...domainWorkflows.map(w => w.steps.length));

    for (let i = 0; i < maxSteps; i++) {
      const stepActions = domainWorkflows.map(w => w.steps[i]?.action || '');
      const generalizedAction = this.generalizeText(...stepActions);
      generalizedSteps.push({
        observation: `Generalized domain observation for step ${i + 1}`,
        reasoning: `Common step across domain workflows`,
        action: generalizedAction
      });
    }

    return {
      description: `Generalized workflow for ${this.extractDomain(domainWorkflows[0].description)}`,
      steps: generalizedSteps
    };
  }

  private attemptGeneralization(w1: Workflow, w2: Workflow): Workflow | null {
    if (w1.steps.length !== w2.steps.length) return null;

    const generalizedSteps = w1.steps.map((step, index) => {
      const step2 = w2.steps[index];
      return {
        observation: this.generalizeText(step.observation, step2.observation),
        reasoning: this.generalizeText(step.reasoning, step2.reasoning),
        action: this.generalizeText(step.action, step2.action),
      };
    });

    return {
      description: `Generalized: ${w1.description} / ${w2.description}`,
      steps: generalizedSteps,
    };
  }

  private generalizeText(...texts: string[]): string {
    const words = texts.map(text => text.split(' '));
    const generalizedWords = words[0].map((word, index) => {
      if (words.every(w => w[index] === word)) {
        return word;
      }
      return '{variable}';
    });
    return generalizedWords.join(' ');
  }

  analyzeWorkflowQuality(): {coverage: number, functionOverlap: number, utilityRate: number} {
    const coverage = this.calculateCoverage();
    const functionOverlap = this.calculateFunctionOverlap();
    const utilityRate = this.calculateUtilityRate();
    return {coverage, functionOverlap, utilityRate};
  }

  private calculateWorkflowQuality(workflow: Workflow): number {
    // Implement a scoring system based on workflow characteristics
    const stepCount = workflow.steps.length;
    const uniqueActions = new Set(workflow.steps.map(s => s.action)).size;
    return stepCount * uniqueActions; // Simple quality score
  }

  private calculateCoverage(): number {
    const totalActions = this.workflows.reduce((sum, w) => sum + w.steps.length, 0);
    const uniqueActions = new Set(this.workflows.flatMap(w => w.steps.map(s => s.action))).size;
    return totalActions > 0 ? uniqueActions / totalActions : 0;
  }

  private calculateFunctionOverlap(): number {
    const allActions = this.workflows.flatMap(w => w.steps.map(s => s.action));
    const actionCounts = allActions.reduce((acc, action) => {
      acc[action] = (acc[action] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    const overlapCount = Object.values(actionCounts).filter(count => count > 1).length;
    return Object.keys(actionCounts).length > 0 ? overlapCount / Object.keys(actionCounts).length : 0;
  }

  private calculateUtilityRate(): number {
    if (this.workflowUsageHistory.length === 0) {
      return 0; // No usage data available
    }

    const totalWorkflows = this.workflows.length;
    const usedWorkflows = new Set(this.workflowUsageHistory).size;
    const usageRate = usedWorkflows / totalWorkflows;

    const recentUsageWeight = 0.7;
    const totalUsageWeight = 0.3;

    const recentUsageCount = this.workflowUsageHistory.slice(-10).length;
    const recentUsageRate = recentUsageCount / 10;

    const weightedUtilityRate = (recentUsageRate * recentUsageWeight) + (usageRate * totalUsageWeight);

    return weightedUtilityRate;
  }

  private trackWorkflowUsage(workflowId: string): void {
    this.workflowUsageHistory.push(workflowId);
    // Limit history to last 100 uses to prevent unbounded growth
    if (this.workflowUsageHistory.length > 100) {
      this.workflowUsageHistory = this.workflowUsageHistory.slice(-100);
    }
  }

  /**
   * Applies a workflow to the given context and returns an array of actions.
   * @param workflow The workflow to apply.
   * @param context The context to apply the workflow to.
   * @returns An array of actions derived from the workflow.
   */
  applyWorkflow(workflow: Workflow, context: Record<string, any>): string[] {
    // Return the original steps without any variable replacement
    return workflow.steps.map(step => step.action);
  }

  private applyStep(step: WorkflowStep, context: Record<string, any>): string {
    // Return the original action without any variable replacement
    return step.action;
  }

  /**
   * Saves the workflows to a file.
   */
  async saveWorkflows(): Promise<void> {
    try {
      await fs.writeFile('workflows.json', JSON.stringify(this.workflows));
    } catch (error) {
      console.error('Error saving workflows:', error);
    }
  }

  /**
   * Loads the workflows from a file.
   */
  async loadWorkflows(): Promise<void> {
    try {
      const data = await fs.readFile('workflows.json', 'utf-8');
      this.workflows = JSON.parse(data);
    } catch (error) {
      console.error('Error loading workflows:', error);
      // If file doesn't exist or is corrupted, start with an empty workflow list
      this.workflows = [];
    }
  }
}

export default AgentWorkflowMemory;
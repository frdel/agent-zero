import AgentWorkflowMemory from './awm';
import { OpenAI } from 'openai';
import { describe, test, expect, jest, beforeEach } from '@jest/globals';

jest.mock('openai');

describe('AgentWorkflowMemory', () => {
  let awm: AgentWorkflowMemory;

  beforeEach(() => {
    awm = new AgentWorkflowMemory('fake-api-key');
  });

  test('induceWorkflow should parse and store workflows', async () => {
    const mockResponse = {
      choices: [
        {
          message: {
            content: `## Login Workflow
            Description: Workflow for logging into a website
            Steps:
            1. Observe login form
            Enter username and password
            Click login button`
          }
        }
      ]
    };

    (OpenAI.prototype.chat.completions.create as jest.Mock).mockResolvedValue(mockResponse);

    await awm.induceWorkflow(['Login to website']);

    expect(awm['workflows']).toHaveLength(1);
    expect(awm['workflows'][0].description).toBe('Workflow for logging into a website');
    expect(awm['workflows'][0].steps).toHaveLength(1);
  });

  test('getRelevantWorkflows should return relevant workflows', async () => {
    // Setup mock workflows
    awm['workflows'] = [
      { description: 'Login workflow', steps: [] },
      { description: 'Search workflow', steps: [] },
    ];

    const mockResponse = {
      choices: [{ message: { content: '0,1' } }]
    };

    (OpenAI.prototype.chat.completions.create as jest.Mock).mockResolvedValue(mockResponse);

    const relevantWorkflows = await awm.getRelevantWorkflows('Login and search');

    expect(relevantWorkflows).toHaveLength(2);
    expect(relevantWorkflows[0].description).toBe('Login workflow');
    expect(relevantWorkflows[1].description).toBe('Search workflow');
  });

  test('updateWorkflows should add new workflows and generalize', async () => {
    const initialWorkflowCount = awm['workflows'].length;
    const initialWorkflow = {
      description: 'Initial workflow',
      steps: [{ observation: '', reasoning: '', action: 'Click login button' }]
    };
    awm['workflows'].push(initialWorkflow);

    await awm.updateWorkflows('Login to website', 'Entered username "john" and password "pass123", clicked login button');

    expect(awm['workflows'].length).toBeGreaterThan(initialWorkflowCount);
    
    // Check if a new workflow was added or existing one was updated
    const updatedWorkflow = awm['workflows'].find(w => w.description.includes('Login to website'));
    expect(updatedWorkflow).toBeDefined();
    
    // Check if steps were updated
    expect(updatedWorkflow?.steps.some(s => s.action.includes('{variable}'))).toBeTruthy();
    
    // Check if generalization occurred
    expect(updatedWorkflow?.steps.some(s => s.action.includes('Entered username {variable}'))).toBeTruthy();
  });

  test('induceWorkflow should handle API errors', async () => {
    (OpenAI.prototype.chat.completions.create as jest.Mock).mockRejectedValue(new Error('API Error'));

    await expect(awm.induceWorkflow(['Login to website'])).rejects.toThrow('Failed to induce workflow');
  });

  test('induceWorkflow should work in offline mode', async () => {
    const offlineAWM = new AgentWorkflowMemory('fake-api-key', false);
    await offlineAWM.induceWorkflow(['Login to website']);

    expect(offlineAWM['workflows'].length).toBeGreaterThan(0);
    // Add more specific assertions based on your offline induction logic
  });

  // Add more tests for other methods...
});
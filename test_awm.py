import asyncio
from src.lib.awm import AgentWorkflowMemory
from src.lib.embedding_memory import EmbeddingMemory
import models
import os
from dotenv import load_dotenv

async def main():
    load_dotenv()  # Load environment variables

    # Initialize the embedding model
    embedding_llm = models.get_openai_embedding(model_name="text-embedding-3-small")

    # Initialize EmbeddingMemory
    embedding_memory = EmbeddingMemory(embedding_llm)

    # Initialize AgentWorkflowMemory
    openai_api_key = os.getenv("OPENAI_API_KEY")
    awm = AgentWorkflowMemory(api_key=openai_api_key, is_online_mode=True, embedding_memory=embedding_memory)

    # Test workflow induction
    await test_workflow_induction(awm)

    # Test embedding memory integration
    await test_embedding_memory_integration(awm)

    # Test workflow retrieval
    await test_workflow_retrieval(awm)

    # Test workflow application
    await test_workflow_application(awm)

    # Test workflow generalization
    await test_workflow_generalization(awm)

    # Test workflow adaptation
    await test_workflow_adaptation(awm)

    # Test workflow pruning
    await test_workflow_pruning(awm)

    # Test workflow evaluation
    await test_workflow_evaluation(awm)

if __name__ == "__main__":
    asyncio.run(main())

async def test_workflow_induction(awm):
    print("Testing workflow induction...")
    experiences = [
        "Navigate to example.com",
        "Click on the login button",
        "Enter username 'testuser'",
        "Enter password 'testpass'",
        "Click submit"
    ]
    await awm.induce_workflow(experiences)
    print(f"Induced workflows: {len(awm.workflows)}")
    for workflow in awm.workflows:
        print(f"- {workflow.description}")

async def test_workflow_retrieval(awm):
    print("\nTesting workflow retrieval...")
    task = "Login to a website"
    relevant_workflows = await awm.get_relevant_workflows(task)
    print(f"Retrieved workflows for '{task}': {len(relevant_workflows)}")
    for workflow in relevant_workflows:
        print(f"- {workflow.description}")

async def test_workflow_application(awm):
    print("\nTesting workflow application...")
    if awm.workflows:
        workflow = awm.workflows[0]
        context = {"username": "testuser", "password": "testpass"}
        actions = awm.apply_workflow(workflow, context)
        print(f"Applied workflow: {workflow.description}")
        print("Actions:")
        for action in actions:
            print(f"- {action}")

async def test_workflow_generalization(awm):
    print("\nTesting workflow generalization...")
    if awm.workflows:
        workflow = awm.workflows[0]
        generalized = await awm._apply_generalization_methods(workflow)
        print(f"Original workflow: {workflow.description}")
        print(f"Generalized workflow: {generalized.description}")
        print("Original steps:")
        for step in workflow.steps:
            print(f"- {step.action}")
        print("Generalized steps:")
        for step in generalized.steps:
            print(f"- {step.action}")

async def test_workflow_evaluation(awm):
    print("\nTesting workflow evaluation...")
    if awm.workflows:
        workflow = awm.workflows[0]
        metrics = await awm.evaluate_workflow(workflow)
        print(f"Evaluation metrics for '{workflow.description}':")
        for metric, value in metrics.items():
            print(f"- {metric}: {value}")

async def test_embedding_memory_integration(awm):
    print("\nTesting embedding memory integration...")
    task = "Login to a website"
    await awm.store_generalized_workflow(awm.workflows[0])  # Store a workflow in embedding memory
    relevant_workflows = await awm.get_relevant_workflows(task)
    print(f"Retrieved workflows from embedding memory for '{task}': {len(relevant_workflows)}")
    for workflow in relevant_workflows:
        print(f"- {workflow.description}")

async def test_workflow_adaptation(awm):
    print("\nTesting workflow adaptation...")
    experience = "Navigate to newsite.com\nClick on sign-in\nEnter email\nEnter password\nClick login"
    await awm.adapt_workflows(experience)
    print("Adapted workflows:")
    for workflow in awm.workflows:
        print(f"- {workflow.description}")
        for step in workflow.steps:
            print(f"  * {step.action}")

async def test_workflow_pruning(awm):
    print("\nTesting workflow pruning...")
    initial_count = len(awm.workflows)
    print(f"Initial workflow count: {initial_count}")
    
    # Add more workflows to exceed the max_workflows limit
    for i in range(awm.max_workflows):
        await awm.induce_workflow([f"Test workflow {i}"])
    
    awm.prune_workflows()
    final_count = len(awm.workflows)
    print(f"Final workflow count after pruning: {final_count}")
    assert final_count <= awm.max_workflows, "Pruning failed to limit workflow count"
from agent import Agent
from tools.helpers import perplexity_search

def execute(agent:Agent, question:str, **kwargs):
    return perplexity_search.perplexity_search(question)
    
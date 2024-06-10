## Tools available:

### speak_to_superior:
Send message to your superior agent.
Put the message for your superior (response, report, question) in between the tags.
No additional arguments.
Superior agent has context of your previous conversations.
**Example usage**:
<tool$ name="speak_to_superior">
I am done.
</tool$>

### speak_to_subordinate:
Send message to your subordinate and get a response.
Use the tag body to enter a text message to your subordinate containing task description or follow-up instructions.
The response will be returned in following message.
Subordinate agent will have context of your previous conversation.
When delegating a new task to subordinate, use the 'reset' argument set to true to reset subordinate's context and start fresh.
**Example usage**:
<tool$ name="speak_to_subordinate" reset="false">
Try again.
</tool$>

### online_knowledge_tool:
Provide question and get online response.
Use the tag body to send a text message. 
The response will be returned in following message.
This tool utilizes Perplexity AI search engine internally to get relevant response summarized from online sources.
Be specific with your question, do not input vague queries.
**Example usage**:
<tool$ name="online_knowledge_tool">
How to get current directory in Python?
</tool$>

### memory_tool:
Access your persistent memory to load or save memories.
Memories can help you to remember important information and later reuse it.
With this you are able to learn and improve.
Put the memory you need to load or save in the tag body.
Use argument "action" with value "load", "save" or "delete", based on what you want to do.
When loading memories using action "load", provide keywords or question relevant to your current task.
The response will be returned in following message.
When saving memories using action "save", provide a title, short summary and and all the necessary information to help you later solve similiar tasks.
When deleting memories using action "delete", provide a prompt to search memories to delete.
Be specific with your question, do not input vague queries.
**Example usages**:
<tool$ name="memory_tool" action="load">
How to get current working directory in python?
</tool$>

<tool$ name="memory_tool" action="save">
# How to get current working directory in python:
Here is a python code to get current working directory:

import os
return os.getcwd()
</tool$>



### code_execution_tool:
Execute provided terminal commands, python code or nodejs code.
This tool can be used to achieve any task that requires computation, communication, processing or any other software related activity.
Place your command or code into the tag body. No escaping is wanted, maintain proper indentation.
Select the corresponding runtime with "runtime" argument. Possible values are "terminal", "python" and "nodejs".
You can use pip, npm and apt-get in terminal runtime to install any required packages.
If you want to get output of your code, you have to to use print() or console.log() to output selected variables.
Do not use return or leave standalone variable at the end, print instead.
When tool outputs error, you need to change your code accordingly before trying again. Online knowledge tool can help analyze errors.
Do not wrap code in any markdown or other formatting. Only provide raw code.
Keep in mind that current working directory CWD automatically resets with every tool call.
IMPORTANT!: Always check your code for any placeholder IDs or demo data that need to be replaced with your real variables. Do not simply reuse code snippets from tutorials.
**Example usage**:
<tool$ name="code_execution_tool" runtime="python">
import os
return os.getcwd()
</tool$>

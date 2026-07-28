from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from typing import TypedDict

# llm = init_chat_model()

# Context from index.py
def agent_process(ticket, application):
  print(f'this is the ticket: {ticket}')
  print(f'this is the application: {application}')


# 1. Define the state
class AgentState(TypedDict):
  understand: 

# Create Tools

# Create the nodes
def agent_comprehend(state: AgentState):
  """ Plan what to do """

def agent_plan(state: AgentState):
  """ Plan what to do """

def agent_action(state: AgentState):
  """ Take action """

def agent_test(state: AgentState):
  """ Take action """

def agent_retry(state: AgentState):
  """ Take action """

def agent_success(state: AgentState):
  """ Take action """


  """ 
  -------------------------------
  Game Plan
  -------------------------------
  → Start
  → Understand
  → Plan
  → Act
  → Test
  → Retry
  → Success
  → END
  -------------------------------
  """

# 3. Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("understand", agent_comprehend)
workflow.add_node("plan", agent_plan)
workflow.add_node("act", agent_action)
workflow.add_node("test", agent_test)
workflow.add_node("retry", agent_retry)
workflow.add_node("success", agent_success)

# 5. Compile and invoke
graph = workflow.compile()
result = graph.invoke({"message": "hello langgraph"})
print(result)  # Output: {'message': 'HELLO LANGGRAPH'}
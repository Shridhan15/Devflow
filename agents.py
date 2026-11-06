# agents.py
import os
from typing import Dict
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticToolsParser

from dotenv import load_dotenv

load_dotenv()
# 1. Initialize the Groq Model (Llama 3.3)
llm = ChatGroq(
    model="openai/gpt-oss-120b",  
    temperature=0.1,
    max_tokens=2000
)

# ---------------------------------------------------------
# Planner Agent Logic
# ---------------------------------------------------------
class PlannerOutput(BaseModel):
    plan: str = Field(description="Step-by-step logic for how to implement the code")

planner_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert software architect. Given a task, write a clear, step-by-step logic plan for how to implement it in Python. Do NOT write the actual code, only the plan."),
    ("human", "Task: {task_description}")
])

# FIX: Explicitly bind the tool and FORCE the model to use it, then parse the output
planner_llm_with_tools = llm.bind_tools([PlannerOutput], tool_choice="PlannerOutput")
planner_chain = planner_prompt | planner_llm_with_tools | PydanticToolsParser(tools=[PlannerOutput])

def planner_node(state: dict):
    print("--- PLANNER AGENT RUNNING ---")
    result = planner_chain.invoke({"task_description": state["task_description"]})
    # PydanticToolsParser returns a list of tool calls. We want the first one.
    return {"plan": result[0].plan}

# ---------------------------------------------------------
# Coder Agent Logic
# ---------------------------------------------------------
class CoderOutput(BaseModel):
    files: Dict[str, str] = Field(description="Dictionary mapping a single filename (e.g., 'script.py') to its complete string of Python code.")

coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python developer. 
    Write the complete, runnable Python code based on the provided plan and task. 
    
    CRITICAL INSTRUCTIONS:
    - Output only the raw code in the dictionary value. No markdown formatting (do not wrap in ```python).
    - Ensure all quotes and newlines inside the code string are properly escaped so the JSON parser does not break.
    - If you receive error logs from a previous attempt, fix the bugs and output the corrected code.
    - The code must be self-contained and ready to execute locally."""),
    ("human", """
    Task: {task_description}
    Plan: {plan}
    Current Files: {files}
    Previous Execution Errors (if any): {test_output}
    """)
])

# FIX: Explicitly bind the tool and FORCE the model to use it, then parse the output
coder_llm_with_tools = llm.bind_tools([CoderOutput], tool_choice="CoderOutput")
coder_chain = coder_prompt | coder_llm_with_tools | PydanticToolsParser(tools=[CoderOutput])

def coder_node(state: dict):
    print("--- CODER AGENT RUNNING ---")
    current_iterations = state.get("iterations", 0) + 1
    
    result = coder_chain.invoke({
        "task_description": state["task_description"],
        "plan": state.get("plan", ""),
        "files": state.get("files", {}),
        "test_output": state.get("test_output", "No errors yet. This is the first attempt.")
    })
    
    # PydanticToolsParser returns a list of tool calls. We want the first one.
    return {
        "files": result[0].files,
        "iterations": current_iterations
    }
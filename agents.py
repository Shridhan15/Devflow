# agents.py
import os
from typing import Dict
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticToolsParser

# Initialize the Groq Model (Llama 3.3)
llm = ChatGroq(
    model="openai/gpt-oss-120b",  
    temperature=0.1,
    max_tokens=2000
)

# ---------------------------------------------------------
# Planner Agent Logic
# ---------------------------------------------------------
class PlannerOutput(BaseModel):
    plan: str = Field(description="Step-by-step logic for how to modify the code.")

planner_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert software architect. You are editing an existing codebase. 
    Given a task and the current code, write a clear, step-by-step logic plan for how to modify the code to implement the request.
    
    CRITICAL INSTRUCTIONS:
    - Do NOT write the actual code, only the plan.
    - Understand the existing code and ensure your plan does not break existing functionality.
    - Outline exactly where the new changes should go."""),
    ("human", """
    Task: {task_description}
    Current Files: {files}
    """)
])

# Explicitly bind the tool and FORCE the model to use it
planner_llm_with_tools = llm.bind_tools([PlannerOutput], tool_choice="PlannerOutput")
planner_chain = planner_prompt | planner_llm_with_tools | PydanticToolsParser(tools=[PlannerOutput])

def planner_node(state: dict):
    print("--- PLANNER AGENT RUNNING ---")
    
    # The planner now receives the existing files loaded by the Reader node
    result = planner_chain.invoke({
        "task_description": state["task_description"],
        "files": state.get("files", {})
    })
    
    return {"plan": result[0].plan}

# ---------------------------------------------------------
# Coder Agent Logic
# ---------------------------------------------------------
class CoderOutput(BaseModel):
    files: Dict[str, str] = Field(description="Dictionary mapping the filename to its COMPLETE string of Python code.")

coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python developer modifying an existing codebase. 
    Update the provided files based on the plan and task. 
    
    CRITICAL INSTRUCTIONS:
    - You MUST return the ENTIRE file content, including both the untouched existing code and your new additions. 
    - NEVER use lazy placeholders like '# existing code here'. If you do not return the full code, the old code will be deleted.
    - Output only the raw code in the dictionary value. No markdown formatting.
    - Ensure all quotes and newlines inside the code string are properly escaped.
    - If you receive error logs from a previous attempt, fix the bugs and output the corrected code."""),
    ("human", """
    Task: {task_description}
    Plan: {plan}
    Current Files: {files}
    Previous Execution Errors (if any): {test_output}
    """)
])

# Explicitly bind the tool and FORCE the model to use it
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
    
    return {
        "files": result[0].files,
        "iterations": current_iterations
    }

# ---------------------------------------------------------
# Reviewer Agent Logic
# ---------------------------------------------------------
class ReviewerOutput(BaseModel):
    is_approved: bool = Field(description="True if the code perfectly meets the requirements and is secure. False otherwise.")
    feedback: str = Field(description="Detailed explanation of why it was approved or rejected.")

reviewer_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a strict Senior Staff Engineer reviewing code changes.
    Check the provided new code against the original task description.
    
    Reject the code (is_approved=False) if:
    1. It does not accomplish the exact task requested.
    2. It accidentally deleted existing functionality from the original file.
    3. It contains obvious security flaws or infinite loops.
    
    If you reject it, provide clear, actionable feedback for the Coder agent to fix it."""),
    ("human", """
    Original Task: {task_description}
    Proposed Code Changes: {files}
    Execution Output: {test_output}
    """)
])

reviewer_llm_with_tools = llm.bind_tools([ReviewerOutput], tool_choice="ReviewerOutput")
reviewer_chain = reviewer_prompt | reviewer_llm_with_tools | PydanticToolsParser(tools=[ReviewerOutput])

def reviewer_node(state: dict):
    print("--- REVIEWER AGENT RUNNING ---")
    
    result = reviewer_chain.invoke({
        "task_description": state["task_description"],
        "files": state.get("files", {}),
        "test_output": state.get("test_output", "")
    })
    
    review = result[0]
    print(f"Reviewer Decision: {'APPROVED' if review.is_approved else 'REJECTED'}")
    print(f"Feedback: {review.feedback}")
    
    return {
        "status": "success" if review.is_approved else "failed",
        "reviewer_feedback": review.feedback
    }
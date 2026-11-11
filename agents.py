# agents.py
import os
from typing import Dict,List
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticToolsParser, JsonOutputParser

# ---------------------------------------------------------
# Logging Utilities (Duplicated to avoid circular imports)
# ---------------------------------------------------------
class Log:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    
    @staticmethod
    def agent(name: str):
        print(f"\n{Log.CYAN}{'='*50}\n⚙️  RUNNING NODE: [{name.upper()}]\n{'='*50}{Log.RESET}")

    @staticmethod
    def state_update(key: str, value: str):
        val_str = str(value)
        print(f"   {Log.YELLOW}↳ {key}:{Log.RESET} {val_str[:100]}..." if len(val_str) > 100 else f"   {Log.YELLOW}↳ {key}:{Log.RESET} {val_str}")

# ---------------------------------------------------------
# Initialize the Groq Model (Llama 3.3)
# ---------------------------------------------------------
llm = ChatGroq(
    model="openai/gpt-oss-20b",  
    temperature=0.1,
    max_tokens=8000
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

planner_chain = planner_prompt | llm.with_structured_output(
    PlannerOutput, method="json_schema"
)

def planner_node(state: dict):
    Log.agent("planner")
    result: PlannerOutput = planner_chain.invoke({
        "task_description": state["task_description"],
        "files": state.get("files", {}),
    })
    Log.state_update("Generated Plan", result.plan)
    return {"plan": result.plan}


# ---------------------------------------------------------
# Coder Agent Logic
# ---------------------------------------------------------
class FileItem(BaseModel):
    filename: str = Field(description="The name of the file (e.g., 'calculator.py')")
    content: str = Field(description="The complete, runnable code for the file.")

class CoderOutput(BaseModel):
    files: List[FileItem] = Field(description="List of files to generate or update.")

coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python developer modifying an existing codebase.
    Update the provided files based on the plan and task.

    CRITICAL INSTRUCTIONS:
    - You MUST return the ENTIRE file content, including both the untouched existing code and your new additions.
    - NEVER use lazy placeholders like '# existing code here'. If you do not return the full code, the old code will be deleted."""),
    ("human", """
    Task: {task_description}
    Plan: {plan}
    Current Files: {files}
    Previous Execution Errors (if any): {test_output}
    """)
])
 
coder_chain = coder_prompt | llm.with_structured_output(
    CoderOutput, method="json_schema"
)

def coder_node(state: dict):
    Log.agent("coder")
    current_iterations = state.get("iterations", 0) + 1

    result: CoderOutput = coder_chain.invoke({
        "task_description": state["task_description"],
        "plan": state.get("plan", ""),
        "files": state.get("files", {}),
        "test_output": state.get("test_output", "No errors yet. This is the first attempt."),
    })

    generated_dict = {f.filename: f.content for f in result.files}

    Log.state_update("Generated Files", list(generated_dict.keys()))
    Log.state_update("Attempt", f"{current_iterations}/{state.get('max_iterations', 3)}")
    return {"files": generated_dict, "iterations": current_iterations}


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

reviewer_chain = reviewer_prompt | llm.with_structured_output(
    ReviewerOutput, method="json_schema"
)

def reviewer_node(state: dict):
    Log.agent("reviewer")
    review: ReviewerOutput = reviewer_chain.invoke({
        "task_description": state["task_description"],
        "files": state.get("files", {}),
        "test_output": state.get("test_output", ""),
    })
    decision = "APPROVED" if review.is_approved else "REJECTED"
    if review.is_approved:
        print(f"   {Log.GREEN}✓ AI Decision: {decision}{Log.RESET}")
    else:
        print(f"   {Log.RED}✗ AI Decision: {decision}{Log.RESET}")
    Log.state_update("Feedback", review.feedback)
    return {
        "status": "success" if review.is_approved else "failed",
        "reviewer_feedback": review.feedback,
    }
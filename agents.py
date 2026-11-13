# agents.py
import json
import time
from typing import Any, Dict, List, Optional, Type

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Logging Utilities
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
    def state_update(key: str, value: Any):
        val_str = str(value)
        shown = f"{val_str[:100]}..." if len(val_str) > 100 else val_str
        print(f"   {Log.YELLOW}↳ {key}:{Log.RESET} {shown}")


# ---------------------------------------------------------
# Small helpers
# ---------------------------------------------------------
def normalize_path(name: str) -> str:
    """Normalize a model/metadata supplied path so dict keys never diverge
    ('src\\a.py' vs './src/a.py' vs 'src/a.py')."""
    name = (name or "").strip().replace("\\", "/")
    while name.startswith("./"):
        name = name[2:]
    return name


def _fmt(value: Any, fallback: str) -> str:
    """Prompt-friendly value: empty/None -> fallback text."""
    return str(value) if value else fallback


# ---------------------------------------------------------
# Initialize the Groq Model (GPT-OSS 120B)
# ---------------------------------------------------------
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.1,
    max_tokens=8000,
    # Passed directly (NOT via model_kwargs). Keeps hidden reasoning tokens from
    # eating the output budget, which is a common cause of truncated JSON.
    reasoning_effort="low",
)


# ---------------------------------------------------------
# Robust structured output
# ---------------------------------------------------------
def _looks_like_schema_echo(obj: Any) -> bool:
    """Detects when the model returned the JSON schema instead of data."""
    return isinstance(obj, dict) and "properties" in obj and ("required" in obj or "title" in obj)


def _example_from_schema(schema: dict, root: dict) -> Any:
    """Build a filled-in example INSTANCE from a pydantic JSON schema."""
    if "$ref" in schema:
        return _example_from_schema(root["$defs"][schema["$ref"].split("/")[-1]], root)
    t = schema.get("type")
    if t == "object":
        return {k: _example_from_schema(v, root) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [_example_from_schema(schema.get("items", {}), root)]
    if t == "boolean":
        return True
    if t in ("integer", "number"):
        return 0
    return f"<{schema.get('description', 'text')}>"


class RobustStructuredChain:
    """
    Tries, in order:
      1. function calling (tool use)
      2. JSON mode with an example instance in the prompt
    Each strategy is retried with the previous error fed back to the model.
    If everything fails, returns `default` (if given) instead of raising.
    """

    def __init__(self, prompt: ChatPromptTemplate, schema: Type[BaseModel],
                 default: Optional[BaseModel] = None, retries_per_strategy: int = 2):
        self.prompt = prompt
        self.schema = schema
        self.default = default
        self.retries = retries_per_strategy

        self.tool_chain = prompt | llm.with_structured_output(schema, method="function_calling")
        self.json_llm = llm.bind(response_format={"type": "json_object"})
        self.json_parser = JsonOutputParser()

    def _example_instance(self) -> str:
        js = self.schema.model_json_schema()
        return json.dumps(_example_from_schema(js, js), indent=2)

    def _run_tool(self, inputs: dict) -> BaseModel:
        result = self.tool_chain.invoke(inputs)
        if result is None:
            raise ValueError("Model returned no structured output")
        return result

    def _run_json(self, inputs: dict) -> BaseModel:
        instructions = (
            "\n\nReturn ONLY a single valid JSON object (no markdown, no prose) "
            "that is an INSTANCE of this shape. Fill in real values, do NOT return a schema:\n"
            f"{self._example_instance()}"
        )
        messages = self.prompt.format_messages(**inputs)
        messages[0].content += instructions  # system message
        raw = self.json_llm.invoke(messages)
        data = self.json_parser.parse(raw.content)
        if _looks_like_schema_echo(data):
            raise ValueError("Model echoed the schema instead of data")
        return self.schema.model_validate(data)

    def invoke(self, inputs: dict) -> BaseModel:
        last_error: Optional[Exception] = None
        for strategy in (self._run_tool, self._run_json):
            for attempt in range(self.retries):
                try:
                    payload = dict(inputs)
                    if last_error and "task_description" in payload:
                        payload["task_description"] = (
                            f"{payload['task_description']}\n\n[NOTE: your previous reply was invalid: "
                            f"{str(last_error)[:300]}. Reply again with real values for every field. "
                            f"Never return a schema or placeholders.]"
                        )
                    return strategy(payload)
                except Exception as e:  # parser, validation, JSON and API errors
                    last_error = e
                    print(f"   ⚠️  {strategy.__name__} attempt {attempt + 1} failed: {str(e)[:150]}")
                    msg = str(e).lower()
                    wait = 10 * (attempt + 1) if ("429" in msg or "rate limit" in msg) else 1.5 * (attempt + 1)
                    time.sleep(wait)

        if self.default is not None:
            print("   ❌ All strategies failed, using safe default.")
            return self.default
        raise RuntimeError(f"All structured-output strategies failed: {last_error}")


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
    - If the task requires adding new functionality, ensure your plan integrates it seamlessly with the existing code.
    - If the task requires removing or deleting code, ensure your plan specifies exactly which parts to remove and how to do it safely.
    - If the task requires modifying existing code, ensure your plan specifies exactly which parts to modify and how to do it safely.
    - If the task requires adding new files, specify the exact file names and their intended content.
    - If the task requires deleting files, specify the exact file names to delete.
    - If review feedback or execution errors are provided, your plan MUST explicitly address each of them.
    - Outline exactly where the new changes should go."""),
    ("human", """
    Task: {task_description}
    Current Files: {files}
    Feedback from the previous review (AI or human), if any: {reviewer_feedback}
    Latest execution output, if any: {test_output}
    """)
])

planner_chain = RobustStructuredChain(planner_prompt, PlannerOutput, default=None)

def planner_node(state: dict):
    Log.agent("planner")
    result: PlannerOutput = planner_chain.invoke({
        "task_description": state["task_description"],
        "files": state.get("files", {}),
        "reviewer_feedback": _fmt(state.get("reviewer_feedback"), "None"),
        "test_output": _fmt(state.get("test_output"), "None"),
    })
    Log.state_update("Generated Plan", result.plan)
    return {"plan": result.plan}


# ---------------------------------------------------------
# Coder Agent Logic
# ---------------------------------------------------------
class FileItem(BaseModel):
    filename: str = Field(description="Relative path of the file (e.g., 'calculator.py' or 'src/utils.py')")
    content: str = Field(description="The complete, runnable code for the file.")

class CoderOutput(BaseModel):
    files: List[FileItem] = Field(description="Files to create or update. Only include files you change.")
    delete_files: List[str] = Field(
        default_factory=list,
        description="Relative paths of files to delete. Empty list if none.",
    )

coder_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python developer modifying an existing codebase.
    Update the provided files based on the plan and task.

    CRITICAL INSTRUCTIONS:
    - Only include files that you create or modify. Unchanged files are preserved automatically.
    - For every file you include, return the ENTIRE file content, including both the untouched existing code and your new additions.
    - NEVER use lazy placeholders like '# existing code here'. If you do not return the full code of an included file, the old code of that file will be deleted.
    - If the task or plan requires removing, deleting, or dropping code inside a file, you MUST completely omit that code from your final output.
    - If the task or plan requires deleting a whole file, list its path in delete_files.
    - If review feedback or execution errors are provided, you MUST fix them."""),
    ("human", """
    Task: {task_description}
    Plan: {plan}
    Current Files: {files}
    Feedback from the previous review (AI or human), if any: {reviewer_feedback}
    Previous Execution Errors (if any): {test_output}
    """)
])

coder_chain = RobustStructuredChain(coder_prompt, CoderOutput, default=None)

def coder_node(state: dict):
    Log.agent("coder")
    current_iterations = state.get("iterations", 0) + 1
    existing: Dict[str, str] = state.get("files", {}) or {}

    result: CoderOutput = coder_chain.invoke({
        "task_description": state["task_description"],
        "plan": state.get("plan", ""),
        "files": existing,
        "reviewer_feedback": _fmt(state.get("reviewer_feedback"), "None"),
        "test_output": _fmt(state.get("test_output"), "No errors yet. This is the first attempt."),
    })

    generated: Dict[str, str] = {}
    for f in result.files:
        name = normalize_path(f.filename)
        if not name:
            continue
        # An empty reply for a non-empty existing file would wipe it.
        if not f.content.strip() and existing.get(name, "").strip():
            Log.state_update("Skipped", f"{name} (empty content would wipe the existing file)")
            continue
        generated[name] = f.content

    to_delete = {normalize_path(n) for n in result.delete_files if n and n.strip()} - set(generated)

    if not generated and not to_delete:
        raise ValueError("Coder returned no usable changes")

    # Merge: keep untouched files, apply changes, drop deleted files.
    merged = {k: v for k, v in existing.items() if k not in to_delete}
    merged.update(generated)
    deleted_files = sorted((set(state.get("deleted_files", [])) | to_delete) - set(generated))

    Log.state_update("Generated Files", list(generated.keys()))
    if to_delete:
        Log.state_update("Deleted Files", sorted(to_delete))
    Log.state_update("Attempt", f"{current_iterations}/{state.get('max_iterations', 3)}")
    return {
        "files": merged,
        "changed_files": sorted(generated),
        "deleted_files": deleted_files,
        "iterations": current_iterations,
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

reviewer_chain = RobustStructuredChain(
    reviewer_prompt, ReviewerOutput,
    # Conservative default: a parser failure triggers another coder pass
    # instead of crashing the graph or falsely approving.
    default=ReviewerOutput(
        is_approved=False,
        feedback="Reviewer failed to produce valid output. Re-check the code against the task and fix any issues.",
    ),
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
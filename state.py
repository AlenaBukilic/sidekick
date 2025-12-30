from typing import Annotated, List, Any, Optional, Dict
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool
    clarification_questions: Optional[List[str]]
    clarification_answers: Optional[List[str]]
    clarification_complete: bool
    task_plan: Optional[List[Dict[str, Any]]]
    parallel_groups: Optional[List[List[int]]]
    current_parallel_group: int
    worker_results: Optional[Dict[int, Any]]
    all_tasks_complete: bool
    planning_complete: bool
    plan_quality_score: Optional[float]
    plan_needs_refinement: bool
    plan_quality_check_enabled: bool
    task_evaluation_results: Optional[Dict[int, Dict[str, Any]]]
    overall_evaluation_score: Optional[float]


from pydantic import BaseModel, Field
from typing import List


class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )


class ClarifyingQuestion(BaseModel):
    question: str = Field(description="A clarifying question to better understand the task")


class ClarifierOutput(BaseModel):
    questions: List[ClarifyingQuestion] = Field(
        description="A list of exactly 3 clarifying questions",
        min_length=3,
        max_length=3
    )


class Subtask(BaseModel):
    description: str = Field(description="Description of the subtask")
    dependencies: List[int] = Field(description="List of subtask indices this task depends on", default_factory=list)
    success_criteria: str = Field(description="Success criteria specific to this subtask")
    can_parallelize: bool = Field(description="Whether this task can run in parallel with others", default=True)


class PlannerOutput(BaseModel):
    subtasks: List[Subtask] = Field(description="List of subtasks to complete the overall task")
    parallel_groups: List[List[int]] = Field(description="Groups of subtask indices that can run in parallel")
    reasoning: str = Field(description="Reasoning for the task division and parallel grouping")


class PlanQualityEvaluation(BaseModel):
    plan_quality_score: float = Field(description="Score 0-1 indicating plan quality", ge=0, le=1)
    plan_needs_refinement: bool = Field(description="True if plan should be refined before execution")
    feedback: str = Field(description="Feedback on plan structure and task division")
    issues: List[str] = Field(description="List of specific issues found in the plan", default_factory=list)


class TaskEvaluationResult(BaseModel):
    subtask_index: int
    completion_score: float = Field(ge=0, le=1)
    is_complete: bool
    feedback: str


class PerTaskEvaluation(BaseModel):
    task_results: List[TaskEvaluationResult] = Field(description="Evaluation results for each task in current group")
    group_passed: bool = Field(description="True if all tasks in group passed")
    needs_refinement: bool = Field(description="True if any task needs refinement")


class OverallEvaluation(BaseModel):
    overall_evaluation_score: float = Field(description="Score 0-1 for overall completion", ge=0, le=1)
    success_criteria_met: bool = Field(description="True if overall success criteria are met")
    feedback: str = Field(description="Comprehensive feedback on overall task completion")
    missing_aspects: List[str] = Field(description="Aspects that are missing or incomplete", default_factory=list)
    needs_additional_tasks: bool = Field(description="True if additional tasks are needed")


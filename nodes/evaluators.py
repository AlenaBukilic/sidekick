from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from state import State
from models import PlanQualityEvaluation, PerTaskEvaluation, OverallEvaluation


def create_evaluator_node(evaluator_llm_with_output):
    """Creates an evaluator node function"""
    def format_conversation(messages: List[Any]) -> str:
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    def evaluator(state: State) -> State:
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

The entire conversation with the assistant, with the user's original request and all replies, is:
{format_conversation(state["messages"])}

The success criteria for this assignment is:
{state["success_criteria"]}

And the final response from the Assistant that you are evaluating is:
{last_response}

Respond with your feedback, and decide if the success criteria is met by this response.
Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

"""
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = evaluator_llm_with_output.invoke(evaluator_messages)
        new_state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {eval_result.feedback}",
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }
        return new_state
    
    return evaluator


def create_plan_quality_evaluator_node(plan_quality_evaluator_llm_with_output):
    """Creates a plan quality evaluator node function"""
    def plan_quality_evaluator(state: State) -> Dict[str, Any]:
        """Evaluates if planner divided tasks into meaningful chunks"""
        task_plan = state.get("task_plan", [])
        parallel_groups = state.get("parallel_groups", [])
        user_message = state["messages"][0].content if state["messages"] else ""
        success_criteria = state.get("success_criteria", "")

        system_message = """You are an evaluator that assesses the quality of task plans.
Evaluate if tasks are meaningfully divided:
- Are tasks appropriately granular (not too fine, not too coarse)?
- Do tasks align with the original goal?
- Are dependencies correctly identified?
- Can parallel groups execute efficiently?

CRITICAL: If the task involves creating a SINGLE output file (PDF, document, report), check that:
- Only ONE subtask is responsible for generating the final file
- Other subtasks prepare content/sections that feed into the final output
- The plan does NOT create multiple versions of the same output
- Subtasks do NOT create intermediate files (.txt, .md) - they should return results as text
- If multiple workers would generate files (intermediate or final), flag this as a critical issue
- Workers should pass results through state/responses, not through file creation

Provide a quality score (0-1) and feedback."""

        plan_summary = "\n".join([
            f"Task {i}: {task['description']} (Dependencies: {task['dependencies']})"
            for i, task in enumerate(task_plan)
        ])
        
        groups_summary = "\n".join([
            f"Group {i}: Tasks {group}"
            for i, group in enumerate(parallel_groups)
        ])

        user_prompt = f"""Original task: {user_message}
Success criteria: {success_criteria}

Task plan:
{plan_summary}

Parallel groups:
{groups_summary}

Evaluate the quality of this plan."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]

        result = plan_quality_evaluator_llm_with_output.invoke(messages)

        return {
            "plan_quality_score": result.plan_quality_score,
            "plan_needs_refinement": result.plan_needs_refinement,
            "messages": [{
                "role": "assistant",
                "content": f"Plan Quality Evaluation:\nScore: {result.plan_quality_score:.2f}\nFeedback: {result.feedback}\nIssues: {', '.join(result.issues) if result.issues else 'None'}"
            }]
        }
    
    return plan_quality_evaluator


def create_per_task_evaluator_node(per_task_evaluator_llm_with_output):
    """Creates a per-task evaluator node function"""
    def per_task_evaluator(state: State) -> Dict[str, Any]:
        """Evaluates if each task/group has been completed within success criteria"""
        task_plan = state.get("task_plan")
        parallel_groups = state.get("parallel_groups")
        current_parallel_group = state.get("current_parallel_group", 0)
        
        if not task_plan or not parallel_groups:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": "Error: Missing task plan or parallel groups for evaluation."
                }]
            }
        
        if current_parallel_group >= len(parallel_groups):
            return {
                "all_tasks_complete": True,
                "messages": [{
                    "role": "assistant",
                    "content": "All parallel groups have been processed."
                }]
            }
        
        current_group = parallel_groups[current_parallel_group]
        worker_results = state.get("worker_results", {})
        task_evaluation_results = state.get("task_evaluation_results", {}).copy()

        # Get subtasks and results for current group (with validation)
        group_tasks = []
        for idx in current_group:
            if isinstance(idx, int) and 0 <= idx < len(task_plan):
                try:
                    subtask = task_plan[idx]
                    result = worker_results.get(idx, "")
                    group_tasks.append({
                        "index": idx,
                        "description": subtask.get("description", "Unknown"),
                        "success_criteria": subtask.get("success_criteria", ""),
                        "result": result
                    })
                except (IndexError, KeyError, TypeError) as e:
                    print(f"Error accessing task_plan[{idx}]: {e}. Skipping.")
                    continue
            else:
                print(f"Warning: Invalid index {idx} in parallel group {current_parallel_group}. Skipping.")
        
        if not group_tasks:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": f"Error: No valid tasks found in parallel group {current_parallel_group} for evaluation."
                }]
            }

        system_message = """You are an evaluator that checks if individual subtasks have been completed successfully.
For each subtask in the current group, evaluate:
- Whether the subtask was completed
- If it meets its specific success criteria
- Quality of the output

Provide a quick pass/fail check for each task."""

        tasks_summary = "\n\n".join([
            f"Task {task['index']}:\nDescription: {task['description']}\nSuccess Criteria: {task['success_criteria']}\nResult: {task['result'][:500]}..."
            for task in group_tasks
        ])

        user_prompt = f"""Evaluate the following tasks from the current parallel group:

{tasks_summary}

Provide evaluation for each task."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]

        result = per_task_evaluator_llm_with_output.invoke(messages)

        for task_result in result.task_results:
            task_evaluation_results[task_result.subtask_index] = {
                "completion_score": task_result.completion_score,
                "is_complete": task_result.is_complete,
                "feedback": task_result.feedback
            }

        all_tasks_complete = state["current_parallel_group"] >= len(state["parallel_groups"]) - 1

        return {
            "task_evaluation_results": task_evaluation_results,
            "all_tasks_complete": all_tasks_complete if result.group_passed else False,
            "messages": [{
                "role": "assistant",
                "content": f"Per-Task Evaluation:\nGroup Passed: {result.group_passed}\nNeeds Refinement: {result.needs_refinement}\n{'All tasks passed!' if result.group_passed else 'Some tasks need refinement.'}"
            }]
        }
    
    return per_task_evaluator


def create_overall_evaluator_node(overall_evaluator_llm_with_output):
    """Creates an overall evaluator node function"""
    def overall_evaluator(state: State) -> Dict[str, Any]:
        """Evaluates overall task completion against original success criteria"""
        task_plan = state.get("task_plan", [])
        worker_results = state.get("worker_results", {})
        task_evaluation_results = state.get("task_evaluation_results", {})
        success_criteria = state.get("success_criteria", "")
        original_message = state["messages"][0].content if state["messages"] else ""

        all_results = []
        for idx, task in enumerate(task_plan):
            result = worker_results.get(idx, "")
            eval_result = task_evaluation_results.get(idx, {})
            all_results.append({
                "task": task["description"],
                "result": result,
                "evaluation": eval_result
            })

        system_message = """You are an evaluator that assesses overall task completion.
Evaluate whether all subtasks collectively achieve the overall goal.
Consider:
- Whether all subtasks together meet the original success criteria
- Quality and coherence of the final output
- Alignment with the original user request
- Integration of all subtask results"""

        results_summary = "\n\n".join([
            f"Task {i}: {r['task']}\nResult: {r['result'][:300]}...\nEvaluation: {r['evaluation'].get('feedback', 'N/A')}"
            for i, r in enumerate(all_results)
        ])

        user_prompt = f"""Original task: {original_message}
Success criteria: {success_criteria}

All subtask results:
{results_summary}

Evaluate if the overall task has been completed successfully."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]

        result = overall_evaluator_llm_with_output.invoke(messages)

        return {
            "overall_evaluation_score": result.overall_evaluation_score,
            "success_criteria_met": result.success_criteria_met,
            "messages": [{
                "role": "assistant",
                "content": f"Overall Evaluation:\nScore: {result.overall_evaluation_score:.2f}\nSuccess Criteria Met: {result.success_criteria_met}\nFeedback: {result.feedback}\nMissing Aspects: {', '.join(result.missing_aspects) if result.missing_aspects else 'None'}"
            }]
        }
    
    return overall_evaluator


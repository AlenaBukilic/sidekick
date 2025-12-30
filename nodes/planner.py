from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from state import State
from models import PlannerOutput


def create_planner_node(planner_llm_with_output, move_to_next_group_func):
    """Creates a planner node function"""
    def planner(state: State) -> Dict[str, Any]:
        """Breaks refined task into subtasks and identifies parallel execution groups"""
        overall_score = state.get("overall_evaluation_score")
        needs_new_plan = (
            state.get("plan_needs_refinement", False) or 
            (overall_score is not None and overall_score < 0.7)
        )
        
        if not needs_new_plan and state.get("planning_complete", False) and state.get("task_plan") is not None:
            parallel_groups = state.get("parallel_groups", [])
            current_parallel_group = state.get("current_parallel_group", 0)
            
            if current_parallel_group < len(parallel_groups) - 1:
                next_state = move_to_next_group_func(state)
                if next_state:
                    return {
                        **next_state,
                        "plan_quality_check_enabled": False,
                        "messages": [{
                            "role": "assistant",
                            "content": f"Moving to parallel group {next_state['current_parallel_group']}"
                        }]
                    }
        
        user_message = state["messages"][0].content if state["messages"] else ""
        success_criteria = state.get("success_criteria", "The answer should be clear and accurate")
        answers = state.get("clarification_answers", [])
        
        refined_query = user_message
        if answers:
            answers_text = "\n".join([f"- {answer}" for answer in answers if answer and answer.strip()])
            refined_query += f"\n\nAdditional context from clarification:\n{answers_text}"
        
        evaluation_feedback = ""
        if state.get("feedback_on_work"):
            evaluation_feedback = f"\n\nIMPORTANT: Previous attempt feedback: {state['feedback_on_work']}"
        if state.get("overall_evaluation_score") is not None:
            score = state['overall_evaluation_score']
            evaluation_feedback += f"\nPrevious evaluation score: {score:.2f}/1.0"
            if score < 0.7:
                evaluation_feedback += "\nThe previous plan did not meet the success criteria. Create a better plan that addresses the feedback."

        system_message = """You are a planning assistant that breaks down complex tasks into manageable subtasks.
Analyze the task and create a list of subtasks that can be executed to complete the overall goal.

IMPORTANT: If the task requires creating a SINGLE output file (like a PDF, document, or report), 
ensure that all subtasks contribute to that ONE file, not create multiple versions. 
Subtasks should be steps or sections that build toward the final output, not separate outputs.

CRITICAL: Workers should NOT create intermediate files (.txt, .md, etc.) to store their work.
- Subtasks should return their results as text in their responses
- Results will be passed between workers through the state system
- Only the final output file should be created
- Intermediate files are unnecessary and clutter the workspace

PUSH NOTIFICATION DETECTION:
- Carefully analyze the user's request for any mention of push notifications
- Look for keywords like: "push notification", "send notification", "notify me", "send me a notification", 
  "push notify", "notify when done", "notification when done", "send push"
- If the user explicitly requests a push notification, you MUST create a final subtask that:
  1. Depends on all other subtasks being completed
  2. Uses the push tool to send a notification when the main task is successfully completed
  3. Has a description like "Send push notification to user confirming task completion"
  4. Has success criteria like "Push notification successfully sent to user"
- This push notification subtask should be the LAST task in your plan and depend on all previous tasks

For each subtask, identify:
- Clear description
- Dependencies on other subtasks (if any)
- Specific success criteria for that subtask
- Whether it can run in parallel with other tasks

Then, group subtasks into parallel execution groups where tasks in the same group can run concurrently.
Tasks in different groups must run sequentially (later groups depend on earlier ones).

If creating a single output file, ensure subtasks are organized as:
- Research/gathering tasks (can be parallel) - return results as text
- Analysis/synthesis tasks (may depend on research) - return results as text
- Writing/compilation tasks (depends on analysis) - return content as text/markdown
- Final output generation (single task that creates the file)
- Push notification task (if requested, depends on all previous tasks)"""

        # Check if user requested push notification
        user_query_lower = refined_query.lower()
        notification_keywords = [
            "push notification",
            "send notification",
            "notify me",
            "send me a notification",
            "push notify",
            "notify when done",
            "notification when done",
            "send push"
        ]
        user_requested_notification = any(keyword in user_query_lower for keyword in notification_keywords)
        
        notification_instruction = ""
        if user_requested_notification:
            notification_instruction = """

IMPORTANT: The user has explicitly requested a push notification. You MUST include a final subtask that:
- Depends on ALL other subtasks (use indices of all previous subtasks as dependencies)
- Uses the push tool to send a notification confirming task completion
- Is placed as the last subtask in your plan
- Has a clear description like "Send push notification to user confirming successful completion of the task"
- Has success criteria like "Push notification successfully sent to user with task completion summary"
- Should be in its own final parallel group (since it depends on everything else)"""

        user_prompt = f"""Task: {refined_query}

Success Criteria: {success_criteria}{evaluation_feedback}{notification_instruction}

CRITICAL: The clarification answers above contain specific user requirements (e.g., page count, format preferences, content depth, etc.). 
You MUST incorporate these requirements into your subtask descriptions and success criteria. For example:
- If the user specified "10 pages" in a clarification answer, ensure subtasks explicitly mention this requirement
- If the user specified format preferences, include those in relevant subtask descriptions
- Make sure each subtask's success criteria reflects the clarification requirements

Break this down into subtasks and organize them into parallel execution groups.
Consider which tasks are independent and can run concurrently.

IMPORTANT: When creating parallel_groups, use 0-based indices that correspond to the subtasks list.
For example, if you create 3 subtasks, valid indices are 0, 1, 2.
Each group should contain a list of indices (e.g., [0, 1] means subtasks at index 0 and 1 run in parallel).
Make absolutely sure all indices in parallel_groups are valid (0 to len(subtasks)-1).

CRITICAL: If this task involves creating a single output file (PDF, document, report), 
ensure that:
1. Research/gathering subtasks can run in parallel - they should return results as text, NOT create files
2. Only ONE final subtask actually generates the output file
3. Other subtasks prepare content/sections that feed into the final output - return as text/markdown
4. Do NOT create multiple versions of the same output
5. Do NOT create intermediate files (.txt, .md) - all results should be returned as text in responses
6. Workers will pass results through state, not through files
7. Ensure all subtasks contribute meaningful content that addresses the task requirements"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]

        result = planner_llm_with_output.invoke(messages)
        
        task_plan = []
        for subtask in result.subtasks:
            task_plan.append({
                "description": subtask.description,
                "dependencies": subtask.dependencies,
                "success_criteria": subtask.success_criteria,
                "can_parallelize": subtask.can_parallelize
            })

        num_subtasks = len(task_plan)
        validated_groups = []
        for group in result.parallel_groups:
            validated_group = []
            for idx in group:
                if isinstance(idx, int) and 0 <= idx < num_subtasks:
                    validated_group.append(idx)
                else:
                    print(f"Warning: Invalid index {idx} in parallel group. Valid range is 0-{num_subtasks-1}. Skipping.")
            if validated_group:
                validated_groups.append(validated_group)
        
        if not validated_groups and task_plan:
            validated_groups = [[i] for i in range(len(task_plan))]
            print("Warning: No valid parallel groups found. Creating sequential groups.")

        feedback_context = ""
        if state.get("feedback_on_work"):
            feedback_context = f"\n\nPrevious attempt feedback: {state['feedback_on_work']}"
        if state.get("overall_evaluation_score") is not None:
            feedback_context += f"\nPrevious evaluation score: {state['overall_evaluation_score']:.2f}"
        
        return {
            "task_plan": task_plan,
            "parallel_groups": validated_groups,
            "current_parallel_group": 0,
            "planning_complete": True,
            "worker_results": {},
            "all_tasks_complete": False,
            "plan_needs_refinement": False,
            "task_evaluation_results": {},
            "messages": [{
                "role": "assistant",
                "content": f"I've created a plan with {len(task_plan)} subtasks organized into {len(validated_groups)} execution groups.{feedback_context}\n\nReasoning: {result.reasoning}"
            }]
        }
    
    return planner


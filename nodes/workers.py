from typing import Dict, Any
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import ToolNode
import asyncio
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from state import State


def create_worker_node(worker_llm_with_tools):
    """Creates a worker node function"""
    def worker(state: State) -> Dict[str, Any]:
        system_message = f"""You are a helpful assistant that can use tools to complete tasks.
    You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.
    You have many tools to help you, including tools to browse the internet, navigating and retrieving web pages.
    You have a tool to run python code, but note that you would need to include a print() statement if you wanted to receive output.
    The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    This is the success criteria:
    {state["success_criteria"]}
    You should reply either with a question for the user about this assignment, or with your final response.
    If you have a question for the user, you need to reply by clearly stating your question. An example might be:

    Question: please clarify whether you want a summary or a detailed answer

    If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
    """

        if state.get("feedback_on_work"):
            system_message += f"""
    Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
    Here is the feedback on why this was rejected:
    {state["feedback_on_work"]}
    With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""

        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        response = worker_llm_with_tools.invoke(messages)

        return {
            "messages": [response],
        }
    
    return worker


def create_process_subtask_node(worker_llm_with_tools, tools):
    """Creates a process_subtask function"""
    async def process_subtask(subtask: Dict[str, Any], subtask_index: int, state: State) -> Dict[str, Any]:
        """Processes a single subtask"""
        system_message = f"""You are a helpful assistant that can use tools to complete tasks.
You are working on a specific subtask as part of a larger plan to create a SINGLE final output.

CRITICAL FILE CREATION RULES:
- DO NOT create intermediate files (.txt, .md, etc.) to store your work or results
- Store your results in your response text - they will be saved in state automatically
- Only create a file if it is EXPLICITLY the final output requested by the user
- If the task is to create a PDF/document, do NOT create intermediate .txt or .md files
- Your results will be passed to other workers through the state system, not through files
- Intermediate files clutter the workspace and are unnecessary

IMPORTANT: If this task involves creating an output file (PDF, document, etc.), you are contributing 
to ONE shared output, not creating your own separate file. Check if other workers have already 
started creating the output, and contribute to that file rather than creating a new one.

Current subtask: {subtask['description']}
Subtask success criteria: {subtask['success_criteria']}

The overall task success criteria is: {state['success_criteria']}
The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

You have many tools to help you, including tools to browse the internet, navigating and retrieving web pages.
You have a tool to run python code, but note that you would need to include a print() statement if you wanted to receive output.
You also have access to a push notification tool - if your subtask involves sending a push notification, use the push tool to send it.

Focus on completing this specific subtask. 
- Return your results as text in your response
- Do NOT use file creation tools unless creating the final output
- If creating content for a PDF/document, return the content as text/markdown in your response
- The final file generation should typically be done by ONE worker, not all workers
- If your subtask is to send a push notification, use the push tool with an appropriate message

When done, provide a clear summary of what you accomplished and include any content/results in your response text."""

        context = ""
        if subtask.get("dependencies"):
            for dep_idx in subtask["dependencies"]:
                if dep_idx in state.get("worker_results", {}):
                    context += f"\nResult from dependent task {dep_idx}: {state['worker_results'][dep_idx]}\n"

        # Include clarification answers if available
        clarification_context = ""
        clarification_answers = state.get("clarification_answers", [])
        if clarification_answers:
            valid_answers = [a for a in clarification_answers if a and str(a).strip()]
            if valid_answers:
                clarification_context = "\n\nIMPORTANT - User Clarification Answers:\n"
                for i, answer in enumerate(valid_answers, 1):
                    clarification_context += f"{i}. {answer}\n"
                clarification_context += "\nThese clarification answers provide important context about the user's requirements. Make sure to incorporate these details into your work."

        user_message = f"""Subtask {subtask_index}: {subtask['description']}
{context}{clarification_context}

CRITICAL INSTRUCTIONS:
- This is part of a larger task to create a SINGLE final output
- DO NOT create intermediate files (.txt, .md) to store your work
- Return all your results, content, and findings as text in your response
- Your results will be automatically saved and passed to other workers
- Only create a file if it is the EXPLICITLY requested final output (e.g., the final PDF)
- If you need to prepare content for a PDF/document, return it as markdown/text in your response
- Do NOT create multiple versions of the same output
- Do NOT create temporary or intermediate files
- Pay close attention to the clarification answers above - they contain specific user requirements that must be met

Please complete this subtask and return your results as text in your response."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message)
        ]

        max_iterations = 5
        iteration = 0
        current_messages = messages
        
        while iteration < max_iterations:
            response = await asyncio.to_thread(worker_llm_with_tools.invoke, current_messages)
            current_messages.append(response)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_node = ToolNode(tools=tools)
                tool_results = await tool_node.ainvoke({"messages": [response]})
                current_messages.extend(tool_results.get("messages", []))
                iteration += 1
            else:
                break
        
        result_content = response.content if hasattr(response, 'content') and response.content else "Task completed."
        
        return {
            "subtask_index": subtask_index,
            "result": result_content
        }
    
    return process_subtask


def create_parallel_worker_group_node(process_subtask_func):
    """Creates a parallel_worker_group node function"""
    async def parallel_worker_group(state: State) -> Dict[str, Any]:
        """Processes all subtasks in current parallel group concurrently"""
        task_plan = state.get("task_plan")
        parallel_groups = state.get("parallel_groups")
        current_parallel_group = state.get("current_parallel_group", 0)
        
        if not task_plan:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": "Error: No task plan found. Please create a plan first."
                }]
            }
        
        if not parallel_groups:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": "Error: No parallel groups found. Please create a plan first."
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
        worker_results = state.get("worker_results", {}).copy()

        valid_indices = []
        for idx in current_group:
            if isinstance(idx, int) and 0 <= idx < len(task_plan):
                valid_indices.append(idx)
            else:
                print(f"Warning: Invalid index {idx} in parallel group {current_parallel_group}. Skipping.")
        
        if not valid_indices:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": f"Error: No valid subtask indices in parallel group {current_parallel_group}."
                }]
            }

        subtasks = []
        for idx in valid_indices:
            try:
                if 0 <= idx < len(task_plan):
                    subtasks.append((idx, task_plan[idx]))
                else:
                    print(f"Warning: Index {idx} out of range [0, {len(task_plan)-1}]. Skipping.")
            except (IndexError, TypeError) as e:
                print(f"Error accessing task_plan[{idx}]: {e}. Skipping.")
                continue
        
        if not subtasks:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": f"Error: No valid subtasks found in parallel group {current_parallel_group} after validation."
                }]
            }

        # Process all subtasks in parallel using asyncio.gather
        results = await asyncio.gather(*[
            process_subtask_func(subtask, idx, state)
            for idx, subtask in subtasks
        ])

        # Store results
        for result in results:
            worker_results[result["subtask_index"]] = result["result"]

        return {
            "worker_results": worker_results,
            "messages": [{
                "role": "assistant",
                "content": f"Completed {len(results)} subtasks in parallel group {state['current_parallel_group']}"
            }]
        }
    
    return parallel_worker_group


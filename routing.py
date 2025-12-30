from typing import Dict, Any
from state import State


def create_route_based_on_evaluation():
    """Creates route_based_on_evaluation function"""
    def route_based_on_evaluation(state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        else:
            return "worker"
    
    return route_based_on_evaluation


def create_route_after_wait_for_user():
    """Creates route_after_wait_for_user function"""
    def route_after_wait_for_user(state: State) -> str:
        """Routes after wait_for_user node"""
        answers = state.get("clarification_answers", [])
        clarification_complete = state.get("clarification_complete", False)
        
        if answers and len(answers) >= 3:
            return "planner"
        
        if clarification_complete:
            return "planner"
        
        if state.get("clarification_questions"):
            return "END"
        
        return "planner"
    
    return route_after_wait_for_user


def create_route_after_planner():
    """Creates route_after_planner function"""
    def route_after_planner(state: State) -> str:
        """Routes after planner - conditionally to plan_quality_evaluator or workers"""
        if state.get("plan_quality_check_enabled", False):
            return "plan_quality_evaluator"
        else:
            return "parallel_worker_group"
    
    return route_after_planner


def create_route_after_plan_quality():
    """Creates route_after_plan_quality function"""
    def route_after_plan_quality(state: State) -> str:
        """Routes after plan quality evaluation"""
        if state.get("plan_needs_refinement", False) or state.get("plan_quality_score", 1.0) < 0.6:
            return "planner"
        else:
            return "parallel_worker_group"
    
    return route_after_plan_quality


def create_move_to_next_group():
    """Creates move_to_next_group function"""
    def move_to_next_group(state: State) -> Dict[str, Any]:
        """Moves to the next parallel group"""
        current = state.get("current_parallel_group", 0)
        total_groups = len(state.get("parallel_groups", []))
        
        if current < total_groups - 1:
            return {
                "current_parallel_group": current + 1
            }
        return {}
    
    return move_to_next_group


def create_route_after_per_task_evaluation():
    """Creates route_after_per_task_evaluation function"""
    def route_after_per_task_evaluation(state: State) -> str:
        """Routes after per-task evaluation"""
        task_eval_results = state.get("task_evaluation_results", {})
        current_group = state["parallel_groups"][state["current_parallel_group"]]
        
        needs_refinement = False
        for idx in current_group:
            eval_result = task_eval_results.get(idx, {})
            if not eval_result.get("is_complete", False):
                needs_refinement = True
                break

        if needs_refinement:
            return "planner"
        
        if state.get("all_tasks_complete", False):
            return "overall_evaluator"
        else:
            return "planner"
    
    return route_after_per_task_evaluation


def create_route_after_overall_evaluation():
    """Creates route_after_overall_evaluation function"""
    def route_after_overall_evaluation(state: State) -> str:
        """Routes after overall evaluation"""
        if state.get("success_criteria_met", False):
            return "END"
        else:
            return "planner"
    
    return route_after_overall_evaluation


def create_route_from_start():
    """Creates route_from_start function"""
    def route_from_start(state: State) -> str:
        answers = state.get("clarification_answers", [])
        questions = state.get("clarification_questions")
        clarification_complete = state.get("clarification_complete", False)
        
        if answers and len(answers) >= 3:
            return "planner"
        
        if clarification_complete:
            return "planner"
        
        if questions and len(questions) >= 3:
            return "wait_for_user"
        
        return "planner"
    
    return route_from_start


def create_worker_router():
    """Creates a worker router function"""
    def worker_router(state: State) -> str:
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        else:
            return "evaluator"
    
    return worker_router


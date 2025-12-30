from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
import sys
from pathlib import Path
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
from state import State
from models import ClarifierOutput


def create_clarifier_node(clarifier_llm_with_output):
    """Creates a clarifier node function"""
    def clarifier(state: State) -> Dict[str, Any]:
        """Generates exactly 3 clarifying questions"""
        existing_questions = state.get("clarification_questions")
        if existing_questions and len(existing_questions) >= 3:
            return {
                "messages": [{
                    "role": "assistant",
                    "content": f"I need to clarify a few things before I start:\n\n1. {existing_questions[0]}\n\n2. {existing_questions[1]}\n\n3. {existing_questions[2]}"
                }]
            }
        
        user_message = state["messages"][-1].content if state["messages"] else ""
        success_criteria = state.get("success_criteria", "The answer should be clear and accurate")
        
        system_message = """You are a helpful assistant that asks clarifying questions to better understand tasks.
Given an initial task request, generate exactly 3 clarifying questions that will help refine and focus the work.
The questions should:
- Help understand the user's specific interests or goals
- Clarify ambiguous aspects of the task
- Identify the scope or depth of information needed
- Be concise and easy to answer

Output exactly 3 questions that will improve the quality and relevance of the work."""

        user_prompt = f"""The user's request is: {user_message}

The success criteria is: {success_criteria}

Generate exactly 3 clarifying questions to better understand this task."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_prompt)
        ]

        result = clarifier_llm_with_output.invoke(messages)
        questions = [q.question for q in result.questions]

        return {
            "clarification_questions": questions,
            "clarification_complete": False,
            "messages": [{
                "role": "assistant",
                "content": f"I need to clarify a few things before I start:\n\n1. {questions[0]}\n\n2. {questions[1]}\n\n3. {questions[2]}"
            }]
        }
    
    return clarifier


def create_wait_for_user_node():
    """Creates a wait_for_user node function"""
    def wait_for_user(state: State) -> Dict[str, Any]:
        """Checks if clarification is complete and routes accordingly"""
        answers = state.get("clarification_answers", [])
        
        valid_answers = [a for a in answers if a and str(a).strip()]
        
        if len(valid_answers) >= 3:
            return {
                "clarification_complete": True,
                "user_input_needed": False
            }
        else:
            return {
                "user_input_needed": True,
                "clarification_complete": False
            }
    
    return wait_for_user


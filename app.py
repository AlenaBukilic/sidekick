import gradio as gr
import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import sidekick
from sidekick import Sidekick


async def setup():
    try:
        sidekick = Sidekick()
        await sidekick.setup()
        return sidekick
    except Exception as e:
        print(f"Error in setup: {e}")
        import traceback
        traceback.print_exc()
        return None


async def process_message(sidekick, message, success_criteria, history, answer1, answer2, answer3):
    if sidekick is None:
        sidekick = Sidekick()
        await sidekick.setup()

    clarification_answers = []
    if answer1 and answer1.strip():
        clarification_answers.append(answer1.strip())
    if answer2 and answer2.strip():
        clarification_answers.append(answer2.strip())
    if answer3 and answer3.strip():
        clarification_answers.append(answer3.strip())
    
    results = await sidekick.run_superstep(message, success_criteria, history, clarification_answers)
    return results, sidekick, "", "", ""


async def get_clarification_questions(sidekick, message, success_criteria):
    """Get clarification questions for the task"""
    if sidekick is None:
        sidekick = Sidekick()
        await sidekick.setup()
    
    if not message or not message.strip():
        return "Please enter a task request first.", sidekick, gr.update(visible=False), gr.update(visible=False)
    
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": sidekick.sidekick_id}}
    
    state = {
        "messages": [HumanMessage(content=message)],
        "success_criteria": success_criteria or "The answer should be clear and accurate",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
        "clarification_questions": None,
        "clarification_answers": [],
        "clarification_complete": False,
        "task_plan": None,
        "parallel_groups": None,
        "current_parallel_group": 0,
        "worker_results": {},
        "all_tasks_complete": False,
        "planning_complete": False,
        "plan_quality_score": None,
        "plan_needs_refinement": False,
        "plan_quality_check_enabled": False,
        "task_evaluation_results": {},
        "overall_evaluation_score": None,
    }
    try:
        clarifier_result = sidekick.clarifier(state)
        questions = clarifier_result.get("clarification_questions", [])
        
        if questions and len(questions) >= 3:
            questions_text = f"## Clarifying Questions\n\n1. {questions[0]}\n\n2. {questions[1]}\n\n3. {questions[2]}\n\nPlease answer these questions to help refine your task."
            return questions_text, sidekick, gr.update(visible=True), gr.update(visible=True)
        else:
            return "Error generating questions. Please try again.", sidekick, gr.update(visible=False), gr.update(visible=False)
    except Exception as e:
        return f"Error: {str(e)}", sidekick, gr.update(visible=False), gr.update(visible=False)


async def reset():
    new_sidekick = Sidekick()
    await new_sidekick.setup()
    return "", "", None, new_sidekick, "", "", "", gr.update(visible=False), gr.update(visible=False)


def free_resources(sidekick):
    """Cleanup function - Gradio delete_callback may not support async directly"""
    print("Cleaning up")
    try:
        if sidekick:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(sidekick.cleanup())
                else:
                    loop.run_until_complete(sidekick.cleanup())
            except RuntimeError:
                asyncio.run(sidekick.cleanup())
    except Exception as e:
        print(f"Exception during cleanup: {e}")


with gr.Blocks(title="Sidekick", theme=gr.themes.Default(primary_hue="emerald")) as ui:
    gr.Markdown("## Sidekick Personal Co-Worker")
    sidekick = gr.State(delete_callback=free_resources)

    with gr.Row():
        chatbot = gr.Chatbot(label="Sidekick", type="messages", height=300)
    
    with gr.Group():
        with gr.Row():
            message = gr.Textbox(show_label=False, placeholder="Your request to the Sidekick")
        with gr.Row():
            success_criteria = gr.Textbox(
                show_label=False, placeholder="What are your success criteria?"
            )
    
    questions_display = gr.Markdown(label="Clarifying Questions (Optional)", visible=False)
    with gr.Group(visible=False) as clarification_group:
        gr.Markdown("### Answer these questions to refine your task (optional)")
        gr.Markdown("*Note: You can click 'Go!' without answering these questions to proceed directly.*")
        answer1 = gr.Textbox(label="Question 1", lines=2)
        answer2 = gr.Textbox(label="Question 2", lines=2)
        answer3 = gr.Textbox(label="Question 3", lines=2)
    
    with gr.Row():
        get_questions_button = gr.Button("Get Clarifying Questions (Optional)", variant="secondary")
        reset_button = gr.Button("Reset", variant="stop")
        go_button = gr.Button("Go!", variant="primary")

    def show_questions(questions_output):
        """Show questions and answer fields"""
        if questions_output and "Clarifying Questions" in questions_output:
            return [
                gr.update(visible=True),
                gr.update(visible=True),
            ]
        return [
            gr.update(visible=False),
            gr.update(visible=False),
        ]

    ui.load(setup, [], [sidekick])
    
    get_questions_button.click(
        get_clarification_questions,
        [sidekick, message, success_criteria],
        [questions_display, sidekick, questions_display, clarification_group]
    ).then(
        show_questions,
        questions_display,
        [questions_display, clarification_group]
    )
    
    message.submit(
        process_message,
        [sidekick, message, success_criteria, chatbot, answer1, answer2, answer3],
        [chatbot, sidekick, answer1, answer2, answer3]
    )
    success_criteria.submit(
        process_message,
        [sidekick, message, success_criteria, chatbot, answer1, answer2, answer3],
        [chatbot, sidekick, answer1, answer2, answer3]
    )
    go_button.click(
        process_message,
        [sidekick, message, success_criteria, chatbot, answer1, answer2, answer3],
        [chatbot, sidekick, answer1, answer2, answer3]
    )
    reset_button.click(
        reset,
        [],
        [message, success_criteria, chatbot, sidekick, answer1, answer2, answer3, questions_display, clarification_group]
    )


ui.launch(inbrowser=True)

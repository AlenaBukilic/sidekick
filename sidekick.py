from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from typing import List, Any
from tools import playwright_tools, other_tools
import uuid
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# Import models and state
from models import (
    EvaluatorOutput,
    ClarifierOutput,
    PlannerOutput,
    PlanQualityEvaluation,
    PerTaskEvaluation,
    OverallEvaluation
)
from state import State

# Import node creators
from nodes.clarifier import create_clarifier_node, create_wait_for_user_node
from nodes.planner import create_planner_node
from nodes.workers import (
    create_worker_node,
    create_process_subtask_node,
    create_parallel_worker_group_node
)
from nodes.evaluators import (
    create_evaluator_node,
    create_plan_quality_evaluator_node,
    create_per_task_evaluator_node,
    create_overall_evaluator_node
)
from nodes.collector import create_collector_node

# Import routing functions
from routing import (
    create_route_based_on_evaluation,
    create_route_after_wait_for_user,
    create_route_after_planner,
    create_route_after_plan_quality,
    create_move_to_next_group,
    create_route_after_per_task_evaluation,
    create_route_after_overall_evaluation,
    create_route_from_start,
    create_worker_router
)

load_dotenv(override=True)


class Sidekick:
    def __init__(self):
        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None
        self.clarifier_llm_with_output = None
        self.planner_llm_with_output = None
        self.plan_quality_evaluator_llm_with_output = None
        self.per_task_evaluator_llm_with_output = None
        self.overall_evaluator_llm_with_output = None
        self.tools = None
        self.llm_with_tools = None
        self.graph = None
        self.clarifier = None  # Store clarifier node function for direct access
        self.sidekick_id = str(uuid.uuid4())
        self.browser = None
        self.playwright = None
        self.db_path = "memory.db"

    async def setup(self):
        raw_conn = await aiosqlite.connect(self.db_path)
        class ConnectionWrapper:
            def __init__(self, conn):
                self._conn = conn
            
            def is_alive(self):
                try:
                    return hasattr(self._conn, '_connection') and self._conn._connection is not None
                except:
                    return False
            
            def __getattr__(self, name):
                return getattr(self._conn, name)
        
        self.db_conn = ConnectionWrapper(raw_conn)
        self.sqlite_memory = AsyncSqliteSaver(self.db_conn)
        
        self.tools, self.browser, self.playwright = await playwright_tools()
        self.tools += await other_tools()
        worker_llm = ChatOpenAI(model="gpt-4o-mini")
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)
        evaluator_llm = ChatOpenAI(model="gpt-4o-mini")
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        clarifier_llm = ChatOpenAI(model="gpt-4o-mini")
        self.clarifier_llm_with_output = clarifier_llm.with_structured_output(ClarifierOutput)
        planner_llm = ChatOpenAI(model="gpt-4o-mini")
        self.planner_llm_with_output = planner_llm.with_structured_output(PlannerOutput)
        plan_quality_llm = ChatOpenAI(model="gpt-4o-mini")
        self.plan_quality_evaluator_llm_with_output = plan_quality_llm.with_structured_output(PlanQualityEvaluation)
        per_task_llm = ChatOpenAI(model="gpt-4o-mini")
        self.per_task_evaluator_llm_with_output = per_task_llm.with_structured_output(PerTaskEvaluation)
        overall_llm = ChatOpenAI(model="gpt-4o-mini")
        self.overall_evaluator_llm_with_output = overall_llm.with_structured_output(OverallEvaluation)
        
        await self.build_graph()

    async def build_graph(self):
        graph_builder = StateGraph(State)

        # Create routing functions
        move_to_next_group = create_move_to_next_group()
        route_from_start = create_route_from_start()
        route_after_wait_for_user = create_route_after_wait_for_user()
        route_after_planner = create_route_after_planner()
        route_after_plan_quality = create_route_after_plan_quality()
        route_after_per_task_evaluation = create_route_after_per_task_evaluation()
        route_after_overall_evaluation = create_route_after_overall_evaluation()
        route_based_on_evaluation = create_route_based_on_evaluation()
        worker_router = create_worker_router()

        # Create node functions
        worker = create_worker_node(self.worker_llm_with_tools)
        evaluator = create_evaluator_node(self.evaluator_llm_with_output)
        clarifier = create_clarifier_node(self.clarifier_llm_with_output)
        self.clarifier = clarifier  # Store for direct access from UI
        wait_for_user = create_wait_for_user_node()
        planner = create_planner_node(self.planner_llm_with_output, move_to_next_group)
        plan_quality_evaluator = create_plan_quality_evaluator_node(self.plan_quality_evaluator_llm_with_output)
        process_subtask = create_process_subtask_node(self.worker_llm_with_tools, self.tools)
        parallel_worker_group = create_parallel_worker_group_node(process_subtask)
        collector = create_collector_node()
        per_task_evaluator = create_per_task_evaluator_node(self.per_task_evaluator_llm_with_output)
        overall_evaluator = create_overall_evaluator_node(self.overall_evaluator_llm_with_output)

        # Add nodes to graph
        graph_builder.add_node("worker", worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", evaluator)
        graph_builder.add_node("clarifier", clarifier)
        graph_builder.add_node("wait_for_user", wait_for_user)
        graph_builder.add_node("planner", planner)
        graph_builder.add_node("plan_quality_evaluator", plan_quality_evaluator)
        graph_builder.add_node("parallel_worker_group", parallel_worker_group)
        graph_builder.add_node("collector", collector)
        graph_builder.add_node("per_task_evaluator", per_task_evaluator)
        graph_builder.add_node("overall_evaluator", overall_evaluator)

        # Add edges
        graph_builder.add_conditional_edges(
            START,
            route_from_start,
            {"clarifier": "clarifier", "planner": "planner"}
        )
        
        graph_builder.add_edge("clarifier", "wait_for_user")
        
        graph_builder.add_conditional_edges(
            "wait_for_user",
            route_after_wait_for_user,
            {"planner": "planner", "END": END}
        )
        
        graph_builder.add_conditional_edges(
            "planner",
            route_after_planner,
            {"plan_quality_evaluator": "plan_quality_evaluator", "parallel_worker_group": "parallel_worker_group"}
        )
        
        graph_builder.add_conditional_edges(
            "plan_quality_evaluator",
            route_after_plan_quality,
            {"planner": "planner", "parallel_worker_group": "parallel_worker_group"}
        )
        
        graph_builder.add_edge("parallel_worker_group", "collector")
        
        graph_builder.add_edge("collector", "per_task_evaluator")
        
        graph_builder.add_conditional_edges(
            "per_task_evaluator",
            route_after_per_task_evaluation,
            {"planner": "planner", "overall_evaluator": "overall_evaluator"}
        )
        
        graph_builder.add_conditional_edges(
            "overall_evaluator",
            route_after_overall_evaluation,
            {"planner": "planner", "END": END}
        )

        graph_builder.add_conditional_edges(
            "worker", worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", route_based_on_evaluation, {"worker": "worker", "END": END}
        )

        self.graph = graph_builder.compile(checkpointer=self.sqlite_memory)

    async def run_superstep(self, message, success_criteria, history, clarification_answers=None):
        config = {
            "configurable": {"thread_id": self.sidekick_id},
            "recursion_limit": 100
        }
        
        if isinstance(message, str):
            messages = [HumanMessage(content=message)]
        else:
            messages = message if isinstance(message, list) else [message]

        valid_answers = []
        if clarification_answers:
            valid_answers = [a for a in clarification_answers if a and str(a).strip()]
        
        clarification_complete = len(valid_answers) >= 3
        
        state = {
            "messages": messages,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
            "clarification_questions": None,
            "clarification_answers": valid_answers,
            "clarification_complete": clarification_complete,
            "task_plan": None,
            "parallel_groups": None,
            "current_parallel_group": 0,
            "worker_results": {},
            "all_tasks_complete": False,
            "planning_complete": False,
            "plan_quality_score": None,
            "plan_needs_refinement": False,
            "plan_quality_check_enabled": True,
            "task_evaluation_results": {},
            "overall_evaluation_score": None,
        }
        
        result = await self.graph.ainvoke(state, config=config)
        
        final_messages = result.get("messages", [])
        if final_messages:
            user = {"role": "user", "content": message if isinstance(message, str) else messages[0].content}
            last_assistant_msg = None
            for msg in reversed(final_messages):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    last_assistant_msg = msg
                    break
                elif isinstance(msg, AIMessage):
                    last_assistant_msg = {"role": "assistant", "content": msg.content}
                    break
            
            if last_assistant_msg:
                return history + [user, last_assistant_msg]
            else:
                return history + [user, {"role": "assistant", "content": "Processing..."}]
        
        return history

    async def cleanup(self):
        if self.browser:
            try:
                await self.browser.close()
                if self.playwright:
                    await self.playwright.stop()
            except Exception as e:
                print(f"Error closing browser/playwright: {e}")
        
        if hasattr(self, 'db_conn') and self.db_conn:
            try:
                if hasattr(self.db_conn, '_conn'):
                    await self.db_conn._conn.close()
                else:
                    await self.db_conn.close()
            except Exception as e:
                print(f"Error closing database connection: {e}")

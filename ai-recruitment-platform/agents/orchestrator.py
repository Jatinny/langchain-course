"""
Agent Orchestrator
Master LangGraph orchestrator that coordinates all agents, routes Kafka events,
manages cross-agent state, and drives the main recruitment automation loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agents.analytics_agent import AnalyticsAgent
from agents.base_agent import AgentState, BaseAgent
from agents.candidate_matching_agent import CandidateMatchingAgent
from agents.commission_tracking_agent import CommissionTrackingAgent
from agents.email_automation_agent import EmailAutomationAgent
from agents.employer_discovery_agent import EmployerDiscoveryAgent
from agents.lead_qualification_agent import LeadQualificationAgent
from agents.recruiter_outreach_agent import RecruiterOutreachAgent
from agents.relationship_management_agent import RelationshipManagementAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task Types
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    DISCOVER_EMPLOYERS = "discover_employers"
    QUALIFY_LEAD = "qualify_lead"
    SEND_OUTREACH = "send_outreach"
    MATCH_CANDIDATE = "match_candidate"
    AUTOMATE_EMAIL = "automate_email"
    MANAGE_RELATIONSHIP = "manage_relationship"
    GENERATE_ANALYTICS = "generate_analytics"
    TRACK_COMMISSION = "track_commission"
    FULL_PIPELINE = "full_pipeline"


# Kafka topic routing table
KAFKA_TOPIC_ROUTING: Dict[str, TaskType] = {
    "employer.discovered": TaskType.QUALIFY_LEAD,
    "employer.qualified": TaskType.SEND_OUTREACH,
    "recruiter.found": TaskType.SEND_OUTREACH,
    "outreach.sent": TaskType.MANAGE_RELATIONSHIP,
    "candidate.matched": TaskType.AUTOMATE_EMAIL,
    "placement.confirmed": TaskType.TRACK_COMMISSION,
    "commission.earned": TaskType.GENERATE_ANALYTICS,
}


# ---------------------------------------------------------------------------
# Orchestrator State
# ---------------------------------------------------------------------------

class OrchestratorState(TypedDict, total=False):
    """State for the master orchestrator workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    task_type: str
    task_payload: Dict[str, Any]
    active_agents: List[str]
    agent_results: Dict[str, Any]
    routing_decision: Optional[str]
    pipeline_stage: Optional[str]
    error: Optional[str]
    retry_count: int
    session_id: str
    completed: bool
    token_usage: Dict[str, int]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class AgentOrchestrator(BaseAgent):
    """
    Master orchestrator that routes tasks to the appropriate specialist agents,
    manages cross-agent state, handles Kafka event consumption, and drives
    the end-to-end recruitment automation pipeline.

    Workflow nodes:
        route_task -> execute_agent -> handle_result -> check_continuation -> END
    """

    KAFKA_CONSUMER_GROUP = "ai-recruitment-orchestrator"

    def __init__(
        self,
        kafka_bootstrap_servers: Optional[str] = None,
        redis_url: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_name="AgentOrchestrator",
            kafka_bootstrap_servers=kafka_bootstrap_servers,
            redis_url=redis_url,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            **kwargs,
        )
        shared_kwargs = {
            "openai_api_key": openai_api_key,
            "anthropic_api_key": anthropic_api_key,
            "kafka_bootstrap_servers": kafka_bootstrap_servers,
            "redis_url": redis_url,
        }

        # Instantiate all specialist agents
        self.agents: Dict[str, BaseAgent] = {
            TaskType.DISCOVER_EMPLOYERS: EmployerDiscoveryAgent(**shared_kwargs),
            TaskType.QUALIFY_LEAD: LeadQualificationAgent(**shared_kwargs),
            TaskType.SEND_OUTREACH: RecruiterOutreachAgent(**shared_kwargs),
            TaskType.MATCH_CANDIDATE: CandidateMatchingAgent(**shared_kwargs),
            TaskType.AUTOMATE_EMAIL: EmailAutomationAgent(**shared_kwargs),
            TaskType.MANAGE_RELATIONSHIP: RelationshipManagementAgent(**shared_kwargs),
            TaskType.GENERATE_ANALYTICS: AnalyticsAgent(**shared_kwargs),
            TaskType.TRACK_COMMISSION: CommissionTrackingAgent(**shared_kwargs),
        }

        self._graph = self._build_graph()
        self._running = False
        self.logger.info("Orchestrator initialised with %d agents.", len(self.agents))

    # ------------------------------------------------------------------
    # Graph
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        workflow = StateGraph(OrchestratorState)
        workflow.add_node("route_task", self._node_route_task)
        workflow.add_node("execute_agent", self._node_execute_agent)
        workflow.add_node("handle_result", self._node_handle_result)
        workflow.add_node("check_continuation", self._node_check_continuation)

        workflow.set_entry_point("route_task")
        workflow.add_edge("route_task", "execute_agent")
        workflow.add_edge("execute_agent", "handle_result")
        workflow.add_edge("handle_result", "check_continuation")
        workflow.add_conditional_edges(
            "check_continuation",
            self._should_continue,
            {"continue": "route_task", "end": END},
        )
        return workflow.compile()

    def _should_continue(self, state: OrchestratorState) -> str:
        if state.get("completed", False) or state.get("error"):
            return "end"
        next_stage = state.get("pipeline_stage")
        if next_stage and next_stage != state.get("task_type"):
            return "continue"
        return "end"

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    async def _node_route_task(self, state: OrchestratorState) -> OrchestratorState:
        """Determine which agent should handle the current task."""
        self.log_state_transition("START/loop", "route_task", list(state.keys()))
        task_type = state.get("task_type", TaskType.DISCOVER_EMPLOYERS)

        # Use LLM for complex routing decisions when task_type is ambiguous
        if task_type == "auto":
            payload_desc = json.dumps(state.get("task_payload", {}), default=str)[:500]
            prompt = (
                f"Given this task payload, classify it into one of these task types: "
                f"{', '.join(t.value for t in TaskType if t != TaskType.FULL_PIPELINE)}\n\n"
                f"Payload: {payload_desc}\n\n"
                f"Respond with ONLY the task_type value, no other text."
            )
            try:
                decision = await self.invoke_llm([{"role": "user", "content": prompt}])
                task_type = decision.strip()
            except Exception:
                task_type = TaskType.DISCOVER_EMPLOYERS

        routing_decision = task_type
        self.logger.info("Routing task to: %s", routing_decision)
        return {**state, "routing_decision": routing_decision, "task_type": task_type}

    async def _node_execute_agent(self, state: OrchestratorState) -> OrchestratorState:
        """Invoke the appropriate specialist agent."""
        self.log_state_transition("route_task", "execute_agent", list(state.keys()))
        task_type = state.get("routing_decision", TaskType.DISCOVER_EMPLOYERS)
        payload = state.get("task_payload", {})

        agent = self.agents.get(task_type)
        if not agent:
            return {**state, "error": f"No agent found for task type: {task_type}"}

        agent_results = dict(state.get("agent_results", {}))

        try:
            result = await self._invoke_agent(agent, task_type, payload)
            agent_results[task_type] = {
                "result": result,
                "completed_at": time.time(),
                "status": "success",
            }
            self.logger.info("Agent %s completed successfully.", task_type)
        except Exception as exc:
            self.logger.error("Agent %s failed: %s", task_type, exc)
            agent_results[task_type] = {
                "error": str(exc),
                "completed_at": time.time(),
                "status": "failed",
            }
            return {**state, "agent_results": agent_results, "error": str(exc)}

        return {**state, "agent_results": agent_results, "active_agents": [task_type]}

    async def _invoke_agent(
        self,
        agent: BaseAgent,
        task_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch to the correct agent run() signature."""
        task = payload.get("task", f"Execute {task_type}")

        if task_type == TaskType.DISCOVER_EMPLOYERS:
            return await agent.run(  # type: ignore[attr-defined]
                task=task,
                region=payload.get("region", "India"),
                industry=payload.get("industry"),
                target_role=payload.get("target_role"),
            )
        elif task_type == TaskType.QUALIFY_LEAD:
            return await agent.run(task=task, lead=payload.get("lead", payload))  # type: ignore[attr-defined]
        elif task_type == TaskType.SEND_OUTREACH:
            return await agent.run(  # type: ignore[attr-defined]
                task=task,
                contact=payload.get("contact"),
                channel=payload.get("channel", "email"),
                jd_data=payload.get("jd_data"),
            )
        elif task_type == TaskType.MATCH_CANDIDATE:
            return await agent.run(  # type: ignore[attr-defined]
                task=task,
                resume_text=payload.get("resume_text"),
                job_description=payload.get("job_description"),
            )
        elif task_type == TaskType.AUTOMATE_EMAIL:
            return await agent.run(  # type: ignore[attr-defined]
                task=task,
                recipient=payload.get("recipient"),
                email_config=payload.get("email_config"),
            )
        elif task_type == TaskType.MANAGE_RELATIONSHIP:
            return await agent.run(  # type: ignore[attr-defined]
                task=task,
                contact=payload.get("contact"),
                interaction_history=payload.get("interaction_history", []),
            )
        elif task_type == TaskType.GENERATE_ANALYTICS:
            return await agent.run(task=task, report_type=payload.get("report_type", "weekly"))  # type: ignore[attr-defined]
        elif task_type == TaskType.TRACK_COMMISSION:
            return await agent.run(task=task, placement=payload.get("placement"))  # type: ignore[attr-defined]
        else:
            return await agent.run(task=task)  # type: ignore[attr-defined]

    async def _node_handle_result(self, state: OrchestratorState) -> OrchestratorState:
        """Process the agent result and determine the next pipeline stage."""
        self.log_state_transition("execute_agent", "handle_result", list(state.keys()))
        if state.get("error"):
            return {**state, "completed": True}

        task_type = state.get("task_type")
        agent_results = state.get("agent_results", {})
        current_result = agent_results.get(task_type, {}).get("result", {})

        # Cache results in Redis
        try:
            await self.cache_set(
                f"result:{state.get('session_id')}:{task_type}",
                current_result,
                ttl_seconds=3600,
            )
        except Exception as exc:
            self.logger.warning("Cache set failed: %s", exc)

        # Determine next pipeline stage based on task type
        pipeline_progression = {
            TaskType.DISCOVER_EMPLOYERS: TaskType.QUALIFY_LEAD,
            TaskType.QUALIFY_LEAD: TaskType.SEND_OUTREACH,
            TaskType.SEND_OUTREACH: TaskType.MANAGE_RELATIONSHIP,
            TaskType.MATCH_CANDIDATE: TaskType.AUTOMATE_EMAIL,
        }
        next_stage = pipeline_progression.get(task_type)

        return {**state, "pipeline_stage": next_stage, "completed": next_stage is None}

    async def _node_check_continuation(self, state: OrchestratorState) -> OrchestratorState:
        """Prepare state for the next pipeline stage if continuing."""
        self.log_state_transition("handle_result", "check_continuation", list(state.keys()))
        if state.get("completed", False) or not state.get("pipeline_stage"):
            return {**state, "completed": True}

        # Update task_type and payload for next stage
        next_stage = state["pipeline_stage"]
        current_results = state.get("agent_results", {})
        current_task = state.get("task_type")
        current_result = current_results.get(current_task, {}).get("result", {})

        # Build payload for next stage from current results
        next_payload = self._build_next_payload(next_stage, current_result, state.get("task_payload", {}))

        return {
            **state,
            "task_type": next_stage,
            "task_payload": next_payload,
            "routing_decision": next_stage,
        }

    def _build_next_payload(
        self,
        next_stage: str,
        current_result: Dict[str, Any],
        original_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract relevant data from current result to seed next stage payload."""
        if next_stage == TaskType.QUALIFY_LEAD:
            employers = current_result.get("scored_employers", [])
            return {"lead": employers[0] if employers else original_payload, "task": "Qualify discovered employer lead"}
        elif next_stage == TaskType.SEND_OUTREACH:
            contacts = current_result.get("lead", {}).get("contacts", [])
            contact = contacts[0] if contacts else original_payload.get("contact", {})
            return {"contact": contact, "task": "Send outreach to qualified employer contact"}
        elif next_stage == TaskType.MANAGE_RELATIONSHIP:
            return {
                "contact": original_payload.get("contact", {}),
                "task": "Record outreach interaction and assess relationship",
                "interaction_history": [],
            }
        return original_payload

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        task_type: str = TaskType.DISCOVER_EMPLOYERS,
        task_payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute an orchestrated workflow starting from the given task type.

        Args:
            task: Human-readable task description.
            task_type: Starting task type (TaskType enum value).
            task_payload: Data payload for the task.

        Returns:
            Dict with agent_results, completed status, and session_id.
        """
        session_id = str(uuid.uuid4())
        initial: OrchestratorState = {
            "messages": [],
            "task_type": task_type,
            "task_payload": task_payload or {"task": task},
            "active_agents": [],
            "agent_results": {},
            "routing_decision": None,
            "pipeline_stage": None,
            "error": None,
            "retry_count": 0,
            "session_id": session_id,
            "completed": False,
            "token_usage": {},
        }

        self.logger.info(
            "Orchestrator starting session=%s task_type=%s",
            session_id,
            task_type,
        )
        final = await self._graph.ainvoke(initial)

        return {
            "session_id": session_id,
            "completed": final.get("completed", False),
            "agent_results": final.get("agent_results", {}),
            "error": final.get("error"),
            "token_usage": self.token_tracker.to_dict(),
        }

    async def process_state(self, state: AgentState) -> AgentState:
        meta = state.get("metadata", {})
        result = await self.run(
            task=state.get("task", "orchestrate"),
            task_type=meta.get("task_type", TaskType.DISCOVER_EMPLOYERS),
            task_payload=meta.get("task_payload"),
        )
        return {**state, "result": result, "updated_at": time.time()}

    async def run_full_pipeline(
        self,
        region: str = "India",
        target_role: str = "Java Developer",
        industry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete end-to-end recruitment pipeline:
        Discover -> Qualify -> Outreach -> Manage Relationships -> Analytics
        """
        self.logger.info(
            "Starting full pipeline: region=%s role=%s",
            region,
            target_role,
        )
        return await self.run(
            task=f"Full pipeline for {target_role} in {region}",
            task_type=TaskType.DISCOVER_EMPLOYERS,
            task_payload={
                "task": f"Discover {target_role} employers in {region}",
                "region": region,
                "target_role": target_role,
                "industry": industry,
            },
        )

    # ------------------------------------------------------------------
    # Kafka event loop
    # ------------------------------------------------------------------

    async def start_kafka_consumer_loop(
        self,
        topics: Optional[List[str]] = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        """
        Start the Kafka event consumer loop.
        Reads events from platform topics and routes them to appropriate agents.
        Runs until stop() is called.
        """
        if topics is None:
            topics = list(KAFKA_TOPIC_ROUTING.keys())

        consumer = self.create_kafka_consumer(
            topics=topics,
            group_id=self.KAFKA_CONSUMER_GROUP,
        )

        self._running = True
        self.logger.info(
            "Kafka consumer loop started. Topics: %s",
            topics,
        )

        try:
            while self._running:
                messages = consumer.poll(timeout_ms=int(poll_interval_seconds * 1000), max_records=10)
                for tp, records in messages.items():
                    for record in records:
                        await self._handle_kafka_event(record.topic, record.value or {})
                await asyncio.sleep(0)  # yield control
        except Exception as exc:
            self.logger.error("Kafka consumer loop error: %s", exc)
        finally:
            consumer.close()
            self.logger.info("Kafka consumer loop stopped.")

    async def _handle_kafka_event(self, topic: str, payload: Dict[str, Any]) -> None:
        """Route a Kafka event to the appropriate agent."""
        task_type = KAFKA_TOPIC_ROUTING.get(topic)
        if not task_type:
            self.logger.warning("No route found for Kafka topic: %s", topic)
            return

        self.logger.info(
            "Received Kafka event on topic=%s -> routing to %s",
            topic,
            task_type,
        )

        try:
            await self.run(
                task=f"Handle {topic} event",
                task_type=task_type,
                task_payload=payload,
            )
        except Exception as exc:
            self.logger.error(
                "Failed to handle Kafka event from topic=%s: %s",
                topic,
                exc,
            )

    def stop(self) -> None:
        """Signal the consumer loop to stop."""
        self._running = False
        self.logger.info("Orchestrator stop signal sent.")

    async def close(self) -> None:
        """Close all agent connections."""
        self.stop()
        for agent in self.agents.values():
            try:
                await agent.close()
            except Exception as exc:
                self.logger.warning("Error closing agent: %s", exc)
        await super().close()

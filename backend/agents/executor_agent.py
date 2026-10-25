from __future__ import annotations

import re
import uuid
from pathlib import Path

from core.agent_base import Agent
from services.tool_router import pick_route
from config import WORKSPACE_DIR
from utils.logging_setup import get_logger

logger = get_logger("jarvis.executor")


class ExecutorAgent(Agent):

    def __init__(self, bus):
        super().__init__("executor", bus)
        self.sessions: dict[str, dict] = {}

    async def handle_message(self, msg):

        msg_type = msg.get("type")
        payload = msg.get("payload", {})

        # --------------------------------------------------
        # START EXECUTION
        # --------------------------------------------------

        if msg_type == "execute_plan":

            request_id = payload.get("original_msg_id")

            if not request_id:
                logger.error("execute_plan without request_id")
                return

            self.sessions[request_id] = {
                "goal": payload.get("goal", ""),
                "mode": payload.get("mode", "general"),
                "steps": payload.get("steps", []),
                "index": 0,
                "results": [],
                "waiting_permission": None,
            }

            logger.info(
                "execution_started",
                extra={"request_id": request_id},
            )

            await self._run_next_step(request_id)

        # --------------------------------------------------
        # TOOL RESULT
        # --------------------------------------------------

        elif msg_type == "tool_result":

            request_id = payload.get("original_msg_id")

            session = self.sessions.get(request_id)

            if not session:
                logger.warning("session_not_found")
                return

            if session["index"] >= len(session["steps"]):
                return

            step = session["steps"][session["index"]]

            result_text = payload.get("result") or ""

            session["results"].append(
                {
                    "step": step,
                    "result": result_text,
                    "artifact": payload.get("artifact"),
                }
            )

            await self.bus.send(
                "main",
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": "main",
                    "type": "step_finished",
                    "payload": {
                        "original_msg_id": request_id,
                        "step": step.get("title", str(step)),
                        "result": result_text,
                        "artifact": payload.get("artifact"),
                    },
                },
            )

            session["index"] += 1
            session["waiting_permission"] = None

            await self._run_next_step(request_id)

        # --------------------------------------------------
        # PERMISSION RESULT
        # --------------------------------------------------

        elif msg_type == "permission_result":

            request_id = payload.get("original_msg_id")
            session = self.sessions.get(request_id)

            if not session:
                return

            pending = session.get("waiting_permission")

            if not pending:
                return

            if pending["request_id"] != payload.get("request_id"):
                return

            if not payload.get("allowed"):

                self.sessions.pop(request_id, None)

                await self.bus.send(
                    "main",
                    {
                        "id": str(uuid.uuid4()),
                        "from": self.name,
                        "to": "main",
                        "type": "request_failed",
                        "payload": {
                            "original_msg_id": request_id,
                            "error": f"Действие отклонено: {pending['reason']}",
                        },
                    },
                )

                return

            session["waiting_permission"] = None

            await self._dispatch_step(request_id, pending["step"])

    # --------------------------------------------------
    # RUN NEXT STEP
    # --------------------------------------------------

    async def _run_next_step(self, request_id: str):

        session = self.sessions.get(request_id)

        if not session:
            return

        if session["index"] >= len(session["steps"]):

            results = session["results"]

            result_text = "\n\n".join(
                str(r.get("result", ""))
                for r in results
                if r.get("result")
            ) or "Задача выполнена."

            logger.info(
                "execution_completed",
                extra={"request_id": request_id},
            )

            await self.bus.send(
                "critic",
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": "critic",
                    "type": "review_result",
                    "payload": {
                        "original_msg_id": request_id,
                        "goal": session.get("goal", ""),
                        "result": result_text,
                        "artifacts": [
                            r.get("artifact")
                            for r in results
                            if r.get("artifact")
                        ],
                    },
                },
            )

            self.sessions.pop(request_id, None)

            return

        step = session["steps"][session["index"]]

        await self.bus.send(
            "main",
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": "main",
                "type": "step_started",
                "payload": {
                    "original_msg_id": request_id,
                    "step": step.get("title", str(step)),
                    "index": session["index"] + 1,
                    "total": len(session["steps"]),
                },
            },
        )

        if step.get("requires_permission"):

            pending = self._build_permission(request_id, step, session)

            session["waiting_permission"] = pending

            await self.bus.send(
                "policy",
                {
                    "id": str(uuid.uuid4()),
                    "from": self.name,
                    "to": "policy",
                    "type": "check_permission",
                    "payload": pending,
                },
            )

            return

        await self._dispatch_step(request_id, step)

    # --------------------------------------------------
    # DISPATCH STEP
    # --------------------------------------------------

    async def _dispatch_step(self, request_id: str, step: dict):

        session = self.sessions.get(request_id)

        if not session:
            return

        route = step.get("route") or pick_route(
            step.get("title", ""),
            session["mode"]
        )

        target = step.get("target")

        destination = {
            "files": "file",
            "network": "network",
            "web": "web",
            "system": "performance",
            "vision": "vision",
            "voice": "voice",
            "backup": "backup",
            "memory": "memory",
            "game": "game_coach",
        }.get(route, "social")

        logger.info(
            "dispatch_tool",
            extra={
                "request_id": request_id,
                "route": route,
                "agent": destination,
            },
        )

        await self.bus.send(
            destination,
            {
                "id": str(uuid.uuid4()),
                "from": self.name,
                "to": destination,
                "type": "tool_request",
                "payload": {
                    "original_msg_id": request_id,
                    "step": step.get("title", ""),
                    "step_meta": step,
                    "goal": session.get("goal", ""),
                    "mode": session.get("mode", "general"),
                    "target": target,
                },
            },
        )

    # --------------------------------------------------

    def _extract_url(self, text: str) -> str | None:

        match = re.search(r"(https?://\S+)", text)

        return match.group(1) if match else None

    def _extract_path(self, text: str) -> str | None:

        match = re.search(r"([\w./\\-]+\.[\w]+)", text)

        return match.group(1) if match else None
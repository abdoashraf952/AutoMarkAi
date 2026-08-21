"""Campaign cadence scheduler — Phase 4.

Demo implementation: asyncio background tasks that periodically
re-invoke the supervisor on live sessions (campaign_phase == 'operate').

Cadences (per Section 13 of the architecture plan):
  - Metrics optimisation: every 6 h
  - Daily diagnosis:      every 24 h (after attribution settles ~T+24h)
  - Timer sweep:          every 15 min (check for scheduled launches)

Production path: swap asyncio tasks for Celery beat (single) or
EventBridge for exactly-once semantics. The graph itself is cadence-
agnostic — the scheduler only re-invokes the supervisor on a saved
thread, which resumes from the checkpoint.

Usage (called from api.py lifespan):
    scheduler = CampaignScheduler(sessions_store, pipeline_graph)
    await scheduler.start()
    ...
    await scheduler.stop()
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Hour of day (UTC) at which the daily diagnosis fires.
# Defaults to 9 AM UTC (matches attribution-settle window for Egypt ~T+24h).
# Override with LIFECYCLE_DIAGNOSIS_HOUR in .env (0–23).
_DIAGNOSIS_HOUR = int(os.getenv("LIFECYCLE_DIAGNOSIS_HOUR", "9"))

# Cadence intervals (seconds)
_CADENCE = {
    "metrics":   6 * 3600,   # every 6 hours
    "diagnosis": 24 * 3600,  # every 24 hours (time-of-day check inside _tick)
    "timer":     15 * 60,    # every 15 minutes
}

_DEMO_CADENCE = {
    "metrics":   300,   # 5 min in demo
    "diagnosis": 600,   # 10 min in demo
    "timer":     60,    # 1 min in demo
}


class CampaignScheduler:
    """
    Background asyncio scheduler for operate-loop cadences.

    Holds a reference to the in-memory sessions store and the compiled
    pipeline graph so it can re-invoke sessions that have reached the
    'operate' phase.
    """

    def __init__(
        self,
        sessions: dict,
        get_graph: Callable[[], Any],
        demo_mode: bool = True,
    ) -> None:
        self._sessions = sessions
        self._get_graph = get_graph
        self._cadence = _DEMO_CADENCE if demo_mode else _CADENCE
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._run_cadence("metrics", self._cadence["metrics"])),
            asyncio.create_task(self._run_cadence("diagnosis", self._cadence["diagnosis"])),
            asyncio.create_task(self._run_cadence("timer", self._cadence["timer"])),
        ]
        logger.info(
            "CampaignScheduler started (demo=%s, metrics=%ds, diagnosis=%ds, timer=%ds)",
            True, self._cadence["metrics"], self._cadence["diagnosis"], self._cadence["timer"],
        )

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("CampaignScheduler stopped")

    async def _run_cadence(self, name: str, interval: int) -> None:
        while self._running:
            await asyncio.sleep(interval)
            try:
                await self._tick(name)
            except Exception as e:
                logger.error("scheduler cadence '%s' error: %s", name, e)

    async def _tick(self, cadence: str) -> None:
        """Run one cadence tick across all active operate sessions.

        The 'diagnosis' cadence is additionally gated on LIFECYCLE_DIAGNOSIS_HOUR
        in production mode: it only fires when the current UTC hour matches.
        Demo mode skips the hour gate so tests don't have to wait until 9 AM.
        """
        if cadence == "diagnosis" and self._cadence is _CADENCE:
            current_hour = datetime.now(timezone.utc).hour
            if current_hour != _DIAGNOSIS_HOUR:
                logger.debug(
                    "scheduler diagnosis: UTC hour=%d, target=%d — skipping",
                    current_hour, _DIAGNOSIS_HOUR,
                )
                return

        operate_sessions = [
            (sid, s) for sid, s in self._sessions.items()
            if s.get("ui_stage") == "done"
            and (s.get("final_state") or {}).get("campaign_phase") == "operate"
        ]

        if not operate_sessions:
            logger.debug("scheduler %s tick: no active operate sessions", cadence)
            return

        logger.info(
            "scheduler %s tick: triggering %d operate session(s)",
            cadence, len(operate_sessions),
        )

        for sid, session in operate_sessions:
            try:
                await self._advance_operate(sid, session, cadence)
            except Exception as e:
                logger.error("scheduler: error advancing session %s: %s", sid, e)

    async def _advance_operate(self, session_id: str, session: dict, cadence: str) -> None:
        """Re-invoke the pipeline on a session with campaign_phase='operate'."""
        from langgraph.types import Command

        graph = self._get_graph()
        config = {"configurable": {"thread_id": session["thread_id"]}}

        # Re-enter with operate phase
        input_ = Command(resume={"campaign_phase": "operate", "_cadence": cadence})

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = session.get("event_queue", asyncio.Queue())

        def push(event: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def _run() -> None:
            for chunk in graph.stream(input_, config, stream_mode="values"):
                if chunk.get("latest_diagnosis"):
                    push({
                        "event": "progress",
                        "stage": "diagnosis",
                        "message": chunk["latest_diagnosis"].get("status", "Diagnosis complete"),
                        "data": chunk["latest_diagnosis"],
                    })
                if chunk.get("decisions_log"):
                    decisions = chunk["decisions_log"]
                    if decisions:
                        last = decisions[-1]
                        push({
                            "event": "progress",
                            "stage": "operate_decision",
                            "message": f"Decision: {last.get('decision')} — {last.get('rationale', '')[:100]}",
                        })

        await asyncio.to_thread(_run)
        logger.info(
            "scheduler: operate cycle complete for session %s (cadence=%s)",
            session_id, cadence,
        )

    async def trigger_session(self, session_id: str) -> dict:
        """
        Manually trigger an immediate operate cycle for one session.
        Used by the POST /session/{id}/operate endpoint for demo purposes.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"error": f"Session {session_id} not found"}

        try:
            await self._advance_operate(session_id, session, "manual")
            return {"ok": True, "session_id": session_id}
        except Exception as e:
            logger.error("manual operate trigger failed for %s: %s", session_id, e)
            return {"error": str(e)}

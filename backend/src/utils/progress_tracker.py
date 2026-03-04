"""Progress timeline tracker for query execution replay.

Accumulates timestamped progress messages during query execution
so the full timeline can be stored and replayed on the frontend.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- mypy --strict compliant
"""

import json
import time
from typing import Any
from uuid import UUID

from backend.src.services.query_history import QueryHistoryService


class ProgressTracker:
    """Accumulates progress messages with elapsed timestamps for replay.

    Wraps QueryHistoryService.update_progress_message() so each call
    both writes to the database AND appends to an in-memory timeline.

    Attributes:
        history_service: Service for writing progress to the database.
        query_id: UUID of the query being tracked.
        username: Username for schema context.
        start_time: Epoch timestamp when tracking began.
        timeline: Accumulated timeline entries.
    """

    def __init__(
        self,
        history_service: QueryHistoryService,
        query_id: UUID,
        username: str,
        start_time: float,
    ) -> None:
        """Initialise the tracker.

        Args:
            history_service: Service for writing progress to the database.
            query_id: UUID of the query being tracked.
            username: Username for schema context.
            start_time: Epoch timestamp (time.time()) when processing began.
        """
        self.history_service: QueryHistoryService = history_service
        self.query_id: UUID = query_id
        self.username: str = username
        self.start_time: float = start_time
        self.timeline: list[dict[str, Any]] = []

    def update(self, message: str) -> None:
        """Record a progress message and write it to the database.

        Args:
            message: Human-readable progress description.
        """
        elapsed_ms: int = int((time.time() - self.start_time) * 1000)
        self.timeline.append({"elapsed_ms": elapsed_ms, "message": message})
        self.history_service.update_progress_message(self.query_id, self.username, message)

    def get_timeline_json(self) -> str:
        """Return the accumulated timeline as a JSON string for JSONB storage.

        Returns:
            JSON string representation of the timeline array.
        """
        return json.dumps(self.timeline)

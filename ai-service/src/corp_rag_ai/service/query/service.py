from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from corp_rag_ai.domain.query import QueryInput, QueryResult


class QueryService:
    def __init__(self, graph: Any, *, clock: Callable[[], float] = time.perf_counter) -> None:
        self._graph = graph
        self._clock = clock

    async def answer(self, query: QueryInput) -> QueryResult:
        state = await self._graph.ainvoke({"query": query, "started_at": self._clock()})
        result = state.get("final_result")
        if not isinstance(result, QueryResult):
            raise RuntimeError("query graph completed without a final result")
        return result

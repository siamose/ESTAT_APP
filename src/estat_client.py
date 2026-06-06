from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests


ESTAT_API_BASE_URL = "https://api.e-stat.go.jp/rest/3.0/app/json"


class EstatApiError(RuntimeError):
    pass


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


class EstatClient:
    def __init__(
        self,
        app_id: str,
        *,
        base_url: str = ESTAT_API_BASE_URL,
        timeout: int = 30,
    ) -> None:
        self.app_id = app_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {"appId": self.app_id, "lang": "J", **params}
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            params=request_params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        self._raise_for_api_error(payload)
        return payload

    @staticmethod
    def _raise_for_api_error(payload: dict[str, Any]) -> None:
        roots = ["GET_STATS_DATA", "GET_STATS_LIST"]
        for root in roots:
            result = get_nested(payload, root, "RESULT")
            if not result:
                continue
            status = str(result.get("STATUS", "0"))
            if status not in {"0", ""}:
                message = result.get("ERROR_MSG") or result.get("MESSAGE") or "e-Stat API error"
                raise EstatApiError(f"{status}: {message}")

    def get_stats_data(
        self,
        stats_data_id: str,
        *,
        limit: int | None = None,
        collect_all_pages: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"statsDataId": stats_data_id}
        if limit is not None:
            params["limit"] = limit

        first_payload = self._get("getStatsData", params)
        if not collect_all_pages:
            return first_payload

        merged = deepcopy(first_payload)
        next_key = get_nested(
            first_payload,
            "GET_STATS_DATA",
            "STATISTICAL_DATA",
            "DATA_INF",
            "NEXT_KEY",
        )
        while next_key:
            next_payload = self._get(
                "getStatsData",
                {**params, "startPosition": next_key},
            )
            self._append_values(merged, next_payload)
            next_key = get_nested(
                next_payload,
                "GET_STATS_DATA",
                "STATISTICAL_DATA",
                "DATA_INF",
                "NEXT_KEY",
            )
        return merged

    def search_stats_list(
        self,
        *,
        search_word: str | None = None,
        stats_code: str | None = None,
        survey_date: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if search_word:
            params["searchWord"] = search_word
        if stats_code:
            params["statsCode"] = stats_code
        if survey_date:
            params["surveyDate"] = survey_date
        return self._get("getStatsList", params)

    @staticmethod
    def _append_values(target: dict[str, Any], source: dict[str, Any]) -> None:
        target_data_inf = get_nested(
            target,
            "GET_STATS_DATA",
            "STATISTICAL_DATA",
            "DATA_INF",
            default={},
        )
        source_values = ensure_list(
            get_nested(
                source,
                "GET_STATS_DATA",
                "STATISTICAL_DATA",
                "DATA_INF",
                "VALUE",
                default=[],
            )
        )
        target_values = ensure_list(target_data_inf.get("VALUE"))
        target_data_inf["VALUE"] = target_values + source_values
        target_data_inf.pop("NEXT_KEY", None)

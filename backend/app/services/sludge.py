"""污泥处置业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sludge"
CARRIER_FIELD = "承运单位"
REQUIRED_FIELDS = ["处置单号", "污泥来源", "含水率"]
STATUS_ORDER = ["待外运", "运输中", "已接收", "已退回"]
RETURNED_STATUS = STATUS_ORDER[-1]
PENDING_STATUSES = {"待外运", "运输中"}
ACTION_RULES = {"安排外运": "运输中", "确认接收": "已接收", "退回污泥": "已退回"}
ACTION_STATUSES = {
    "安排外运": {"待外运"},
    "确认接收": {"运输中"},
    "退回污泥": {"运输中", "已接收", "已退回"},
}
IDEMPOTENT_ACTIONS = {"退回污泥"}
UNKNOWN_CARRIER = "未填写承运单位"


class SludgeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("处置单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["处置状态"] = STATUS_ORDER[0]
        rows.append(entry)
        return entry, []

    def carrier_stats(self) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            carrier = str(row.get(CARRIER_FIELD) or "").strip() or UNKNOWN_CARRIER
            item = stats.setdefault(carrier, {
                CARRIER_FIELD: carrier,
                "total": 0,
                "pending": 0,
                "abnormal": 0,
                "returned": 0,
            })
            item["total"] += 1
            status = row.get("status")
            if status in PENDING_STATUSES:
                item["pending"] += 1
            if status == RETURNED_STATUS:
                item["abnormal"] += 1
                item["returned"] += 1
        return [stats[carrier] for carrier in sorted(stats)]

    def summary(self) -> dict[str, int]:
        items = self.carrier_stats()
        return {
            "total": sum(int(item["total"]) for item in items),
            "pending": sum(int(item["pending"]) for item in items),
            "abnormal": sum(int(item["abnormal"]) for item in items),
            "returned": sum(int(item["returned"]) for item in items),
        }

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"污泥处置单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于污泥处置可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        current_status = str(entry.get("status") or "")
        if current_status == target and action in IDEMPOTENT_ACTIONS:
            return entry, "污泥处置单已退回，无需重复退回"
        if current_status not in ACTION_STATUSES[action]:
            return None, f"污泥处置单当前为{current_status or '未命名状态'}，不能{action}"

        entry["status"] = target
        entry["pending"] = target in PENDING_STATUSES
        if action == "安排外运":
            entry["abnormal"] = entry.get("abnormal", False)
        elif target == RETURNED_STATUS:
            entry["abnormal"] = True
        entry["处置状态"] = target
        return entry, f"污泥处置单已{action}"

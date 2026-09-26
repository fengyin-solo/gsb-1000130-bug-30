"""检测人员业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "staff"
REQUIRED_FIELDS = ["员工编号", "姓名", "技术职称"]
STATUS_ORDER = ["在岗", "培训中", "离岗", "停岗"]
ACTION_RULES = {"安排培训": "培训中", "确认离岗": "离岗", "恢复在岗": "在岗"}
NEGATIVE_ACTIONS: list[str] = []

# 编号精确定位，名称类字段模糊包含；keyword 在编号、姓名、职称里同时找。
# 列表、详情、导出共用这一套口径，保证两条入口定位到同一条记录。
CODE_FIELD = "员工编号"
TEXT_FIELDS = ["姓名", "技术职称"]
KEYWORD_FIELDS = [CODE_FIELD, *TEXT_FIELDS]


def _text(value: Any) -> str:
    return str(value or "").strip()


class StaffService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        filters: dict[str, str | None] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [
            row
            for row in store.rows(MODULE)
            if self._matches(row, keyword=keyword, status=status, filters=filters)
        ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._present(row) if row is not None else None

    @staticmethod
    def _matches(
        row: dict[str, Any],
        *,
        keyword: str | None,
        status: str | None,
        filters: dict[str, str | None] | None,
    ) -> bool:
        if keyword:
            if not any(keyword in _text(row.get(field)) for field in KEYWORD_FIELDS):
                return False
        if status and _text(row.get("status")) != status:
            return False
        filters = filters or {}
        code = _text(filters.get(CODE_FIELD))
        if code and _text(row.get(CODE_FIELD)).upper() != code.upper():
            # 编号精确匹配：STAF-0001 不应把 STAF-00010 一起带出来
            return False
        for field in TEXT_FIELDS:
            expected = _text(filters.get(field))
            if expected and expected not in _text(row.get(field)):
                return False
        return True

    @staticmethod
    def _present(row: dict[str, Any]) -> dict[str, Any]:
        """列表、详情、导出共用的序列化：拷贝行数据，把真实状态回填到展示列。"""
        entry = dict(row)
        entry["在岗状态"] = _text(row.get("status"))
        return entry

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
        rows.append(entry)
        return self._present(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测员 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检测人员可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self._present(entry), f"检测员已{action}"

"""检测人员接口：维护检测员，覆盖安排培训、确认离岗、恢复在岗等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.staff import StaffService

router = APIRouter(prefix="/api/staff", tags=["检测人员"])

service = StaffService()

LIST_FIELDS = ["员工编号", "姓名", "技术职称", "资质证书", "授权项目", "在岗状态", "考核日期", "考核结果"]
STATUSES = ["在岗", "培训中", "离岗", "停岗"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    number: str | None = Query(default=None, description="按员工编号模糊检索"),
    name: str | None = Query(default=None, description="按姓名模糊检索"),
    title: str | None = Query(default=None, description="按技术职称模糊检索"),
    status: str | None = Query(default=None, description="在岗、培训中、离岗、停岗"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按编号、姓名、职称、状态组合过滤检测人员列表；条件冲突时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if status and status.strip() and status.strip() not in STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"状态「{status}」不在允许范围：{'、'.join(STATUSES)}",
        )
    items, total = service.list_entries(
        number=number, name=name, title=title, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    number: str | None = Query(default=None, description="按员工编号模糊检索"),
    name: str | None = Query(default=None, description="按姓名模糊检索"),
    title: str | None = Query(default=None, description="按技术职称模糊检索"),
    status: str | None = Query(default=None, description="在岗、培训中、离岗、停岗"),
) -> dict[str, Any]:
    """导出检测人员清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(
        number=number, name=name, title=title, status=status, page=1, size=10000
    )
    return {"module": "staff", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测员明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检测员 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测员，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检测员已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测员执行安排培训、确认离岗、恢复在岗；记录不存在返回 404，动作冲突返回 409。"""
    if service.get_entry(entry_id) is None:
        raise HTTPException(status_code=404, detail=f"检测员 {entry_id} 不存在或已归档")
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        raise HTTPException(status_code=409, detail=message)
    return ActionResult(ok=True, message=message, entry=entry)

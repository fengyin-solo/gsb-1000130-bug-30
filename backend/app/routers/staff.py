"""检测人员接口：维护检测员，覆盖安排培训、确认离岗、恢复在岗等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.staff import StaffService

router = APIRouter(prefix="/api/staff", tags=["检测人员"])

service = StaffService()

LIST_FIELDS = ["员工编号", "姓名", "技术职称", "资质证书", "授权项目", "在岗状态", "考核日期", "考核结果"]
STATUSES = ["在岗", "培训中", "离岗", "停岗"]

# 列表与导出认得的检索参数；除此之外一律视为笔误并显式拒绝，
# 避免条件被静默丢弃、列表悄悄退回全量。
KNOWN_PARAMS = {"keyword", "status", "page", "size", "员工编号", "姓名", "技术职称"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def search_criteria(
    request: Request,
    keyword: str | None = Query(default=None, description="按员工编号、姓名或技术职称模糊检索"),
    status: str | None = Query(default=None, description="在岗、培训中、离岗、停岗"),
    staff_code: str | None = Query(default=None, alias="员工编号", description="按员工编号精确定位"),
    name: str | None = Query(default=None, alias="姓名", description="按姓名模糊检索"),
    title: str | None = Query(default=None, alias="技术职称", description="按技术职称模糊检索"),
) -> dict[str, Any]:
    """解析并校验检索条件：无法识别的参数、非法状态都显式报错，不再静默吞掉。"""
    unknown = sorted(key for key in request.query_params if key not in KNOWN_PARAMS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"无法识别的检索条件：{'、'.join(unknown)}；支持 员工编号、姓名、技术职称、status、keyword",
        )
    status = _clean(status)
    if status and status not in STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"状态「{status}」不在允许的状态序列里：{'、'.join(STATUSES)}",
        )
    return {
        "keyword": _clean(keyword),
        "status": status,
        "filters": {"员工编号": _clean(staff_code), "姓名": _clean(name), "技术职称": _clean(title)},
    }


@router.get("", response_model=PageResult[dict])
def list_entries(
    criteria: dict[str, Any] = Depends(search_criteria),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按编号、姓名、技术职称与状态组合过滤；条件互相矛盾时返回空页，不报错。"""
    if page < 1:
        raise HTTPException(status_code=400, detail="页码从 1 开始，请调整 page 参数")
    if size < 1 or size > 200:
        raise HTTPException(status_code=400, detail="每页 1–200 条，请缩小分页范围")
    items, total = service.list_entries(**criteria, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：/export 必须声明在 /{entry_id} 之前，否则 "export" 会被当成记录编号解析，
# 导出入口会被 422 顶掉、明细一条也拿不到。
@router.get("/export")
def export_entries(criteria: dict[str, Any] = Depends(search_criteria)) -> dict[str, Any]:
    """导出检测人员清单：返回当前过滤条件下的全量数据，口径与列表一致。"""
    items, total = service.list_entries(**criteria, page=1, size=10000)
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
    """对单条检测员执行安排培训、确认离岗、恢复在岗；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

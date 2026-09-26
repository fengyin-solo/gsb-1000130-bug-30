"""检测人员检索定位回归测试：列表、详情、导出三条入口口径一致。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import SEED_ROWS
from app.store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_staff_rows():
    """每个用例前还原检测人员数据，避免动作类用例互相污染。"""
    rows = store.rows("staff")
    rows[:] = [dict(row) for row in SEED_ROWS["staff"]]
    yield


def test_list_without_criteria_returns_all():
    payload = client.get("/api/staff").json()
    assert payload["total"] == 3
    assert [item["员工编号"] for item in payload["items"]] == ["STAF-0001", "STAF-0002", "STAF-0003"]


def test_search_by_name_and_title():
    payload = client.get("/api/staff", params={"姓名": "检测人员样例2"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2

    payload = client.get("/api/staff", params={"技术职称": "样例3"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 3


def test_search_by_code_is_exact():
    payload = client.get("/api/staff", params={"员工编号": "STAF-0002"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["员工编号"] == "STAF-0002"
    # 编号是精确定位：只给前缀不应把别的记录带出来
    payload = client.get("/api/staff", params={"员工编号": "STAF-000"}).json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_keyword_matches_code_name_and_title():
    payload = client.get("/api/staff", params={"keyword": "检测人员样例2"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 2

    payload = client.get("/api/staff", params={"keyword": "STAF-0003"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == 3


def test_search_by_status_shows_real_status():
    payload = client.get("/api/staff", params={"status": "培训中"}).json()
    assert payload["total"] == 1
    assert payload["items"][0]["status"] == "培训中"
    # 展示列回填真实状态，列表里能直接核对筛选结果
    assert payload["items"][0]["在岗状态"] == "培训中"


def test_conflicting_criteria_return_empty_page():
    # 编号与状态互相矛盾：空页，不报错
    response = client.get("/api/staff", params={"员工编号": "STAF-0001", "status": "培训中"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["items"] == []


def test_unknown_param_is_rejected():
    response = client.get("/api/staff", params={"部门": "理化室"})
    assert response.status_code == 400
    assert "部门" in response.json()["detail"]


def test_invalid_status_is_rejected():
    response = client.get("/api/staff", params={"status": "在职"})
    assert response.status_code == 400
    assert "在职" in response.json()["detail"]


def test_invalid_pagination_is_rejected():
    assert client.get("/api/staff", params={"page": 0}).status_code == 400
    assert client.get("/api/staff", params={"size": 0}).status_code == 400
    assert client.get("/api/staff", params={"size": 201}).status_code == 400


def test_export_is_not_shadowed_by_detail_route():
    response = client.get("/api/staff/export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "staff"
    assert payload["total"] == 3


def test_export_matches_list_under_same_criteria():
    params = {"status": "在岗"}
    listed = client.get("/api/staff", params=params).json()
    exported = client.get("/api/staff/export", params=params).json()
    assert exported["total"] == listed["total"]
    assert [item["id"] for item in exported["items"]] == [item["id"] for item in listed["items"]]


def test_detail_matches_list_row():
    listed = client.get("/api/staff", params={"员工编号": "STAF-0002"}).json()
    entry_id = listed["items"][0]["id"]
    detail = client.get(f"/api/staff/{entry_id}").json()
    for field in ["员工编号", "姓名", "技术职称", "在岗状态"]:
        assert detail[field] == listed["items"][0][field]


def test_detail_missing_returns_404():
    response = client.get("/api/staff/999")
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_action_then_search_locates_same_entry():
    # 连续操作：状态流转后按新状态仍能定位到同一条记录，明细不丢
    response = client.post("/api/staff/1/actions", json={"values": {"action": "安排培训"}})
    assert response.json()["ok"] is True

    payload = client.get("/api/staff", params={"status": "培训中"}).json()
    assert 1 in [item["id"] for item in payload["items"]]

    detail = client.get("/api/staff/1").json()
    assert detail["status"] == "培训中"
    assert detail["姓名"] == "检测人员样例1"

    exported = client.get("/api/staff/export", params={"status": "培训中"}).json()
    assert 1 in [item["id"] for item in exported["items"]]

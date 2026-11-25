"""BUGFIX-29 · 同车二次过磅升代：三红先行。

红一（甲）：同车再磅须同事务作废旧票、升新代；现状旧票未废、新票已正式，
            同车双正式并存。
红二（乙）：未晋升的影子新代不得被对账双计；现状对账把旧票与新票一并计重。
红三（争用）：双会话同车二次过磅须抢车号锁；后到只记争用痕、不写业务。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app
from db import connect, init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _auth(c: TestClient, user="admin", password="admin123") -> dict:
    tok = c.post(
        "/api/login", json={"username": user, "password": password}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def _lane_id(c: TestClient, h: dict, code="LN-N-01-IN") -> int:
    items = c.get("/api/lanes", headers=h).json()["items"]
    return next(x for x in items if x["lane_code"] == code)["id"]


def _axles(*weights: float) -> list[dict]:
    return [{"axle": i + 1, "w": w} for i, w in enumerate(weights)]


def _weigh(
    c: TestClient,
    h: dict,
    *,
    lane_id: int,
    plate: str,
    bl_ref: str,
    code: str,
    axles: list[dict],
):
    return c.post(
        "/api/tickets",
        headers=h,
        json={
            "lane_id": lane_id,
            "bl_ref": bl_ref,
            "vehicle_plate": plate,
            "axle_weights": axles,
            "ticket_code": code,
        },
    )


def _ticket_by_code(code: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM weigh_tickets WHERE ticket_code=?", (code,)
        ).fetchone()
        return dict(row) if row else None


def _formal_of(plate: str) -> list[dict]:
    with connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """SELECT * FROM weigh_tickets
                   WHERE vehicle_plate=? AND status!='作废' ORDER BY id""",
                (plate,),
            ).fetchall()
        ]


def _reproduce_same_vehicle_dual_formal(
    c: TestClient, h: dict, lane_id: int, plate: str, bl_ref: str
) -> tuple[dict, dict]:
    """复现埋雷夹具：同车牌连打两票，旧逻辑旧票不废、新票即为正式。"""
    first = _weigh(
        c,
        h,
        lane_id=lane_id,
        plate=plate,
        bl_ref=bl_ref,
        code="WT-29-甲-001",
        axles=_axles(9.0, 10.0, 11.0),
    )
    second = _weigh(
        c,
        h,
        lane_id=lane_id,
        plate=plate,
        bl_ref=bl_ref,
        code="WT-29-甲-002",
        axles=_axles(10.0, 11.0, 11.0),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    return first.json(), second.json()


def test_reweigh_voids_old_and_bumps_single_formal_chain():
    c = TestClient(app)
    h = _auth(c)
    lane_id = _lane_id(c, h)
    plate = "测甲·29001"

    _first, second = _reproduce_same_vehicle_dual_formal(
        c, h, lane_id, plate, "BL-2026-0101"
    )

    # 同车只允许一张正式票，且必须是新代
    formal = _formal_of(plate)
    assert [t["ticket_code"] for t in formal] == ["WT-29-甲-002"], (
        "同车双正式并存：" f"{[(t['ticket_code'], t['status']) for t in formal]}"
    )
    assert formal[0]["status"] in ("已裁定", "旁路挂起")

    # 旧票在同一次过磅事务内作废
    old = _ticket_by_code("WT-29-甲-001")
    assert old is not None and old["status"] == "作废"

    # 升新代，而非再插一张一代正式票
    assert second["generation"] == 2

    # 血缘边唯一接续：旧票 -> 新票（二次升代）
    edges = c.get("/api/lineage", headers=h).json()["items"]
    up = [e for e in edges if e["from_code"] == "WT-29-甲-001"]
    assert len(up) == 1
    assert up[0]["to_code"] == "WT-29-甲-002"
    assert up[0]["edge_type"] == "二次升代"

    # 升代命运条：单正式、接续完整、当班锁死
    fates = c.get("/api/lineage/fates", headers=h).json()["items"]
    fate = next(f for f in fates if f["vehicle_plate"] == plate)
    assert fate["formal_count"] == 1
    assert fate["current_ticket_code"] == "WT-29-甲-002"
    assert fate["chain_ok"] is True
    assert fate["locked"] is True
    assert fate["issues"] == []


def test_reweigh_void_old_not_double_counted_by_reconcile():
    c = TestClient(app)
    h = _auth(c)
    lane_id = _lane_id(c, h)
    plate = "测乙·29002"
    bl = "BL-29-乙"

    reg = c.post(
        "/api/bl",
        headers=h,
        json={
            "bl_code": bl,
            "cargo_desc": "卷板钢材",
            "declared_gross_t": 47.0,
            "vessel_voyage": "试航/29",
        },
    )
    assert reg.status_code == 200, reg.text

    first = _weigh(
        c,
        h,
        lane_id=lane_id,
        plate=plate,
        bl_ref=bl,
        code="WT-29-乙-001",
        axles=_axles(15.0, 15.0, 15.0, 15.0),
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "旁路挂起"

    # 驳载后同车再磅：影子新代晋升为唯一正式票
    second = _weigh(
        c,
        h,
        lane_id=lane_id,
        plate=plate,
        bl_ref=bl,
        code="WT-29-乙-002",
        axles=_axles(12.0, 12.0, 12.0, 11.0),
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "已裁定"

    recon = c.get(f"/api/reconcile/{bl}", headers=h).json()
    # 未晋升前的旧票只作影子，不得与晋升票双计
    assert recon["ticket_sum_t"] == 47.0, (
        "对账双计：" f"过磅合计={recon['ticket_sum_t']} 票={[t['ticket_code'] for t in recon['tickets']]}"
    )
    assert [t["ticket_code"] for t in recon["tickets"]] == ["WT-29-乙-002"]
    assert recon["balanced"] is True
    assert recon["double_formal"] == []
    assert [t["ticket_code"] for t in recon["voided_tickets"]] == ["WT-29-乙-001"]
    assert recon["seals"] == []

    # 晋升票须为新代
    assert second.json()["generation"] == 2

    # 旧票开放超重挂起随作废闭环，不得继续计数
    open_holds = c.get("/api/overloads?status=开放", headers=h).json()["items"]
    assert not any(x["ticket_code"] == "WT-29-乙-001" for x in open_holds)


def test_two_sessions_reweigh_contend_on_plate_lock_only_trace():
    c = TestClient(app)
    h_admin = _auth(c, "admin", "admin123")
    h_writer = _auth(c, "writer", "writer123")
    lane_id = _lane_id(c, h_admin)
    plate = "测丙·29003"
    lock_key = f"plate:{plate}"

    first = _weigh(
        c,
        h_admin,
        lane_id=lane_id,
        plate=plate,
        bl_ref="BL-2026-0101",
        code="WT-29-丙-001",
        axles=_axles(9.0, 10.0, 10.0),
    )
    assert first.status_code == 200, first.text

    # 第一会话抢住车号锁
    assert (
        c.post(
            "/api/locks/acquire", headers=h_admin, json={"lock_key": lock_key}
        ).status_code
        == 200
    )
    try:
        # 第二会话同车再磅：只记争用痕，不落业务
        late = _weigh(
            c,
            h_writer,
            lane_id=lane_id,
            plate=plate,
            bl_ref="BL-2026-0101",
            code="WT-29-丙-002",
            axles=_axles(10.0, 10.0, 11.0),
        )
        assert late.status_code == 409
        assert "争用" in late.json()["detail"]

        with connect() as conn:
            rows = conn.execute(
                "SELECT ticket_code, status FROM weigh_tickets WHERE vehicle_plate=?",
                (plate,),
            ).fetchall()
        assert [r["ticket_code"] for r in rows] == ["WT-29-丙-001"]
        assert _ticket_by_code("WT-29-丙-002") is None

        contention = c.get("/api/contention", headers=h_admin).json()["items"]
        assert any(
            x["lock_key"] == lock_key and x["actor"] == "writer"
            for x in contention
        )
    finally:
        c.post(
            "/api/locks/release", headers=h_admin, json={"lock_key": lock_key}
        )

    # 锁释放后同会话可正常升代
    ok = _weigh(
        c,
        h_admin,
        lane_id=lane_id,
        plate=plate,
        bl_ref="BL-2026-0101",
        code="WT-29-丙-002",
        axles=_axles(10.0, 10.0, 11.0),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["generation"] == 2
    assert _ticket_by_code("WT-29-丙-001")["status"] == "作废"


def _craft_ticket(
    lane_id: int,
    *,
    code: str,
    plate: str,
    bl_ref: str,
    gross: float,
    generation: int,
    status: str,
    superseded_by: int | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO weigh_tickets(ticket_code,lane_id,bl_ref,vehicle_plate,
               axle_weights,gross_t,generation,status,created_at,superseded_by)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (code, lane_id, bl_ref, plate, "[]", gross, generation, status,
             "2026-01-01T00:00:00", superseded_by),
        )
        conn.commit()
        return int(cur.lastrowid)


def test_fate_deviation_rejects_write_and_keeps_trace():
    """旧库漏废形成的同车双正式：命运条偏航，拒写并留痕，不得再添正式。"""
    c = TestClient(app)
    h = _auth(c)
    lane_id = _lane_id(c, h)
    plate = "测偏·29004"
    _craft_ticket(lane_id, code="WT-DEV-001", plate=plate,
                  bl_ref="BL-2026-0101", gross=30.0, generation=1, status="已裁定")
    _craft_ticket(lane_id, code="WT-DEV-002", plate=plate,
                  bl_ref="BL-2026-0101", gross=31.0, generation=2, status="已裁定")

    fate = c.get(f"/api/lineage/fate/{plate}", headers=h).json()
    assert fate["chain_ok"] is False
    assert fate["formal_count"] == 2
    assert any("双正式" in x for x in fate["issues"])

    res = _weigh(
        c, h, lane_id=lane_id, plate=plate, bl_ref="BL-2026-0101",
        code="WT-DEV-003", axles=_axles(9.0, 10.0),
    )
    assert res.status_code == 409
    assert "偏航" in res.json()["detail"]
    assert _ticket_by_code("WT-DEV-003") is None

    audit = c.get("/api/audit", headers=h).json()["items"]
    assert any(
        a["action"] == "reweigh_fate_deviation" and a["target"] == plate
        for a in audit
    )
    # 偏航条不得谎报锁死为可写
    assert c.get(f"/api/lineage/fate/{plate}", headers=h).json()["locked"] is False


def test_shadow_generation_not_promoted_is_not_double_counted():
    """乙：影子新代已落但未晋升（旧票仍正式）时，对账只计正式旧票，不得双计。"""
    c = TestClient(app)
    h = _auth(c)
    lane_id = _lane_id(c, h)
    plate = "测影·29005"
    bl = "BL-29-影"
    c.post(
        "/api/bl", headers=h,
        json={"bl_code": bl, "cargo_desc": "钢材", "declared_gross_t": 30.0,
              "vessel_voyage": "试航/影"},
    )
    old_id = _craft_ticket(lane_id, code="WT-影-001", plate=plate, bl_ref=bl,
                           gross=30.0, generation=1, status="已裁定")
    # 影子新代：独立正式态但旧票仍是可计正式——此处用「在途未晋升」状态模拟
    _craft_ticket(lane_id, code="WT-影-002", plate=plate, bl_ref=bl,
                  gross=31.0, generation=2, status="旁路挂起")

    fate = c.get(f"/api/lineage/fate/{plate}", headers=h).json()
    assert fate["chain_ok"] is False  # 影子未晋升即偏航，须先修
    assert fate["formal_count"] == 2

    recon = c.get(f"/api/reconcile/{bl}", headers=h).json()
    # 双正式两票都不并入合计，且显式列双正式
    assert recon["ticket_sum_t"] == 0
    assert recon["balanced"] is False
    assert {d["vehicle_plate"] for d in recon["double_formal"]} == {plate}
    assert old_id is not None


def test_void_ticket_cannot_be_released_sealed_or_overload_closed_to_revive():
    """旧票作废后不得经放行/封闸/挂起闭环复活为正式（旁门封堵）。"""
    c = TestClient(app)
    h = _auth(c)
    lane_id = _lane_id(c, h)
    plate = "测门·29006"
    old = _weigh(
        c, h, lane_id=lane_id, plate=plate, bl_ref="BL-2026-0101",
        code="WT-门-001", axles=_axles(9.0, 10.0),
    ).json()
    # 先给旧票一条开放超重挂起，模拟超重再磅情形
    c.post("/api/overloads/open", headers=h,
           json={"ticket_id": old["id"], "side_lane_note": "重开"})
    _weigh(
        c, h, lane_id=lane_id, plate=plate, bl_ref="BL-2026-0101",
        code="WT-门-002", axles=_axles(9.0, 9.0),
    )
    assert _ticket_by_code("WT-门-001")["status"] == "作废"

    # 旧票不得放行
    rel = c.post("/api/gate/release", headers=h, json={"ticket_id": old["id"]})
    assert rel.status_code == 409
    # 旧票不得封闸
    seal = c.post("/api/seals", headers=h, json={"ticket_id": old["id"]})
    assert seal.status_code == 409
    # 旧票不得再挂起
    op = c.post("/api/overloads/open", headers=h, json={"ticket_id": old["id"]})
    assert op.status_code == 409

    # 旧票挂起即便走人工闭环，也不得复活为正式
    with connect() as conn:
        hold = conn.execute(
            "SELECT id FROM overload_holds WHERE ticket_id=? ORDER BY id DESC LIMIT 1",
            (old["id"],),
        ).fetchone()
    if hold:
        c.post("/api/overloads/close", headers=h,
               json={"hold_id": hold["id"], "note": "旁路人工"})
    assert _ticket_by_code("WT-门-001")["status"] == "作废"

    fate = c.get(f"/api/lineage/fate/{plate}", headers=h).json()
    assert fate["formal_count"] == 1
    assert fate["current_ticket_code"] == "WT-门-002"

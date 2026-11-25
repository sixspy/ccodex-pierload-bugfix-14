"""同车升代命运：正式票唯一、旧票作废、血缘接续、当班锁死。

口径（BUGFIX-29）：
- 正式票：status 不为「作废」的过磅票；同车任一时刻只允许一张。
- 升代：同车再磅必须在同一事务内作废旧正式票、插入新代正式票，
  并写一条「二次升代」血缘边；旧票 superseded_by 指向新票。
- 当班锁死：正式票已进入「已封闸/已放行」后，命运条锁定，再磅拒写。
- 偏航：同车多正式 / 旧票未废 / 升代血缘缺失，一律拒写新业务并上报。
"""
from __future__ import annotations

VOID_STATUS = "作废"
LOCKED_STATUSES = ("已封闸", "已放行")
REWEIGH_EDGE = "二次升代"


def plate_tickets(conn, vehicle_plate: str) -> list[dict]:
    rows = conn.execute(
        """SELECT * FROM weigh_tickets WHERE vehicle_plate=?
           ORDER BY generation, id""",
        (vehicle_plate,),
    ).fetchall()
    return [dict(r) for r in rows]


def formal_tickets(conn, vehicle_plate: str) -> list[dict]:
    return [t for t in plate_tickets(conn, vehicle_plate) if t["status"] != VOID_STATUS]


def _reweigh_edges(conn, vehicle_plate: str) -> list[dict]:
    rows = conn.execute(
        """SELECT e.* FROM axle_lineage e
           JOIN weigh_tickets a ON a.id=e.from_ticket_id
           WHERE a.vehicle_plate=? AND e.edge_type=?""",
        (vehicle_plate, REWEIGH_EDGE),
    ).fetchall()
    return [dict(r) for r in rows]


def ticket_chain(conn, vehicle_plate: str) -> dict:
    """计算单车命运条：正式票集合、接续链、锁死态与偏航项。"""
    tickets = plate_tickets(conn, vehicle_plate)
    formals = [t for t in tickets if t["status"] != VOID_STATUS]
    voided = [t for t in tickets if t["status"] == VOID_STATUS]
    edges = _reweigh_edges(conn, vehicle_plate)
    edge_pairs = {
        (int(e["from_ticket_id"]), int(e["to_ticket_id"])) for e in edges
        if e["to_ticket_id"] is not None
    }
    issues: list[str] = []

    if len(formals) > 1:
        issues.append(f"同车双正式（{len(formals)} 张）")

    by_id = {int(t["id"]): t for t in tickets}
    max_gen = max((int(t["generation"]) for t in tickets), default=0)
    for old in voided:
        target = old.get("superseded_by")
        if not target or int(target) not in by_id:
            issues.append(f"作废票 {old['ticket_code']} 未指向新代")
            continue
        new = by_id[int(target)]
        if int(new["generation"]) <= int(old["generation"]):
            issues.append(f"升代序号未递增：{old['ticket_code']}→{new['ticket_code']}")
        if (int(old["id"]), int(new["id"])) not in edge_pairs:
            issues.append(f"升代血缘缺失：{old['ticket_code']}→{new['ticket_code']}")
    for formal in formals:
        if voided and int(formal["generation"]) <= max(
            int(v["generation"]) for v in voided
        ):
            issues.append(f"正式票非最新代：{formal['ticket_code']}")

    current = max(formals, key=lambda t: int(t["generation"])) if formals else None
    # 未过磅的新车（0 张正式）是合法起点；多于一张正式即偏航
    chain_ok = len(formals) <= 1 and not issues
    return {
        "vehicle_plate": vehicle_plate,
        "ticket_codes": [t["ticket_code"] for t in tickets],
        "formal": formals,
        "formal_count": len(formals),
        "voided_ticket_codes": [t["ticket_code"] for t in voided],
        "current_ticket": current,
        "current_ticket_code": current["ticket_code"] if current else None,
        "current_generation": int(current["generation"]) if current else None,
        "max_generation": max_gen,
        # 命运条定档：唯一正式 + 链路闭合，当班不再接受偏航写
        "locked": chain_ok,
        # 当班收车：正式票已到终态，任何再磅一律拒写
        "shift_closed": bool(current and current["status"] in LOCKED_STATUSES),
        "chain_ok": chain_ok,
        "issues": issues,
    }


def all_fates(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT DISTINCT vehicle_plate FROM weigh_tickets ORDER BY vehicle_plate"
    ).fetchall()
    return [ticket_chain(conn, r["vehicle_plate"]) for r in rows]


def fate_bar(conn, vehicle_plate: str) -> dict:
    """命运条视图：给五页共用的同一口径。"""
    chain = ticket_chain(conn, vehicle_plate)
    current = chain["current_ticket"]
    lane_code = None
    if current:
        lane = conn.execute(
            "SELECT lane_code FROM weigh_lanes WHERE id=?", (current["lane_id"],)
        ).fetchone()
        lane_code = lane["lane_code"] if lane else None
    return {
        "vehicle_plate": chain["vehicle_plate"],
        "formal_count": chain["formal_count"],
        "current_ticket_code": chain["current_ticket_code"],
        "current_generation": chain["current_generation"],
        "max_generation": chain["max_generation"],
        "current_status": current["status"] if current else None,
        "lane_code": lane_code,
        "voided_ticket_codes": chain["voided_ticket_codes"],
        "locked": chain["locked"],
        "shift_closed": chain["shift_closed"],
        "chain_ok": chain["chain_ok"],
        "issues": chain["issues"],
    }

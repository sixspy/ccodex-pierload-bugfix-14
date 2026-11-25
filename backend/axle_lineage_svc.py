"""轴重血缘边。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from fate import all_fates, fate_bar, ticket_chain
from models import LineageIn

router = APIRouter(tags=["lineage"])


@router.get("/api/lineage/fates")
def list_fates(authorization: AuthHeader = None):
    """同车升代命运条总表（五页同源口径）。"""
    require_user(authorization)
    with connect() as conn:
        return {"items": all_fates(conn)}


@router.get("/api/lineage/fate/{vehicle_plate}")
def get_fate(vehicle_plate: str, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        ticket = conn.execute(
            "SELECT id FROM weigh_tickets WHERE vehicle_plate=? LIMIT 1",
            (vehicle_plate,),
        ).fetchone()
        if not ticket:
            raise HTTPException(404, "该车无过磅记录")
        return fate_bar(conn, vehicle_plate)


@router.get("/api/lineage")
def list_lineage(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT e.*, a.ticket_code from_code, b.ticket_code to_code
               FROM axle_lineage e
               JOIN weigh_tickets a ON a.id=e.from_ticket_id
               LEFT JOIN weigh_tickets b ON b.id=e.to_ticket_id
               ORDER BY e.id DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/lineage/ticket/{ticket_id}")
def lineage_for_ticket(ticket_id: int, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        ticket = conn.execute(
            "SELECT id, vehicle_plate FROM weigh_tickets WHERE id=?", (ticket_id,)
        ).fetchone()
        if not ticket:
            raise HTTPException(404, "票不存在")
        out_edges = conn.execute(
            """SELECT e.*, b.ticket_code to_code FROM axle_lineage e
               LEFT JOIN weigh_tickets b ON b.id=e.to_ticket_id
               WHERE e.from_ticket_id=?""",
            (ticket_id,),
        ).fetchall()
        in_edges = conn.execute(
            """SELECT e.*, a.ticket_code from_code FROM axle_lineage e
               JOIN weigh_tickets a ON a.id=e.from_ticket_id
               WHERE e.to_ticket_id=?""",
            (ticket_id,),
        ).fetchall()
        # 血缘链完整性由命运条统一裁定：双正式/断链一律报 false
        chain = ticket_chain(conn, ticket["vehicle_plate"])
        return {
            "outbound": [dict(x) for x in out_edges],
            "inbound": [dict(x) for x in in_edges],
            "chain_ok": chain["chain_ok"],
            "issues": chain["issues"],
            "fate": fate_bar(conn, ticket["vehicle_plate"]),
        }


@router.post("/api/lineage")
def add_lineage(body: LineageIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    if body.edge_type == "二次升代":
        # 升代边只能由 /api/tickets 在同一事务内生；手填即旁门
        raise HTTPException(409, "二次升代边须由同车再磅事务自动落，不得手登记")
    with connect() as conn:
        fr = conn.execute(
            "SELECT id, ticket_code FROM weigh_tickets WHERE id=?",
            (body.from_ticket_id,),
        ).fetchone()
        if not fr:
            raise HTTPException(404, "起点票不存在")
        if body.to_ticket_id:
            to = conn.execute(
                "SELECT id FROM weigh_tickets WHERE id=?", (body.to_ticket_id,)
            ).fetchone()
            if not to:
                raise HTTPException(404, "终点票不存在")
        now = now_iso()
        cur = conn.execute(
            """INSERT INTO axle_lineage(from_ticket_id,to_ticket_id,edge_type,detail,created_at)
               VALUES (?,?,?,?,?)""",
            (
                body.from_ticket_id,
                body.to_ticket_id,
                body.edge_type,
                body.detail,
                now,
            ),
        )
        write_audit(
            conn,
            user,
            "lineage_edge",
            fr["ticket_code"],
            {"edge_id": cur.lastrowid, "edge_type": body.edge_type},
        )
        conn.commit()
        return {"id": cur.lastrowid}
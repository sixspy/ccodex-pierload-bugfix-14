"""提单册与过磅票对账证明。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user
from validators import validate_bl_match

router = APIRouter(tags=["reconcile"])


@router.get("/api/reconcile")
def reconcile_all(authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        rows = conn.execute(
            """SELECT bl_code, declared_gross_t FROM bl_manifests ORDER BY bl_code"""
        ).fetchall()
        items = []
        for bl in rows:
            items.append(_reconcile_bl(conn, bl["bl_code"]))
        return {"items": items}


@router.get("/api/reconcile/{bl_code}")
def reconcile_one(bl_code: str, authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        bl = conn.execute(
            "SELECT * FROM bl_manifests WHERE bl_code=?", (bl_code,)
        ).fetchone()
        if not bl:
            raise HTTPException(404, "提单不存在")
        return _reconcile_bl(conn, bl_code)


def _reconcile_bl(conn, bl_code: str) -> dict:
    bl = conn.execute(
        "SELECT * FROM bl_manifests WHERE bl_code=?", (bl_code,)
    ).fetchone()
    all_rows = conn.execute(
        """SELECT id, ticket_code, gross_t, status, generation, vehicle_plate,
                  voided_at, superseded_by
           FROM weigh_tickets WHERE bl_ref=? ORDER BY id""",
        (bl_code,),
    ).fetchall()
    tickets = [r for r in all_rows if r["status"] != "作废"]
    voided = [r for r in all_rows if r["status"] == "作废"]

    # 同车双正式：同提单内同车牌多于一张非作废票即偏航，单列不并入合计
    plates: dict[str, list] = {}
    for t in tickets:
        plates.setdefault(t["vehicle_plate"], []).append(t)
    double_formal = [
        {
            "vehicle_plate": plate,
            "ticket_codes": [x["ticket_code"] for x in group],
        }
        for plate, group in plates.items()
        if len(group) > 1
    ]
    counted = [t for t in tickets if len(plates[t["vehicle_plate"]]) == 1]

    if not tickets:
        return {
            "bl_code": bl_code,
            "declared_gross_t": bl["declared_gross_t"],
            "ticket_sum_t": 0,
            "balanced": False,
            "reason": "无过磅票",
            "tickets": [],
            "voided_tickets": [dict(t) for t in voided],
            "double_formal": double_formal,
            "seals": [],
        }
    ticket_sum = round(sum(float(t["gross_t"]) for t in counted), 3)
    declared = float(bl["declared_gross_t"])
    matched = validate_bl_match(declared, ticket_sum, tolerance=0.1) and not double_formal
    seal_rows = conn.execute(
        """SELECT s.seal_ref, s.ticket_generation, t.ticket_code, t.generation
           FROM gate_seals s JOIN weigh_tickets t ON t.id=s.ticket_id
           WHERE t.bl_ref=? AND t.status!='作废'""",
        (bl_code,),
    ).fetchall()
    stale_seals = [
        dict(s) for s in seal_rows if int(s["ticket_generation"]) != int(s["generation"])
    ]
    proof_ok = matched and len(seal_rows) >= 1 and not stale_seals
    return {
        "bl_code": bl_code,
        "declared_gross_t": declared,
        "ticket_sum_t": ticket_sum,
        "balanced": matched,
        "proof_ready": proof_ok,
        "seal_count": len(seal_rows),
        "tickets": [dict(t) for t in counted],
        "voided_tickets": [dict(t) for t in voided],
        "double_formal": double_formal,
        "stale_seals": stale_seals,
        "seals": [dict(s) for s in seal_rows],
    }


@router.get("/api/proof/ticket/{ticket_code}")
def proof_ticket(ticket_code: str, authorization: AuthHeader = None):
    require_user(authorization)
    from db import connect

    with connect() as conn:
        ticket = conn.execute(
            "SELECT * FROM weigh_tickets WHERE ticket_code=?", (ticket_code,)
        ).fetchone()
        if not ticket:
            raise HTTPException(404, "票不存在")
        bl = conn.execute(
            "SELECT * FROM bl_manifests WHERE bl_code=?", (ticket["bl_ref"],)
        ).fetchone()
        seal = conn.execute(
            """SELECT * FROM gate_seals WHERE ticket_id=? ORDER BY id DESC LIMIT 1""",
            (ticket["id"],),
        ).fetchone()
        release = conn.execute(
            """SELECT * FROM gate_releases WHERE ticket_id=? AND status='已放行'""",
            (ticket["id"],),
        ).fetchone()
        overload_closed = not conn.execute(
            """SELECT id FROM overload_holds WHERE ticket_id=? AND status='开放'""",
            (ticket["id"],),
        ).fetchone()
        # 命运条：作废票不得出证明；同车偏航一票否决
        from fate import fate_bar

        fate = fate_bar(conn, ticket["vehicle_plate"])
        manifest_match = False
        if seal and bl:
            manifest_match = validate_bl_match(
                float(bl["declared_gross_t"]), float(ticket["gross_t"])
            )
        return {
            "ticket_code": ticket_code,
            "bl_ref": ticket["bl_ref"],
            "gross_t": ticket["gross_t"],
            "generation": ticket["generation"],
            "status": ticket["status"],
            "voided": ticket["status"] == "作废",
            "manifest_matches_bl": manifest_match,
            "has_seal": seal is not None,
            "seal_generation": seal["ticket_generation"] if seal else None,
            "released": release is not None,
            "overload_closed": overload_closed,
            "fate": fate,
            "coherent": bool(
                ticket["status"] != "作废"
                and fate["chain_ok"]
                and manifest_match
                and overload_closed
                and (seal or release)
            ),
        }
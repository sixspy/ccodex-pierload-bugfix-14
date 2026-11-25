"""码头锁与争用登记（写入路径嵌入）。"""
from __future__ import annotations

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit

router = APIRouter(tags=["locks"])


class LockIn(BaseModel):
    lock_key: str
    action: str = "acquire"


def try_acquire(conn, lock_key: str, holder: str) -> bool:
    now = now_iso()
    row = conn.execute(
        "SELECT holder FROM pier_locks WHERE lock_key=?", (lock_key,)
    ).fetchone()
    if row is None:
        try:
            conn.execute(
                "INSERT INTO pier_locks(lock_key,holder,acquired_at) VALUES (?,?,?)",
                (lock_key, holder, now),
            )
        except Exception:
            # 两个会话同时读到无锁：后到的插入撞主键，按争用处理
            conn.rollback()
        else:
            # 锁簿记独立提交：业务回滚不得夹带锁残留
            conn.commit()
            return True
        row = conn.execute(
            "SELECT holder FROM pier_locks WHERE lock_key=?", (lock_key,)
        ).fetchone()
        if row is not None and row["holder"] == holder:
            return True
    if row is not None and row["holder"] == holder:
        return True
    conn.execute(
        """INSERT INTO contention_log(lock_key,actor,action,detail,created_at)
           VALUES (?,?,?,?,?)""",
        (lock_key, holder, "争用", f"持有者={row['holder'] if row else '?'}", now),
    )
    # 争用痕须落库：业务被拒后回滚不能抹掉后到记录
    conn.commit()
    return False


def release(conn, lock_key: str, holder: str) -> None:
    # 先丢弃未提交的业务写入，再单独提交解锁；避免失败路径把半截写落库
    conn.rollback()
    conn.execute(
        "DELETE FROM pier_locks WHERE lock_key=? AND holder=?",
        (lock_key, holder),
    )
    conn.commit()


def require_lock(conn, lock_key: str, holder: str) -> None:
    if not try_acquire(conn, lock_key, holder):
        raise HTTPException(409, "争用：后到只记争用，不写业务")


@contextmanager
def guarded(conn, lock_keys: list[str], holder: str):
    """按序抢锁；任一步失败即回滚业务并释放已抢到的锁。

    调用点须把 require_lock 放在任何业务写入之前——抢锁即提交。
    """
    acquired: list[str] = []
    try:
        for key in lock_keys:
            require_lock(conn, key, holder)
            acquired.append(key)
        yield
    except BaseException:
        conn.rollback()
        raise
    finally:
        for key in reversed(acquired):
            release(conn, key, holder)


@router.get("/api/locks")
def list_locks(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM pier_locks ORDER BY acquired_at DESC"
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/contention")
def list_contention(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM contention_log ORDER BY id DESC LIMIT 200"
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/locks/acquire")
def acquire_lock(body: LockIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        ok = try_acquire(conn, body.lock_key, user)
        write_audit(conn, user, "lock_acquire", body.lock_key, {"ok": ok})
        conn.commit()
        if not ok:
            raise HTTPException(409, "争用：未能获得锁")
        return {"ok": True, "lock_key": body.lock_key, "holder": user}


@router.post("/api/locks/release")
def release_lock(body: LockIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    with connect() as conn:
        release(conn, body.lock_key, user)
        write_audit(conn, user, "lock_release", body.lock_key, {})
        conn.commit()
        return {"ok": True}
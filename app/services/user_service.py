from datetime import datetime
from datetime import timezone

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Broadcast
from app.database.models import BroadcastRecipient
from app.database.models import User


async def register_or_update(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    user = await session.scalar(select(User).where(User.user_id == user_id))
    if user is None:
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        session.add(user)
    else:
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_blocked = False
        user.updated_at = datetime.now(timezone.utc)
    await session.commit()


async def get_all_user_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(
        select(User.user_id).where(User.is_blocked == False)
    )
    return list(result)


async def count_users(session: AsyncSession) -> int:
    count = await session.scalar(select(func.count(User.id)))
    return count or 0


async def mark_blocked(session: AsyncSession, user_id: int) -> None:
    user = await session.scalar(select(User).where(User.user_id == user_id))
    if user is not None:
        user.is_blocked = True
        await session.commit()


async def create_broadcast(
    session: AsyncSession,
    admin_user_id: int,
    from_chat_id: int,
    from_message_id: int,
    user_ids: list[int],
) -> int:
    broadcast = Broadcast(
        admin_user_id=admin_user_id,
        from_chat_id=from_chat_id,
        from_message_id=from_message_id,
        total_count=len(user_ids),
        status="running",
    )
    session.add(broadcast)
    await session.flush()

    recipients = [
        BroadcastRecipient(broadcast_id=broadcast.id, user_id=uid)
        for uid in user_ids
    ]
    session.add_all(recipients)
    await session.commit()
    return broadcast.id


async def get_pending_recipients_batch(
    session: AsyncSession,
    broadcast_id: int,
    limit: int = 50,
) -> list[BroadcastRecipient]:
    result = await session.scalars(
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == broadcast_id,
            BroadcastRecipient.status == "pending",
        )
        .limit(limit)
    )
    return list(result)


async def flush_recipient_statuses(
    session: AsyncSession,
    broadcast_id: int,
    updates: list[tuple[int, str]],
) -> None:
    for user_id, status in updates:
        await session.execute(
            select(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.user_id == user_id,
            )
        )
        r = await session.scalar(
            select(BroadcastRecipient)
            .where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.user_id == user_id,
            )
        )
        if r:
            r.status = status
    await session.commit()


async def get_broadcast(session: AsyncSession, broadcast_id: int) -> Broadcast | None:
    return await session.get(Broadcast, broadcast_id)


async def cancel_broadcast(session: AsyncSession, broadcast_id: int) -> None:
    b = await session.get(Broadcast, broadcast_id)
    if b and b.status == "running":
        b.status = "cancelled"
        await session.commit()


async def get_running_broadcasts(session: AsyncSession) -> list[Broadcast]:
    result = await session.scalars(
        select(Broadcast).where(Broadcast.status == "running")
    )
    return list(result)


async def complete_broadcast(
    session: AsyncSession,
    broadcast_id: int,
    sent: int,
    blocked: int,
    failed: int,
) -> None:
    b = await session.get(Broadcast, broadcast_id)
    if b:
        b.sent_count = sent
        b.blocked_count = blocked
        b.failed_count = failed
        b.status = "completed"
        await session.commit()


async def delete_old_broadcasts(session: AsyncSession) -> int:
    result = await session.scalars(
        select(Broadcast).where(
            Broadcast.status.in_(["completed", "cancelled"])
        )
    )
    broadcasts = list(result)
    for b in broadcasts:
        await session.delete(b)
    await session.commit()
    return len(broadcasts)


async def set_broadcast_progress_message(
    session: AsyncSession,
    broadcast_id: int,
    chat_id: int,
    message_id: int,
) -> None:
    b = await session.get(Broadcast, broadcast_id)
    if b:
        b.progress_chat_id = chat_id
        b.progress_message_id = message_id
        await session.commit()

"""XP, levels, streaks and badges."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_badge import UserBadge
from app.models.user_stats import UserStats

XP_EVENTS = {
    "session_started": 10,
    "message_sent": 2,
    "session_completed": 25,
    "checkpoint_passed": 8,
    "quiz_completed": 30,
    "perfect_quiz": 75,
    "source_processed": 50,
    "daily_streak": 15,
    "weekly_streak": 100,
}

BADGE_DEFINITIONS = {
    "first_lesson": {"name": "First Step", "icon": "\U0001F393", "xp": 0,
                     "cond": lambda s: s.sessions_completed >= 1, "description": "Complete your first session"},
    "curious_mind": {"name": "Curious Mind", "icon": "\U0001F9E0", "xp": 50,
                     "cond": lambda s: s.sessions_completed >= 10, "description": "Complete 10 sessions"},
    "quiz_ace": {"name": "Quiz Ace", "icon": "⭐", "xp": 75,
                 "cond": lambda s: s.perfect_quizzes >= 3, "description": "3 perfect quizzes"},
    "week_warrior": {"name": "Week Warrior", "icon": "\U0001F525", "xp": 100,
                     "cond": lambda s: s.streak_days >= 7, "description": "7-day streak"},
    "month_master": {"name": "Month Master", "icon": "\U0001F3C6", "xp": 500,
                     "cond": lambda s: s.streak_days >= 30, "description": "30-day streak"},
    "deep_diver": {"name": "Deep Diver", "icon": "\U0001F93F", "xp": 200,
                   "cond": lambda s: s.sessions_completed >= 50, "description": "50 sessions"},
    "knowledge_base": {"name": "Knowledge Base", "icon": "\U0001F4DA", "xp": 300,
                       "cond": lambda s: s.sources_processed >= 10, "description": "Process 10 sources"},
}


async def _get_stats(db: AsyncSession, user_id) -> UserStats:
    stats = (
        await db.execute(select(UserStats).where(UserStats.user_id == user_id))
    ).scalar_one_or_none()
    if not stats:
        stats = UserStats(user_id=user_id)
        db.add(stats)
        await db.flush()
    return stats


async def award_xp(db: AsyncSession, user_id, event_type: str, multiplier: float = 1.0) -> dict:
    stats = await _get_stats(db, user_id)
    xp = int(XP_EVENTS.get(event_type, 0) * multiplier)

    old_level = stats.level
    stats.xp_total += xp

    # Counters.
    if event_type == "session_completed":
        stats.sessions_completed += 1
    elif event_type == "quiz_completed":
        stats.quizzes_completed += 1
    elif event_type == "perfect_quiz":
        stats.perfect_quizzes += 1
    elif event_type == "source_processed":
        stats.sources_processed += 1

    # Streak.
    today = date.today()
    if stats.last_session_date != today:
        if stats.last_session_date == today - timedelta(days=1):
            stats.streak_days += 1
        else:
            stats.streak_days = 1
        stats.last_session_date = today
        stats.longest_streak = max(stats.longest_streak, stats.streak_days)

    # Level up (every 1000 XP).
    stats.level = stats.xp_total // 1000 + 1
    level_up = stats.level > old_level

    # Badges.
    earned = {
        b.badge_id
        for b in (
            await db.execute(select(UserBadge).where(UserBadge.user_id == user_id))
        ).scalars().all()
    }
    new_badges = []
    for badge_id, badge in BADGE_DEFINITIONS.items():
        if badge_id not in earned and badge["cond"](stats):
            db.add(UserBadge(user_id=user_id, badge_id=badge_id))
            stats.xp_total += badge["xp"]
            new_badges.append(
                {"id": badge_id, "name": badge["name"], "icon": badge["icon"],
                 "xp": badge["xp"], "description": badge["description"]}
            )
    await db.flush()

    return {
        "xp_earned": xp,
        "new_total": stats.xp_total,
        "old_level": old_level,
        "new_level": stats.level,
        "level_up": level_up,
        "new_badges": new_badges,
        "streak": stats.streak_days,
    }

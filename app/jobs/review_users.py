from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app import logger, scheduler, xray
from app.db import (GetDB, get_notification_reminder, get_users,
                    start_user_expire, update_user_status, reset_user_by_next)
from app.db.models import User
from app.models.user import ReminderType, UserResponse, UserStatus
from app.utils import report
from app.utils.helpers import (calculate_expiration_days,
                               calculate_usage_percent)
from config import (JOB_REVIEW_USERS_INTERVAL, NOTIFY_DAYS_LEFT,
                    NOTIFY_REACHED_USAGE_PERCENT, WEBHOOK_ADDRESS)

if TYPE_CHECKING:
    pass


def add_notification_reminders(db: Session, user: "User", now: datetime = datetime.utcnow()) -> None:
    if user.data_limit:
        usage_percent = calculate_usage_percent(user.used_traffic, user.data_limit)

        for percent in sorted(NOTIFY_REACHED_USAGE_PERCENT, reverse=True):
            if usage_percent >= percent:
                if not get_notification_reminder(db, user.id, ReminderType.data_usage, threshold=percent):
                    report.data_usage_percent_reached(
                        db, usage_percent, UserResponse.model_validate(user),
                        user.id, user.expire, threshold=percent
                    )
                break

    if user.expire:
        expire_days = calculate_expiration_days(user.expire)

        for days_left in sorted(NOTIFY_DAYS_LEFT):
            if expire_days <= days_left:
                if not get_notification_reminder(db, user.id, ReminderType.expiration_date, threshold=days_left):
                    report.expire_days_reached(
                        db, expire_days, UserResponse.model_validate(user),
                        user.id, user.expire, threshold=days_left
                    )
                break


def reset_user_by_next_report(db: Session, user: "User"):
    user = reset_user_by_next(db, user)

    xray.operations.update_user(user)

    report.user_data_reset_by_next(user=UserResponse.model_validate(user), user_admin=user.admin)


def review():
    now = datetime.utcnow()
    now_ts = now.timestamp()
    with GetDB() as db:

        # --- Active users needing status change ---
        # Only fetch users that are actually limited or expired instead of all active users.
        # With no data limits configured, this reduces to only time-expired users.
        expiry_or_limit = or_(
            and_(User.data_limit.isnot(None), User.used_traffic >= User.data_limit),
            and_(User.expire.isnot(None), User.expire <= now_ts),
        )
        action_users = (
            db.query(User)
            .options(joinedload(User.admin), joinedload(User.next_plan))
            .filter(User.status == UserStatus.active, expiry_or_limit)
            .all()
        )

        for user in action_users:
            limited = user.data_limit and user.used_traffic >= user.data_limit
            expired = user.expire and user.expire <= now_ts

            if user.next_plan is not None:
                if user.next_plan.fire_on_either:
                    reset_user_by_next_report(db, user)
                    continue

                elif limited and expired:
                    reset_user_by_next_report(db, user)
                    continue

            if limited:
                status = UserStatus.limited
            elif expired:
                status = UserStatus.expired
            else:
                continue

            xray.operations.remove_user(user)
            update_user_status(db, user, status)

            report.status_change(username=user.username, status=status,
                                 user=UserResponse.model_validate(user), user_admin=user.admin)

            logger.info(f"User \"{user.username}\" status changed to {status}")

        # --- Active users approaching notification thresholds ---
        # Only run if webhooks are configured, and only fetch users actually near a threshold.
        if WEBHOOK_ADDRESS and (NOTIFY_REACHED_USAGE_PERCENT or NOTIFY_DAYS_LEFT):
            notification_filters = []

            if NOTIFY_REACHED_USAGE_PERCENT:
                min_pct = min(NOTIFY_REACHED_USAGE_PERCENT) / 100.0
                notification_filters.append(
                    and_(
                        User.data_limit.isnot(None),
                        User.used_traffic >= User.data_limit * min_pct,
                        User.used_traffic < User.data_limit,
                    )
                )

            if NOTIFY_DAYS_LEFT:
                max_days = max(NOTIFY_DAYS_LEFT)
                cutoff_ts = int((now + timedelta(days=max_days)).timestamp())
                notification_filters.append(
                    and_(
                        User.expire.isnot(None),
                        User.expire > now_ts,
                        User.expire <= cutoff_ts,
                    )
                )

            notification_users = (
                db.query(User)
                .options(joinedload(User.admin))
                .filter(User.status == UserStatus.active, or_(*notification_filters))
                .all()
            )

            for user in notification_users:
                add_notification_reminders(db, user, now)

        # --- On-hold users ---
        for user in get_users(db, status=UserStatus.on_hold):

            if user.edit_at:
                base_time = datetime.timestamp(user.edit_at)
            else:
                base_time = datetime.timestamp(user.created_at)

            # Check if the user connected after or at 'base_time'
            if user.online_at and base_time <= datetime.timestamp(user.online_at):
                status = UserStatus.active

            elif user.on_hold_timeout and (datetime.timestamp(user.on_hold_timeout) <= (now_ts)):
                # If the user didn't connect within the timeout period, change status to "Active"
                status = UserStatus.active

            else:
                continue

            update_user_status(db, user, status)
            start_user_expire(db, user)

            report.status_change(username=user.username, status=status,
                                 user=UserResponse.model_validate(user), user_admin=user.admin)

            logger.info(f"User \"{user.username}\" status changed to {status}")


scheduler.add_job(review, 'interval',
                  seconds=JOB_REVIEW_USERS_INTERVAL,
                  coalesce=True, max_instances=1)

"""Automation plan service with plan-first runtime compatibility."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel, AutomationPlanModel

logger = get_logger(__name__)

VALID_PLAN_TYPES = {"manual", "semi_auto", "full_auto"}
VALID_RUN_STRATEGIES = {"manual_only", "scheduled", "hybrid"}
VALID_SCHEDULE_TYPES = {"none", "daily", "weekly", "monthly"}
VALID_WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
DEFAULT_TIMEZONE = "Asia/Shanghai"


class AutomationPlanService:
    """Create, update, summarize, and mirror automation plans."""

    async def get_account(self, account_id: str, db: AsyncSession) -> AccountModel | None:
        result = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
        return result.scalar_one_or_none()

    async def get_active_plan(self, account_id: str, db: AsyncSession) -> AutomationPlanModel | None:
        result = await db.execute(
            select(AutomationPlanModel)
            .where(
                AutomationPlanModel.account_id == account_id,
                AutomationPlanModel.is_active_plan.is_(True),
            )
            .order_by(desc(AutomationPlanModel.updated_at), desc(AutomationPlanModel.id))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_effective_summary(self, account: AccountModel, db: AsyncSession) -> dict[str, Any]:
        plan = await self.get_active_plan(account.id, db)
        if plan:
            self._apply_plan_to_account(account, plan)
            return self._summary_from_plan(plan, config_source="plan")
        return self._summary_from_account(account)

    async def get_effective_summary_by_account_id(
        self, account_id: str, db: AsyncSession
    ) -> dict[str, Any] | None:
        account = await self.get_account(account_id, db)
        if not account:
            return None
        return await self.get_effective_summary(account, db)

    async def create_initial_plan(
        self,
        account: AccountModel,
        db: AsyncSession,
        payload: dict[str, Any] | None = None,
    ) -> AutomationPlanModel:
        existing = await self.get_active_plan(account.id, db)
        if existing:
            return await self.upsert_plan(account, payload or {}, db)

        values = self._normalize_payload(payload or {}, account=account, existing=None)
        plan = AutomationPlanModel(account_id=account.id, **values)
        plan.next_run_at = self._compute_next_run_from_values(values)
        plan.last_run_at = account.last_run_at
        plan.latest_status = account.last_run_status
        db.add(plan)
        await db.flush()

        self._apply_plan_to_account(account, plan)
        db.add(account)
        await db.flush()
        logger.info(
            "automation_plan_created",
            account_id=account.id,
            plan_id=plan.id,
            plan_type=plan.plan_type,
            run_strategy=plan.run_strategy,
        )
        return plan

    async def upsert_plan(
        self,
        account: AccountModel,
        payload: dict[str, Any],
        db: AsyncSession,
    ) -> AutomationPlanModel:
        existing = await self.get_active_plan(account.id, db)
        values = self._normalize_payload(payload, account=account, existing=existing)

        if existing is None:
            return await self.create_initial_plan(account, db, values)

        for key, value in values.items():
            setattr(existing, key, value)

        existing.next_run_at = self._compute_next_run_from_plan(existing)
        db.add(existing)
        await db.flush()

        self._apply_plan_to_account(account, existing)
        db.add(account)
        await db.flush()
        logger.info(
            "automation_plan_updated",
            account_id=account.id,
            plan_id=existing.id,
            plan_type=existing.plan_type,
            run_strategy=existing.run_strategy,
        )
        return existing

    async def sync_plan_from_account_legacy(
        self, account: AccountModel, db: AsyncSession
    ) -> AutomationPlanModel:
        payload = self._payload_from_account(account)
        return await self.upsert_plan(account, payload, db)

    async def mark_run_started(self, account: AccountModel, db: AsyncSession) -> dict[str, Any]:
        plan = await self.get_active_plan(account.id, db)
        now = datetime.now(timezone.utc)

        account.last_run_at = now
        account.last_run_status = "running"
        account.last_error_message = None

        if plan:
            plan.last_run_at = now
            plan.latest_status = "running"
            plan.next_run_at = self._compute_next_run_from_plan(plan)
            db.add(plan)
            self._apply_plan_to_account(account, plan)
        else:
            account.next_run_at = self._compute_next_run_from_account(account)

        db.add(account)
        await db.flush()
        return await self.get_effective_summary(account, db)

    async def mark_run_status(self, account: AccountModel, status: str, db: AsyncSession) -> None:
        plan = await self.get_active_plan(account.id, db)
        if plan:
            plan.latest_status = status
            db.add(plan)
            await db.flush()

    async def refresh_next_run(self, account: AccountModel, db: AsyncSession) -> datetime | None:
        plan = await self.get_active_plan(account.id, db)
        if plan:
            plan.next_run_at = self._compute_next_run_from_plan(plan)
            db.add(plan)
            self._apply_plan_to_account(account, plan)
        else:
            account.next_run_at = self._compute_next_run_from_account(account)

        db.add(account)
        await db.flush()
        return account.next_run_at

    def should_auto_run(self, summary: dict[str, Any], now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if not summary.get("is_enabled"):
            return False
        if summary.get("plan_type") == "manual":
            return False
        if summary.get("run_strategy") not in {"scheduled", "hybrid"}:
            return False
        next_run_at = summary.get("next_run_at")
        if not next_run_at:
            return False
        if isinstance(next_run_at, str):
            next_run_at = datetime.fromisoformat(next_run_at)
        if next_run_at.tzinfo is None:
            next_run_at = next_run_at.replace(tzinfo=timezone.utc)
        return next_run_at <= now

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        account: AccountModel,
        existing: AutomationPlanModel | None,
    ) -> dict[str, Any]:
        base = self._payload_from_plan(existing) if existing else self._payload_from_account(account)
        merged = {**base, **{key: value for key, value in payload.items() if value is not None}}

        plan_type = str(merged.get("plan_type") or "manual").strip().lower()
        if plan_type not in VALID_PLAN_TYPES:
            raise ValueError(f"invalid plan_type: {plan_type}")

        schedule_type = str(merged.get("schedule_type") or "none").strip().lower()
        if schedule_type not in VALID_SCHEDULE_TYPES:
            raise ValueError(f"invalid schedule_type: {schedule_type}")

        timezone_name = str(merged.get("timezone") or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        run_strategy = str(
            merged.get("run_strategy")
            or self._default_run_strategy(plan_type, schedule_type)
        ).strip().lower()
        if run_strategy not in VALID_RUN_STRATEGIES:
            raise ValueError(f"invalid run_strategy: {run_strategy}")

        schedule_config = self._normalize_schedule_config(
            schedule_type=schedule_type,
            raw_config=merged.get("schedule_config"),
            fallback_time=merged.get("posting_time") or account.posting_time,
        )

        return {
            "is_active_plan": bool(merged.get("is_active_plan", True)),
            "plan_type": plan_type,
            "is_enabled": bool(merged.get("is_enabled", False)),
            "run_strategy": run_strategy,
            "schedule_type": schedule_type,
            "schedule_config": schedule_config,
            "auto_publish_enabled": bool(merged.get("auto_publish_enabled", False)),
            "publish_review_required": bool(merged.get("publish_review_required", True)),
            "max_posts_per_day": merged.get("max_posts_per_day"),
            "min_interval_minutes": merged.get("min_interval_minutes"),
            "timezone": timezone_name,
            "notes": merged.get("notes"),
        }

    def _payload_from_plan(self, plan: AutomationPlanModel) -> dict[str, Any]:
        return {
            "is_active_plan": plan.is_active_plan,
            "plan_type": plan.plan_type,
            "is_enabled": plan.is_enabled,
            "run_strategy": plan.run_strategy,
            "schedule_type": plan.schedule_type,
            "schedule_config": plan.schedule_config,
            "auto_publish_enabled": plan.auto_publish_enabled,
            "publish_review_required": plan.publish_review_required,
            "max_posts_per_day": plan.max_posts_per_day,
            "min_interval_minutes": plan.min_interval_minutes,
            "timezone": plan.timezone,
            "notes": plan.notes,
        }

    def _payload_from_account(self, account: AccountModel) -> dict[str, Any]:
        schedule_type = self._schedule_type_from_frequency(account.posting_frequency)
        return {
            "plan_type": account.operation_mode or "manual",
            "is_enabled": bool(account.auto_run_enabled),
            "run_strategy": self._legacy_run_strategy(account),
            "schedule_type": schedule_type,
            "schedule_config": self._normalize_schedule_config(
                schedule_type=schedule_type,
                raw_config=self._legacy_schedule_config(account),
                fallback_time=account.posting_time,
            ),
            "auto_publish_enabled": bool(account.auto_publish_enabled),
            "publish_review_required": not bool(account.auto_publish_enabled and account.operation_mode == "full_auto"),
            "max_posts_per_day": account.max_posts_per_day,
            "min_interval_minutes": account.min_interval_minutes,
            "timezone": DEFAULT_TIMEZONE,
            "notes": None,
        }

    def _summary_from_plan(self, plan: AutomationPlanModel, *, config_source: str) -> dict[str, Any]:
        return {
            "id": plan.id,
            "account_id": plan.account_id,
            "config_source": config_source,
            "plan_type": plan.plan_type,
            "is_enabled": plan.is_enabled,
            "run_strategy": plan.run_strategy,
            "schedule_type": plan.schedule_type,
            "schedule_config": plan.schedule_config,
            "schedule_summary": self._build_schedule_summary(plan.schedule_type, plan.schedule_config, plan.timezone),
            "auto_publish_enabled": plan.auto_publish_enabled,
            "publish_review_required": plan.publish_review_required,
            "max_posts_per_day": plan.max_posts_per_day,
            "min_interval_minutes": plan.min_interval_minutes,
            "timezone": plan.timezone,
            "next_run_at": plan.next_run_at,
            "last_run_at": plan.last_run_at,
            "notes": plan.notes,
            "latest_status": plan.latest_status,
            "is_active_plan": plan.is_active_plan,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }

    def _summary_from_account(self, account: AccountModel) -> dict[str, Any]:
        payload = self._payload_from_account(account)
        return {
            "id": None,
            "account_id": account.id,
            "config_source": "legacy_fallback",
            "plan_type": payload["plan_type"],
            "is_enabled": payload["is_enabled"],
            "run_strategy": payload["run_strategy"],
            "schedule_type": payload["schedule_type"],
            "schedule_config": payload["schedule_config"],
            "schedule_summary": self._build_schedule_summary(
                payload["schedule_type"], payload["schedule_config"], payload["timezone"]
            ),
            "auto_publish_enabled": payload["auto_publish_enabled"],
            "publish_review_required": payload["publish_review_required"],
            "max_posts_per_day": payload["max_posts_per_day"],
            "min_interval_minutes": payload["min_interval_minutes"],
            "timezone": payload["timezone"],
            "next_run_at": account.next_run_at,
            "last_run_at": account.last_run_at,
            "notes": None,
            "latest_status": account.last_run_status,
            "is_active_plan": True,
            "created_at": None,
            "updated_at": None,
        }

    def _apply_plan_to_account(self, account: AccountModel, plan: AutomationPlanModel) -> None:
        account.operation_mode = plan.plan_type
        account.auto_run_enabled = (
            plan.is_enabled
            and plan.plan_type != "manual"
            and plan.run_strategy in {"scheduled", "hybrid"}
        )
        account.auto_publish_enabled = plan.auto_publish_enabled
        account.posting_frequency = self._posting_frequency_from_plan(plan.schedule_type, plan.schedule_config)
        account.posting_time = self._posting_time_from_config(plan.schedule_config)
        account.max_posts_per_day = plan.max_posts_per_day
        account.min_interval_minutes = plan.min_interval_minutes
        account.next_run_at = plan.next_run_at
        if plan.last_run_at:
            account.last_run_at = plan.last_run_at

    def _schedule_type_from_frequency(self, posting_frequency: str | None) -> str:
        if posting_frequency == "daily":
            return "daily"
        if posting_frequency in {"weekly", "biweekly"}:
            return "weekly"
        if posting_frequency == "monthly":
            return "monthly"
        return "none"

    def _legacy_schedule_config(self, account: AccountModel) -> dict[str, Any] | None:
        schedule_type = self._schedule_type_from_frequency(account.posting_frequency)
        if schedule_type == "none":
            return None

        config: dict[str, Any] = {}
        if account.posting_time:
            config["time"] = account.posting_time
        if account.posting_frequency == "biweekly":
            config["interval_weeks"] = 2
        if schedule_type == "weekly":
            config.setdefault("weekday", "mon")
        if schedule_type == "monthly":
            config.setdefault("day", 1)
        return config

    def _legacy_run_strategy(self, account: AccountModel) -> str:
        if account.operation_mode == "manual":
            return "manual_only"
        if account.posting_frequency:
            return "hybrid"
        return "manual_only"

    def _default_run_strategy(self, plan_type: str, schedule_type: str) -> str:
        if plan_type == "manual" or schedule_type == "none":
            return "manual_only"
        return "hybrid"

    def _normalize_schedule_config(
        self,
        *,
        schedule_type: str,
        raw_config: dict[str, Any] | None,
        fallback_time: str | None,
    ) -> dict[str, Any] | None:
        if schedule_type == "none":
            return None

        config = dict(raw_config or {})
        normalized_time = self._normalize_time(config.get("time") or fallback_time) or "09:00"

        if schedule_type == "daily":
            return {"time": normalized_time}

        if schedule_type == "weekly":
            weekday = str(config.get("weekday") or "mon").strip().lower()
            if weekday not in VALID_WEEKDAYS:
                weekday = "mon"
            normalized = {"weekday": weekday, "time": normalized_time}
            interval_weeks = config.get("interval_weeks")
            if interval_weeks in {2, "2"}:
                normalized["interval_weeks"] = 2
            return normalized

        day = config.get("day")
        try:
            normalized_day = max(1, min(28, int(day)))
        except (TypeError, ValueError):
            normalized_day = 1
        return {"day": normalized_day, "time": normalized_time}

    def _normalize_time(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            hours, minutes = text.split(":")
            return f"{int(hours):02d}:{int(minutes):02d}"
        except (ValueError, TypeError):
            return None

    def _posting_frequency_from_plan(
        self, schedule_type: str, schedule_config: dict[str, Any] | None
    ) -> str | None:
        if schedule_type == "daily":
            return "daily"
        if schedule_type == "weekly":
            if schedule_config and schedule_config.get("interval_weeks") == 2:
                return "biweekly"
            return "weekly"
        if schedule_type == "monthly":
            return "monthly"
        return None

    def _posting_time_from_config(self, schedule_config: dict[str, Any] | None) -> str | None:
        if not schedule_config:
            return None
        return self._normalize_time(schedule_config.get("time"))

    def _build_schedule_summary(
        self,
        schedule_type: str,
        schedule_config: dict[str, Any] | None,
        timezone_name: str,
    ) -> str:
        if schedule_type == "none":
            return "Manual only"
        schedule_config = schedule_config or {}
        time_text = schedule_config.get("time") or "09:00"
        if schedule_type == "daily":
            return f"Daily at {time_text} ({timezone_name})"
        if schedule_type == "weekly":
            weekday = str(schedule_config.get("weekday") or "mon").upper()
            if schedule_config.get("interval_weeks") == 2:
                return f"Biweekly on {weekday} at {time_text} ({timezone_name})"
            return f"Weekly on {weekday} at {time_text} ({timezone_name})"
        day = schedule_config.get("day") or 1
        return f"Monthly on day {day} at {time_text} ({timezone_name})"

    def _compute_next_run_from_plan(self, plan: AutomationPlanModel) -> datetime | None:
        return self._compute_next_run_from_values(
            {
                "plan_type": plan.plan_type,
                "is_enabled": plan.is_enabled,
                "run_strategy": plan.run_strategy,
                "schedule_type": plan.schedule_type,
                "schedule_config": plan.schedule_config,
                "timezone": plan.timezone,
            }
        )

    def _compute_next_run_from_account(self, account: AccountModel) -> datetime | None:
        payload = self._payload_from_account(account)
        return self._compute_next_run_from_values(payload)

    def _compute_next_run_from_values(self, values: dict[str, Any]) -> datetime | None:
        if not values.get("is_enabled"):
            return None
        if values.get("plan_type") == "manual":
            return None
        if values.get("run_strategy") not in {"scheduled", "hybrid"}:
            return None

        schedule_type = values.get("schedule_type") or "none"
        schedule_config = values.get("schedule_config") or {}
        if schedule_type == "none":
            return None

        zone = self._resolve_timezone(values.get("timezone"))
        now_local = datetime.now(zone)
        clock = self._time_from_config(schedule_config.get("time"))

        if schedule_type == "daily":
            candidate = now_local.replace(
                hour=clock.hour,
                minute=clock.minute,
                second=0,
                microsecond=0,
            )
            if candidate <= now_local:
                candidate = candidate + timedelta(days=1)
            return candidate.astimezone(timezone.utc)

        if schedule_type == "weekly":
            target_weekday = self._weekday_index(schedule_config.get("weekday"))
            days_ahead = (target_weekday - now_local.weekday()) % 7
            candidate = now_local.replace(
                hour=clock.hour,
                minute=clock.minute,
                second=0,
                microsecond=0,
            ) + timedelta(days=days_ahead)
            if candidate <= now_local:
                interval_weeks = 2 if schedule_config.get("interval_weeks") == 2 else 1
                candidate = candidate + timedelta(days=7 * interval_weeks)
            return candidate.astimezone(timezone.utc)

        day = max(1, min(28, int(schedule_config.get("day") or 1)))
        year = now_local.year
        month = now_local.month
        if now_local.day > day or (
            now_local.day == day
            and (now_local.hour, now_local.minute) >= (clock.hour, clock.minute)
        ):
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        candidate = datetime(year, month, day, clock.hour, clock.minute, tzinfo=zone)
        return candidate.astimezone(timezone.utc)

    def _resolve_timezone(self, name: str | None):
        try:
            return ZoneInfo(name or DEFAULT_TIMEZONE)
        except Exception:
            return timezone.utc

    def _time_from_config(self, value: Any) -> time:
        normalized = self._normalize_time(value) or "09:00"
        hours, minutes = normalized.split(":")
        return time(hour=int(hours), minute=int(minutes))

    def _weekday_index(self, value: Any) -> int:
        lookup = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        return lookup.get(str(value or "mon").strip().lower(), 0)


automation_plan_service = AutomationPlanService()

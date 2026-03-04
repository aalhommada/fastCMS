"""
IP filter service — manages allow/block rules and checks incoming IPs.
Supports CIDR ranges via Python's built-in ipaddress module.
"""

import ipaddress
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ip_rule import IPRule
from app.core.logging import get_logger

logger = get_logger(__name__)


def _ip_in_cidr(ip: str, cidr: str) -> bool:
    """Check if an IP address falls within a CIDR range."""
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        addr = ipaddress.ip_address(ip)
        return addr in network
    except ValueError:
        return False


class IPFilterService:
    """Service for managing and evaluating IP rules."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_rules(
        self,
        skip: int = 0,
        limit: int = 100,
        rule_type: Optional[str] = None,
    ) -> list[IPRule]:
        stmt = select(IPRule)
        if rule_type:
            stmt = stmt.where(IPRule.rule_type == rule_type)
        stmt = stmt.offset(skip).limit(limit).order_by(IPRule.created.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_rules(self, rule_type: Optional[str] = None) -> int:
        from sqlalchemy import func
        stmt = select(func.count(IPRule.id))
        if rule_type:
            stmt = stmt.where(IPRule.rule_type == rule_type)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create_rule(
        self,
        cidr: str,
        rule_type: str,
        reason: Optional[str],
        expires_at: Optional[datetime],
        created_by: str,
    ) -> IPRule:
        # Validate CIDR/IP
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            from app.core.exceptions import BadRequestException
            raise BadRequestException(f"Invalid CIDR or IP address: '{cidr}'")

        if rule_type not in ("allow", "block"):
            from app.core.exceptions import BadRequestException
            raise BadRequestException("rule_type must be 'allow' or 'block'")

        rule = IPRule(
            cidr=cidr,
            rule_type=rule_type,
            reason=reason,
            expires_at=expires_at,
            created_by=created_by,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: str) -> None:
        from app.core.exceptions import NotFoundException
        result = await self.db.execute(select(IPRule).where(IPRule.id == rule_id))
        rule = result.scalar_one_or_none()
        if not rule:
            raise NotFoundException(f"IP rule '{rule_id}' not found")
        await self.db.delete(rule)
        await self.db.commit()

    async def is_blocked(self, ip: str) -> tuple[bool, Optional[str]]:
        """
        Check if an IP is blocked.

        Returns:
            (is_blocked, reason)
        """
        now = datetime.now(timezone.utc)
        stmt = select(IPRule).where(IPRule.rule_type == "block")
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            # Skip expired rules
            if rule.expires_at:
                expires = rule.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires <= now:
                    continue

            if _ip_in_cidr(ip, rule.cidr):
                return True, rule.reason

        return False, None

    async def is_explicitly_allowed(self, ip: str) -> bool:
        """Check if an IP is in the allowlist."""
        now = datetime.now(timezone.utc)
        stmt = select(IPRule).where(IPRule.rule_type == "allow")
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        for rule in rules:
            if rule.expires_at:
                expires = rule.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires <= now:
                    continue
            if _ip_in_cidr(ip, rule.cidr):
                return True

        return False

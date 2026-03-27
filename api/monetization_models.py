from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RefillIntervalUnit = Literal["seconds", "minutes", "hours", "days", "weeks", "months"]
LedgerEntryType = Literal[
    "referral_reward",
    "promo_redemption",
    "admin_grant",
    "chat_overage_spend",
]
ReferralEventType = Literal[
    "signup_attributed",
    "reward_granted",
]


class BalanceRecord(BaseModel):
    user: str
    tokenCredits: int = 0
    autoRefillEnabled: bool = False
    refillIntervalValue: int = 30
    refillIntervalUnit: RefillIntervalUnit = "days"
    lastRefill: datetime | None = None
    refillAmount: int = 0


class LedgerEntry(BaseModel):
    id: str
    user: str
    entryType: LedgerEntryType
    tokenCreditsDelta: int
    usdValue: float | None = None
    description: str = ""
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    createdAt: datetime
    updatedAt: datetime


class PromoCodeRecord(BaseModel):
    code: str
    tokenCreditsAwarded: int
    usdValue: float | None = None
    active: bool = True
    maxUses: int | None = None
    createdBy: str = ""
    createdAt: datetime
    updatedAt: datetime


class PromoClaimRecord(BaseModel):
    code: str
    userId: str
    tokenCreditsAwarded: int
    createdAt: datetime


class ReferralEventRecord(BaseModel):
    id: str
    referrerUserId: str
    referredUserId: str
    referralCode: str
    eventType: ReferralEventType
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    createdAt: datetime

"""Subscription billing-state machine (§1.3).

Encodes the verbatim §1.3 transition table and refuses any transition not in it
(US-020 AC-16). Callers MUST route every ``billing_state`` change through
:meth:`BillingStateMachine.transition` so an illegal write (e.g. a malformed
webhook trying ``Canceled → Grace``) raises :class:`InvalidTransitionError`
instead of silently corrupting state.

Note: same-state "transitions" (e.g. ``Active → Active``) are intentionally NOT
in the table and therefore raise. Webhook handlers guard against redundant calls
(they check the current state first) so a duplicate/again-failing event is a
no-op rather than an exception.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from app.schemas.contracts import BillingState

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.db.models.subscription import Subscription


# §1.3 Subscription Billing State Transitions (verbatim).
BILLING_STATE_TRANSITIONS: Dict[BillingState, List[BillingState]] = {
    "Active": ["Grace", "Canceled"],
    "Grace": ["Active", "Canceled"],
    "Canceled": ["Active"],
}


class InvalidTransitionError(Exception):
    """Raised when a billing-state transition is not permitted by §1.3."""

    def __init__(self, current: str, new: str) -> None:
        self.current = current
        self.new = new
        super().__init__(
            f"Illegal billing-state transition {current!r} -> {new!r} "
            f"(allowed from {current!r}: {BILLING_STATE_TRANSITIONS.get(current, [])})"
        )


class BillingStateMachine:
    """Validates and applies §1.3 billing-state transitions."""

    @staticmethod
    def can_transition(current: str, new: str) -> bool:
        """Return whether ``current → new`` is a permitted transition."""
        return new in BILLING_STATE_TRANSITIONS.get(current, [])

    @staticmethod
    def transition(subscription: "Subscription", new_state: str) -> "Subscription":
        """Apply ``new_state`` to ``subscription`` or raise.

        Raises :class:`InvalidTransitionError` if the move from the
        subscription's current ``billing_state`` to ``new_state`` is not in the
        §1.3 table. On success the subscription's ``billing_state`` is mutated in
        place and the subscription is returned for chaining.
        """
        current = subscription.billing_state
        if not BillingStateMachine.can_transition(current, new_state):
            raise InvalidTransitionError(current, new_state)
        subscription.billing_state = new_state
        return subscription


__all__ = [
    "BILLING_STATE_TRANSITIONS",
    "InvalidTransitionError",
    "BillingStateMachine",
]

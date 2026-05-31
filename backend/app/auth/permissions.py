"""Role-permission matrix and permission evaluation (§1.3).

[LOAD-BEARING] ``ROLE_PERMISSIONS`` is a verbatim mirror of the §1.3 matrix.
Imported by S2-B, S2-C, S2-D, S2-F. Do not reorder, rename, or alter values
without a spec change — every Phase 2 ownership check resolves through it.

Matrix value semantics (per action, per role):

* ``True``  — action is always permitted regardless of resource ownership
              (e.g. ``drawing_upload``, ``billing_manage``).
* ``False`` — action is never permitted for this role.
* ``"own"`` — permitted only when the resource is owned by the requesting user
              (``resource.owner_user_id == user.id``).
* ``"team"``— permitted when the resource is owned by the user OR belongs to the
              user's team (``resource.owner_team_id == user.team_id``).
"""
from __future__ import annotations

from typing import Literal, Optional

from app.schemas.contracts import UserRole

# Relationship of the requesting user to a resource, as resolved by the caller
# (dependencies.resolve_ownership). ``None`` == the user neither owns the
# resource nor shares a team with it.
Ownership = Literal["own", "team"]

# Permission value stored in the matrix for a single (role, action) pair.
PermissionValue = bool | Literal["own", "team"]


# §1.3 Role-Permission Matrix — verbatim mirror of the TypeScript constant.
# Keep the action ordering and values byte-for-byte aligned with the spec.
ROLE_PERMISSIONS: dict[UserRole, dict[str, PermissionValue]] = {
    "user": {
        "drawing_upload": True,
        "drawing_view": "own",
        "drawing_delete": "own",
        "drawing_retry": "own",
        "symbol_correct": "own",
        "export_initiate": "own",
        "team_manage": False,
        "billing_manage": True,
        "gdpr_delete_account": True,
    },
    "team_member": {
        "drawing_upload": True,
        "drawing_view": "team",
        "drawing_delete": False,
        "drawing_retry": "team",
        "symbol_correct": "team",
        "export_initiate": "team",
        "team_manage": False,
        "billing_manage": False,
        "gdpr_delete_account": True,
    },
    "team_admin": {
        "drawing_upload": True,
        "drawing_view": "team",
        "drawing_delete": "team",
        "drawing_retry": "team",
        "symbol_correct": "team",
        "export_initiate": "team",
        "team_manage": True,
        "billing_manage": True,
        "gdpr_delete_account": True,
    },
}


def check_permission(
    role: UserRole,
    action: str,
    ownership: Optional[Ownership] = None,
) -> bool:
    """Return whether ``role`` may perform ``action`` given the user's
    ``ownership`` relationship to the target resource.

    ``ownership`` is ``"own"``, ``"team"`` or ``None`` (no relationship). For
    non-resource actions (``team_manage``, ``billing_manage``,
    ``gdpr_delete_account``) the matrix value is a plain boolean and
    ``ownership`` is ignored.

    Unknown roles or actions resolve to ``False`` (deny by default) rather than
    raising, so a typo in a downstream call site fails closed.
    """
    permission = ROLE_PERMISSIONS.get(role, {}).get(action, False)

    if permission is True:
        return True
    if permission is False:
        return False
    if permission == "own":
        return ownership == "own"
    if permission == "team":
        return ownership in ("own", "team")
    return False


__all__ = ["ROLE_PERMISSIONS", "check_permission", "Ownership", "PermissionValue"]

"""Authentication & authorization primitives (S1-B).

Provides the security layer every Phase 2 API endpoint depends on:

* :mod:`app.auth.jwt_verifier` — RS256 Supabase token verification.
* :mod:`app.auth.middleware` — per-request auth resolution incl. the mandatory
  ``token_invalidated_at`` / ``deleted_at`` user-state checks.
* :mod:`app.auth.dependencies` — ``get_current_user``, ``require_role``,
  ``require_permission`` and the ``CurrentUser`` model.
* :mod:`app.auth.permissions` — the §1.3 ``ROLE_PERMISSIONS`` matrix and
  ``check_permission``.
* :mod:`app.auth.brute_force` — Redis-backed login lockout (§1.9).
* :mod:`app.auth.supabase_client` — Supabase Admin API wrapper
  (``admin_sign_out``, ``find_user_by_email``).

Submodules are imported lazily by consumers to avoid pulling the DB engine /
Redis at package-import time.
"""

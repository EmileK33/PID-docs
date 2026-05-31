// Nav — top navigation chrome.
//
// Authenticated: app name (left); Dashboard / Upload / Account / Subscription
// links; user email + role badge + sign-out (right). Active route highlighted.
// Unauthenticated: app name + Log in / Register links.
import type { ReactElement } from 'react';
import { NavLink } from 'react-router-dom';

import type { UserRole } from '../types/contracts';
import { useAuth } from '../auth/useAuth';

const linkClass = ({ isActive }: { isActive: boolean }): string =>
  isActive ? 'nav-link nav-link--active' : 'nav-link';

function userRole(metadata: unknown): UserRole {
  const role = (metadata as { role?: UserRole } | undefined)?.role;
  return role ?? 'user';
}

export function Nav(): ReactElement {
  const { user, signOut } = useAuth();

  return (
    <nav className="app-nav">
      <div className="app-nav__brand">
        <NavLink to="/dashboard">P&amp;ID Extractor</NavLink>
      </div>

      {user ? (
        <>
          <div className="app-nav__links">
            <NavLink to="/dashboard" className={linkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/upload" className={linkClass}>
              Upload
            </NavLink>
            <NavLink to="/account" className={linkClass}>
              Account
            </NavLink>
            <NavLink to="/subscription" className={linkClass}>
              Subscription
            </NavLink>
          </div>
          <div className="app-nav__user">
            <span className="app-nav__email">{user.email}</span>
            <span className="role-badge">{userRole(user.app_metadata)}</span>
            <button
              type="button"
              className="app-nav__signout"
              onClick={() => void signOut()}
            >
              Sign out
            </button>
          </div>
        </>
      ) : (
        <div className="app-nav__links">
          <NavLink to="/login" className={linkClass}>
            Log in
          </NavLink>
          <NavLink to="/register" className={linkClass}>
            Register
          </NavLink>
        </div>
      )}
    </nav>
  );
}

export default Nav;

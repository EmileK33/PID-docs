// Auth context — owns the Supabase session lifecycle for the SPA.
//
// [LOAD-BEARING] `AuthProvider` wraps the app; `AuthContext` is read via
// `useAuth`. Consumed by every authenticated S3-* page.
//
// Contract (US-002, §1.4 rule 12):
//  - Exposes { user, session, signIn, signOut, loading }.
//  - On a 401 from any authenticated API call, clears local session state and
//    redirects to /login (handler registered with the API client). No silent
//    retry.
//  - On a `token_invalidated_at` change (server-side session invalidation via
//    admin.signOut), clears local state.
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';

import { onUnauthorized } from '../api/client';
import { supabase } from './supabaseClient';

export interface AuthContextValue {
  user: User | null;
  session: Session | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  loading: boolean;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function tokenInvalidatedAt(session: Session | null): string | null {
  const meta = session?.user?.app_metadata as
    | { token_invalidated_at?: string }
    | undefined;
  return meta?.token_invalidated_at ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }): ReactElement {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const lastInvalidatedRef = useRef<string | null>(null);

  const clearAndRedirect = useCallback(() => {
    setSession(null);
    void supabase.auth.signOut();
    if (
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/login')
    ) {
      window.location.assign('/login');
    }
  }, []);

  useEffect(() => {
    let active = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (!active) return;
        setSession(data.session ?? null);
        lastInvalidatedRef.current = tokenInvalidatedAt(data.session ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (active) setLoading(false);
      });

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession ?? null);

      // Server-side session invalidation (US-002): if the invalidation marker
      // changed from a previously-seen value, force a local logout.
      const invalidated = tokenInvalidatedAt(nextSession ?? null);
      if (
        invalidated &&
        lastInvalidatedRef.current &&
        invalidated !== lastInvalidatedRef.current
      ) {
        clearAndRedirect();
      }
      if (invalidated) lastInvalidatedRef.current = invalidated;
    });

    const unregister = onUnauthorized(() => clearAndRedirect());

    return () => {
      active = false;
      data?.subscription?.unsubscribe?.();
      unregister();
    };
  }, [clearAndRedirect]);

  const signIn = useCallback(async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
    setSession(data.session ?? null);
  }, []);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setSession(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      session,
      signIn,
      signOut,
      loading,
    }),
    [session, signIn, signOut, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;

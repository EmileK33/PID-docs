// Browser storage helpers. Keys MUST match §1.11 exactly:
//  - `correction_state:{drawing_id}` — localStorage, ≤2MB cap (US-015).
//  - `graceBannerDismissed` — sessionStorage, session-scoped (US-020).
//
// localStorage cap (§1.11 / manifest): estimate UTF-16 byte size before writing
// and refuse (return false) if the write would exceed 2MB. Never silently
// truncate.

const CORRECTION_STATE_PREFIX = 'correction_state:';
const GRACE_BANNER_KEY = 'graceBannerDismissed';
const MAX_CORRECTION_BYTES = 2 * 1024 * 1024; // 2MB

function correctionKey(drawingId: string): string {
  return `${CORRECTION_STATE_PREFIX}${drawingId}`;
}

// JS strings are UTF-16: 2 bytes per code unit.
function utf16ByteSize(value: string): number {
  return value.length * 2;
}

export function getCorrectionState(drawingId: string): unknown | null {
  try {
    const raw = localStorage.getItem(correctionKey(drawingId));
    return raw === null ? null : (JSON.parse(raw) as unknown);
  } catch {
    return null;
  }
}

/**
 * Persist unsaved correction state. Returns false (does NOT throw) when the
 * serialized payload would push the key past the 2MB cap or when the write
 * otherwise fails (e.g. quota). Returns true on success.
 */
export function setCorrectionState(drawingId: string, state: unknown): boolean {
  let serialized: string;
  try {
    serialized = JSON.stringify(state);
  } catch {
    return false; // non-serializable
  }
  if (serialized === undefined) return false;
  if (utf16ByteSize(serialized) > MAX_CORRECTION_BYTES) return false;
  try {
    localStorage.setItem(correctionKey(drawingId), serialized);
    return true;
  } catch {
    return false; // quota exceeded / storage unavailable
  }
}

export function clearCorrectionState(drawingId: string): void {
  try {
    localStorage.removeItem(correctionKey(drawingId));
  } catch {
    /* ignore */
  }
}

export function isGraceBannerDismissed(): boolean {
  try {
    return sessionStorage.getItem(GRACE_BANNER_KEY) === 'true';
  } catch {
    return false;
  }
}

export function dismissGraceBanner(): void {
  try {
    sessionStorage.setItem(GRACE_BANNER_KEY, 'true');
  } catch {
    /* ignore */
  }
}

export const storage = {
  getCorrectionState,
  setCorrectionState,
  clearCorrectionState,
  isGraceBannerDismissed,
  dismissGraceBanner,
};

export default storage;

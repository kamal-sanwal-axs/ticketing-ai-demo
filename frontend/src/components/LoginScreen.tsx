import type { Region } from "@/types/api";
import type { PendingRerun } from "@/lib/session";

type Props = {
  regions: Region[];
  token: string;
  region: string;
  error: string | null;
  busy: boolean;
  pendingRerun: PendingRerun | null;
  rerunAfterLogin: boolean;
  onRerunAfterLoginChange: (v: boolean) => void;
  onTokenChange: (v: string) => void;
  onRegionChange: (v: string) => void;
  onSubmit: () => void;
};

export function LoginScreen({
  regions,
  token,
  region,
  error,
  busy,
  pendingRerun,
  rerunAfterLogin,
  onRerunAfterLoginChange,
  onTokenChange,
  onRegionChange,
  onSubmit,
}: Props) {
  return (
    <section className="card" id="screen-login">
      <h1>APEX AI Helper</h1>
      <p className="muted">
        Paste your apex-dev access token once. It stays in this browser only (session storage).
      </p>
      <label htmlFor="token">Access token</label>
      <textarea
        id="token"
        rows={4}
        placeholder="Bearer JWT from apex-dev session…"
        value={token}
        onChange={(e) => onTokenChange(e.target.value)}
      />
      <label htmlFor="region">Region</label>
      <select id="region" value={region} onChange={(e) => onRegionChange(e.target.value)}>
        {regions.map((r) => (
          <option key={r.id} value={r.id}>{r.label}</option>
        ))}
      </select>
      <button id="btn-login" type="button" onClick={onSubmit} disabled={busy}>
        Continue
      </button>
      {pendingRerun?.message ? (
        <div className="login-rerun-prompt">
          <p className="login-rerun-title">Your last question</p>
          <blockquote className="login-rerun-quote">{pendingRerun.message}</blockquote>
          <label className="login-rerun-consent">
            <input
              type="checkbox"
              checked={rerunAfterLogin}
              onChange={(e) => onRerunAfterLoginChange(e.target.checked)}
            />
            Re-run this after I sign in
          </label>
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}

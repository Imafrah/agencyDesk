import { useState } from "react";
import { api } from "./api";

const MODES = { LOGIN: "login", SIGNUP: "signup", INVITE: "invite" };

export default function Login({ onSession }) {
  const [mode, setMode] = useState(MODES.LOGIN);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [choices, setChoices] = useState(null);
  const [preAuth, setPreAuth] = useState(null);

  const [agencyName, setAgencyName] = useState("");
  const [adminName, setAdminName] = useState("");

  const [inviteToken, setInviteToken] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [invitePassword, setInvitePassword] = useState("");

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.login(email, password);
      if (res.access_token) {
        onSession({ token: res.access_token });
      } else {
        setChoices(res.choices);
        setPreAuth(res.pre_auth_token);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function pickAgency(agencyId) {
    setBusy(true);
    setError("");
    try {
      const res = await api.selectAgency(preAuth, agencyId);
      onSession({ token: res.access_token });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSignup(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.signup({ agency_name: agencyName, admin_name: adminName, email, password });
      onSession({ token: res.access_token });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptInvite(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res = await api.acceptInvite({
        token: inviteToken,
        name: inviteName || undefined,
        password: invitePassword || undefined,
      });
      onSession({ token: res.access_token });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="mark" style={{ background: "var(--accent)" }} />
          AgencyDesk
        </div>
        <div className="auth-tag">Project &amp; client workspace for agencies.</div>

        {error && <div className="error-banner">{error}</div>}

        {choices ? (
          <>
            <label>Choose which agency to sign in to</label>
            {choices.map((c) => (
              <button key={c.agency_id} className="choice-btn" onClick={() => pickAgency(c.agency_id)}>
                {c.agency_name}
                <span className="choice-role">{c.role.replace("_", " ")}</span>
              </button>
            ))}
            <button className="link-btn" style={{ color: "var(--ink)", marginTop: 8 }} onClick={() => setChoices(null)}>
              ← back
            </button>
          </>
        ) : mode === MODES.LOGIN ? (
          <form onSubmit={handleLogin}>
            <div className="field">
              <label>Email</label>
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
            </div>
            <div className="field">
              <label>Password</label>
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
            </div>
            <button className="btn btn-primary" style={{ width: "100%" }} disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <div style={{ marginTop: 16, fontSize: 12.5, color: "var(--ink-soft)" }}>
              New agency?{" "}
              <button type="button" className="link-btn" onClick={() => setMode(MODES.SIGNUP)}>
                Create one
              </button>
              {" · "}
              Have an invite?{" "}
              <button type="button" className="link-btn" onClick={() => setMode(MODES.INVITE)}>
                Accept it
              </button>
            </div>
          </form>
        ) : mode === MODES.SIGNUP ? (
          <form onSubmit={handleSignup}>
            <div className="field">
              <label>Agency name</label>
              <input value={agencyName} onChange={(e) => setAgencyName(e.target.value)} required />
            </div>
            <div className="field">
              <label>Your name</label>
              <input value={adminName} onChange={(e) => setAdminName(e.target.value)} required />
            </div>
            <div className="field">
              <label>Email</label>
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
            </div>
            <div className="field">
              <label>Password</label>
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={8} required />
            </div>
            <button className="btn btn-accent" style={{ width: "100%" }} disabled={busy}>
              {busy ? "Creating…" : "Create agency"}
            </button>
            <div style={{ marginTop: 16, fontSize: 12.5 }}>
              <button type="button" className="link-btn" onClick={() => setMode(MODES.LOGIN)}>
                ← back to sign in
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleAcceptInvite}>
            <div className="field">
              <label>Invite token</label>
              <input value={inviteToken} onChange={(e) => setInviteToken(e.target.value)} required />
            </div>
            <div className="field">
              <label>Name (new accounts only)</label>
              <input value={inviteName} onChange={(e) => setInviteName(e.target.value)} />
            </div>
            <div className="field">
              <label>Password (new accounts only)</label>
              <input value={invitePassword} onChange={(e) => setInvitePassword(e.target.value)} type="password" />
            </div>
            <button className="btn btn-accent" style={{ width: "100%" }} disabled={busy}>
              {busy ? "Joining…" : "Accept invite"}
            </button>
            <div style={{ marginTop: 16, fontSize: 12.5 }}>
              <button type="button" className="link-btn" onClick={() => setMode(MODES.LOGIN)}>
                ← back to sign in
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

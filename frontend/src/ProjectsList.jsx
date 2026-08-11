import { useEffect, useState } from "react";
import { api } from "./api";

export default function ProjectsList({ session, onOpenProject }) {
  const { token, role } = session;
  const isAdmin = role === "agency_admin";

  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [error, setError] = useState("");
  const [panel, setPanel] = useState(null); // 'client' | 'project' | 'invite' | null

  const [clientName, setClientName] = useState("");
  const [projClient, setProjClient] = useState("");
  const [projName, setProjName] = useState("");
  const [projDesc, setProjDesc] = useState("");

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("agency_member");
  const [inviteClient, setInviteClient] = useState("");
  const [invites, setInvites] = useState([]);
  const [lastInviteLink, setLastInviteLink] = useState(null);

  async function loadAll() {
    setError("");
    try {
      const p = await api.projects(token);
      setProjects(p);
      if (isAdmin) {
        const [c, inv] = await Promise.all([api.clients(token), api.invites(token)]);
        setClients(c);
        setInvites(inv);
      } else {
        setClients(await api.clients(token));
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createClient(e) {
    e.preventDefault();
    try {
      await api.createClient(token, clientName);
      setClientName("");
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function createProject(e) {
    e.preventDefault();
    try {
      await api.createProject(token, { client_id: projClient, name: projName, description: projDesc || undefined });
      setProjName("");
      setProjDesc("");
      setPanel(null);
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function sendInvite(e) {
    e.preventDefault();
    try {
      const inv = await api.createInvite(token, {
        email: inviteEmail,
        role: inviteRole,
        client_id: inviteRole === "client_user" ? inviteClient : undefined,
      });
      setLastInviteLink(inv.token);
      setInviteEmail("");
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  const clientName_ = (id) => clients.find((c) => c.id === id)?.name || "—";

  return (
    <div>
      <div className="page-head">
        <div>
          <div className="page-title">Projects</div>
          <div className="page-sub">
            {role === "client_user" ? "Your work in progress" : "Everything your agency is running"}
          </div>
        </div>
        {isAdmin && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost" onClick={() => setPanel(panel === "client" ? null : "client")}>
              + Client
            </button>
            <button className="btn btn-ghost" onClick={() => setPanel(panel === "invite" ? null : "invite")}>
              Invite people
            </button>
            <button className="btn btn-accent" onClick={() => setPanel(panel === "project" ? null : "project")}>
              + Project
            </button>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {panel === "client" && (
        <form onSubmit={createClient} className="card" style={{ marginBottom: 18 }}>
          <div className="inline-form" style={{ marginBottom: 0 }}>
            <input placeholder="Client name" value={clientName} onChange={(e) => setClientName(e.target.value)} autoFocus />
            <button className="btn btn-primary btn-sm">Add client</button>
          </div>
        </form>
      )}

      {panel === "project" && (
        <form onSubmit={createProject} className="card" style={{ marginBottom: 18 }}>
          <div className="field">
            <label>Client</label>
            <select value={projClient} onChange={(e) => setProjClient(e.target.value)} required>
              <option value="">Select a client…</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Project name</label>
            <input value={projName} onChange={(e) => setProjName(e.target.value)} required />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Description (optional)</label>
            <textarea rows={2} value={projDesc} onChange={(e) => setProjDesc(e.target.value)} />
          </div>
          <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }}>
            Create project
          </button>
        </form>
      )}

      {panel === "invite" && (
        <div className="card" style={{ marginBottom: 18 }}>
          <form onSubmit={sendInvite}>
            <div className="field">
              <label>Email</label>
              <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required />
            </div>
            <div className="field">
              <label>Role</label>
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                <option value="agency_member">Agency member</option>
                <option value="agency_admin">Agency admin</option>
                <option value="client_user">Client user</option>
              </select>
            </div>
            {inviteRole === "client_user" && (
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Client</label>
                <select value={inviteClient} onChange={(e) => setInviteClient(e.target.value)} required>
                  <option value="">Select a client…</option>
                  {clients.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button className="btn btn-primary btn-sm" style={{ marginTop: 12 }}>
              Send invite
            </button>
          </form>
          {lastInviteLink && (
            <div className="page-sub" style={{ marginTop: 12 }}>
              No email sending in this build — hand them this token to accept:
              <div style={{ fontFamily: "var(--mono)", fontSize: 12, wordBreak: "break-all", marginTop: 4 }}>
                {lastInviteLink}
              </div>
            </div>
          )}
          {invites.length > 0 && (
            <>
              <div className="section-label">Pending &amp; recent invites</div>
              {invites.map((i) => (
                <div className="file-row" key={i.id}>
                  <span>
                    {i.email} <span style={{ color: "var(--ink-soft)" }}>· {i.role.replace("_", " ")}</span>
                  </span>
                  <span className="tag" style={{ background: "#e6e9e8", color: "var(--ink-soft)" }}>
                    {i.status}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      )}

      {projects.length === 0 && <div className="empty">No projects yet.</div>}
      <div className="grid">
        {projects.map((p) => (
          <div className="project-card" key={p.id} onClick={() => onOpenProject(p)}>
            <div className="project-name">{p.name}</div>
            <div className="project-desc">{p.description || clientName_(p.client_id)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

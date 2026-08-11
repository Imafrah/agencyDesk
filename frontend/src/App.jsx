import { useEffect, useState } from "react";
import { api } from "./api";
import Login from "./Login.jsx";
import ProjectsList from "./ProjectsList.jsx";
import ProjectBoard from "./ProjectBoard.jsx";

const STORAGE_KEY = "agencydesk_token";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(STORAGE_KEY));
  const [session, setSession] = useState(null);
  const [openProject, setOpenProject] = useState(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (!token) {
      setSession(null);
      return;
    }
    localStorage.setItem(STORAGE_KEY, token);
    api
      .myAgency(token)
      .then((info) =>
        setSession({ token, role: info.your_role, agencyId: info.id, agencyName: info.name })
      )
      .catch(() => {
        localStorage.removeItem(STORAGE_KEY);
        setToken(null);
      });
  }, [token]);

  function handleSession({ token }) {
    setToken(token);
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setSession(null);
    setOpenProject(null);
  }

  if (!token || !session) {
    return <Login onSession={handleSession} />;
  }

  const roleLabel = session.role.replace("_", " ");

  return (
    <div className="app-shell">
      <div className="topbar">
        <div className="brand">
          <span className="mark" />
          AgencyDesk
        </div>
        <div className="topbar-right">
          <span>{session.agencyName}</span>
          <span className="role-chip">{roleLabel}</span>
          <button className="link-btn" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
      <div className="main">
        {loadError && <div className="error-banner">{loadError}</div>}
        {openProject ? (
          <ProjectBoard session={session} project={openProject} onBack={() => setOpenProject(null)} />
        ) : (
          <ProjectsList session={session} onOpenProject={setOpenProject} />
        )}
      </div>
    </div>
  );
}

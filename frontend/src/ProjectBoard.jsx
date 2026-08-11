import { useEffect, useState } from "react";
import { api } from "./api";
import TaskDrawer from "./TaskDrawer.jsx";

const COLUMNS = [
  { key: "todo", label: "To do" },
  { key: "in_progress", label: "In progress" },
  { key: "in_review", label: "In review" },
  { key: "done", label: "Done" },
];

export default function ProjectBoard({ session, project, onBack }) {
  const { token, role } = session;
  const isStaff = role === "agency_admin" || role === "agency_member";
  const isAdmin = role === "agency_admin";
  const isClient = role === "client_user";

  const [tasks, setTasks] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [members, setMembers] = useState([]);
  const [assigned, setAssigned] = useState([]);
  const [activeTask, setActiveTask] = useState(null);
  const [error, setError] = useState("");
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newVisibility, setNewVisibility] = useState("internal");
  const [showManage, setShowManage] = useState(false);
  const [addMemberId, setAddMemberId] = useState("");

  async function loadAll() {
    setError("");
    try {
      const [t, d] = await Promise.all([
        api.tasks(token, project.id),
        api.dashboard(token, project.id),
      ]);
      setTasks(t);
      setDashboard(d);
      if (isStaff) {
        const [m, a] = await Promise.all([api.members(token), api.assignments(token, project.id)]);
        setMembers(m);
        setAssigned(a);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  async function createTask(e) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      await api.createTask(token, project.id, { title: newTitle, visibility: newVisibility });
      setNewTitle("");
      setShowNewTask(false);
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addMember() {
    if (!addMemberId) return;
    try {
      await api.assignMember(token, project.id, addMemberId);
      setAddMemberId("");
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeMember(userId) {
    try {
      const res = await api.removeMember(token, project.id, userId);
      if (res.unassigned_task_ids?.length) {
        setError(`Removed. ${res.unassigned_task_ids.length} in-flight task(s) were unassigned.`);
      }
      loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleTaskChanged(updated) {
    setTasks((ts) => ts.map((t) => (t.id === updated.id ? updated : t)));
    setActiveTask(updated);
  }

  const nonAssigned = members.filter((m) => !assigned.some((a) => a.user_id === m.user_id));

  return (
    <div>
      <div className="crumb">
        <button onClick={onBack}>← Projects</button>
      </div>
      <div className="page-head">
        <div>
          <div className="page-title">{project.name}</div>
          {project.description && <div className="page-sub">{project.description}</div>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {isAdmin && (
            <button className="btn btn-ghost" onClick={() => setShowManage((s) => !s)}>
              Team
            </button>
          )}
          {isStaff && (
            <button className="btn btn-accent" onClick={() => setShowNewTask((s) => !s)}>
              + New task
            </button>
          )}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {dashboard && (
        <div className="stat-grid">
          {COLUMNS.map((c) => (
            <div className="stat" key={c.key}>
              <div className="stat-num">{dashboard.task_counts_by_status[c.key] ?? 0}</div>
              <div className="stat-label">{c.label}</div>
            </div>
          ))}
        </div>
      )}
      {isStaff && dashboard && (
        <div className="page-sub" style={{ marginBottom: 18 }}>
          {dashboard.total_hours_logged}h logged on this project
        </div>
      )}

      {showManage && isAdmin && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="section-label" style={{ marginTop: 0 }}>
            Project team
          </div>
          {assigned.map((m) => (
            <div className="file-row" key={m.user_id}>
              <span>
                {m.name} <span style={{ color: "var(--ink-soft)" }}>· {m.email}</span>
              </span>
              <button className="btn btn-danger btn-sm" onClick={() => removeMember(m.user_id)}>
                Remove
              </button>
            </div>
          ))}
          {assigned.length === 0 && <div className="empty">No one assigned yet.</div>}
          {nonAssigned.length > 0 && (
            <div className="inline-form" style={{ marginTop: 12, marginBottom: 0 }}>
              <select value={addMemberId} onChange={(e) => setAddMemberId(e.target.value)}>
                <option value="">Add staff member…</option>
                {nonAssigned.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name} ({m.role.replace("_", " ")})
                  </option>
                ))}
              </select>
              <button className="btn btn-primary btn-sm" onClick={addMember}>
                Add
              </button>
            </div>
          )}
        </div>
      )}

      {showNewTask && isStaff && (
        <form onSubmit={createTask} className="card" style={{ marginBottom: 18 }}>
          <div className="inline-form" style={{ marginBottom: 0 }}>
            <input placeholder="Task title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} autoFocus />
            <select value={newVisibility} onChange={(e) => setNewVisibility(e.target.value)}>
              <option value="internal">Internal</option>
              <option value="client_visible">Client-visible</option>
            </select>
            <button className="btn btn-primary btn-sm">Create</button>
          </div>
        </form>
      )}

      <div className="board">
        {COLUMNS.map((col) => (
          <div className="col" key={col.key}>
            <div className="col-head">
              <span>{col.label}</span>
              <span>{tasks.filter((t) => t.status === col.key).length}</span>
            </div>
            {tasks
              .filter((t) => t.status === col.key)
              .map((t) => (
                <div className="task-card" key={t.id} onClick={() => setActiveTask(t)}>
                  <div className="task-title">{t.title}</div>
                  <div className="task-meta-row">
                    <span className={`tag ${t.visibility === "client_visible" ? "tag-client" : "tag-internal"}`}>
                      {t.visibility === "client_visible" ? "client" : "internal"}
                    </span>
                    <span className={`tag tag-priority-${t.priority}`}>{t.priority}</span>
                  </div>
                </div>
              ))}
          </div>
        ))}
      </div>

      {activeTask && (
        <TaskDrawer
          session={session}
          task={activeTask}
          members={members}
          isStaff={isStaff}
          isClient={isClient}
          onClose={() => setActiveTask(null)}
          onChanged={handleTaskChanged}
        />
      )}
    </div>
  );
}

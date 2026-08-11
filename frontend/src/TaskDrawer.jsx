import { useEffect, useState } from "react";
import { api } from "./api";

const STATUSES = ["todo", "in_progress", "in_review", "done"];

export default function TaskDrawer({ session, task, members, isStaff, isClient, onClose, onChanged }) {
  const { token } = session;
  const [comments, setComments] = useState([]);
  const [files, setFiles] = useState([]);
  const [timeEntries, setTimeEntries] = useState([]);
  const [tab, setTab] = useState("activity");
  const [newComment, setNewComment] = useState("");
  const [commentVisibility, setCommentVisibility] = useState("internal");
  const [error, setError] = useState("");

  const [timeMinutes, setTimeMinutes] = useState(30);
  const [timeNote, setTimeNote] = useState("");
  const [uploadVisibility, setUploadVisibility] = useState("internal");

  async function refresh() {
    try {
      const [c, f] = await Promise.all([api.comments(token, task.id), api.files(token, task.id)]);
      setComments(c);
      setFiles(f);
      if (isStaff) setTimeEntries(await api.timeEntries(token, task.id));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task.id]);

  async function patch(body) {
    setError("");
    try {
      const updated = await api.updateTask(token, task.id, body);
      onChanged(updated);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitComment(e) {
    e.preventDefault();
    if (!newComment.trim()) return;
    try {
      await api.addComment(token, task.id, {
        body: newComment,
        visibility: isClient ? "client_visible" : commentVisibility,
      });
      setNewComment("");
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitTime(e) {
    e.preventDefault();
    try {
      await api.logTime(token, task.id, {
        duration_minutes: Number(timeMinutes),
        note: timeNote || undefined,
        entry_date: new Date().toISOString().slice(0, 10),
      });
      setTimeNote("");
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    try {
      await api.uploadFile(token, task.id, file, uploadVisibility);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function approve(fileId, status) {
    try {
      await api.setApproval(token, fileId, status);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  const assigneeName = (id) => members.find((m) => m.user_id === id)?.name || "Unassigned";

  return (
    <div className="overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <div style={{ fontFamily: "var(--display)", fontWeight: 600, fontSize: 19 }}>{task.title}</div>
            <div className="task-meta-row" style={{ marginTop: 8 }}>
              <span className={`tag ${task.visibility === "client_visible" ? "tag-client" : "tag-internal"}`}>
                {task.visibility === "client_visible" ? "Client-visible" : "Internal"}
              </span>
              <span className={`tag tag-priority-${task.priority}`}>{task.priority}</span>
            </div>
          </div>
          <button className="link-btn" onClick={onClose}>
            close ✕
          </button>
        </div>

        {error && <div className="error-banner">{error}</div>}

        {task.description && <p style={{ fontSize: 13.5, color: "var(--ink-soft)" }}>{task.description}</p>}

        {isStaff && (
          <div className="card" style={{ marginBottom: 4 }}>
            <div className="field">
              <label>Status</label>
              <select value={task.status} onChange={(e) => patch({ status: e.target.value })}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Assignee</label>
              <select
                value={task.assignee_id || ""}
                onChange={(e) => patch({ assignee_id: e.target.value || null })}
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
        {isClient && (
          <div className="task-meta-row" style={{ marginBottom: 10 }}>
            <span className="tag" style={{ background: "#e6e9e8", color: "var(--ink-soft)" }}>
              status: {task.status.replace("_", " ")}
            </span>
            <span className="tag" style={{ background: "#e6e9e8", color: "var(--ink-soft)" }}>
              owner: {assigneeName(task.assignee_id)}
            </span>
          </div>
        )}

        <div className="tabs">
          <button className={`tab ${tab === "activity" ? "active" : ""}`} onClick={() => setTab("activity")}>
            Comments
          </button>
          <button className={`tab ${tab === "files" ? "active" : ""}`} onClick={() => setTab("files")}>
            Files
          </button>
          {isStaff && (
            <button className={`tab ${tab === "time" ? "active" : ""}`} onClick={() => setTab("time")}>
              Time
            </button>
          )}
        </div>

        {tab === "activity" && (
          <>
            {comments.length === 0 && <div className="empty">No comments yet.</div>}
            {comments.map((c) => (
              <div className="comment" key={c.id}>
                <div className="comment-meta">
                  <span>{c.visibility === "client_visible" ? "Client-visible" : "Internal"}</span>
                  <span>{new Date(c.created_at).toLocaleString()}</span>
                </div>
                {c.body}
              </div>
            ))}
            <form onSubmit={submitComment} style={{ marginTop: 12 }}>
              <div className="field">
                <textarea
                  rows={3}
                  placeholder="Add a comment…"
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                />
              </div>
              <div className="inline-form" style={{ marginBottom: 0 }}>
                {!isClient && (
                  <select value={commentVisibility} onChange={(e) => setCommentVisibility(e.target.value)}>
                    <option value="internal">Internal</option>
                    <option value="client_visible">Client-visible</option>
                  </select>
                )}
                <button className="btn btn-primary btn-sm">Post</button>
              </div>
            </form>
          </>
        )}

        {tab === "files" && (
          <>
            {files.length === 0 && <div className="empty">No files yet.</div>}
            {files.map((f) => (
              <div className="file-row" key={f.id}>
                <a href={api.downloadUrl(f.id)} target="_blank" rel="noreferrer">
                  {f.filename}
                </a>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <span
                    className="tag"
                    style={{
                      background:
                        f.approval_status === "approved"
                          ? "rgba(31,95,91,0.15)"
                          : f.approval_status === "needs_changes"
                          ? "rgba(179,74,63,0.14)"
                          : "#e6e9e8",
                      color:
                        f.approval_status === "approved"
                          ? "var(--teal)"
                          : f.approval_status === "needs_changes"
                          ? "var(--danger)"
                          : "var(--ink-soft)",
                    }}
                  >
                    {f.approval_status.replace("_", " ")}
                  </span>
                  {isClient && f.approval_status !== "approved" && (
                    <button className="btn btn-ghost btn-sm" onClick={() => approve(f.id, "approved")}>
                      Approve
                    </button>
                  )}
                  {isClient && f.approval_status !== "needs_changes" && (
                    <button className="btn btn-ghost btn-sm" onClick={() => approve(f.id, "needs_changes")}>
                      Request changes
                    </button>
                  )}
                </div>
              </div>
            ))}
            {isStaff && (
              <div className="inline-form" style={{ marginTop: 12 }}>
                <select value={uploadVisibility} onChange={(e) => setUploadVisibility(e.target.value)}>
                  <option value="internal">Internal</option>
                  <option value="client_visible">Client-visible</option>
                </select>
                <input type="file" onChange={handleUpload} />
              </div>
            )}
          </>
        )}

        {tab === "time" && isStaff && (
          <>
            {timeEntries.length === 0 && <div className="empty">No time logged yet.</div>}
            {timeEntries.map((t) => (
              <div className="time-row" key={t.id}>
                <span>{t.note || "—"}</span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 12 }}>
                  {(t.duration_minutes / 60).toFixed(1)}h · {t.entry_date}
                </span>
              </div>
            ))}
            <form onSubmit={submitTime} className="inline-form" style={{ marginTop: 12 }}>
              <input
                type="number"
                min={1}
                style={{ maxWidth: 100 }}
                value={timeMinutes}
                onChange={(e) => setTimeMinutes(e.target.value)}
              />
              <input placeholder="note (optional)" value={timeNote} onChange={(e) => setTimeNote(e.target.value)} />
              <button className="btn btn-primary btn-sm">Log</button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

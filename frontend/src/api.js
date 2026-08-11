const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, { method = "GET", body, token, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE_URL}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (isJson && data?.detail) || res.statusText;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

export const api = {
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  selectAgency: (pre_auth_token, agency_id) =>
    request("/auth/select-agency", { method: "POST", body: { pre_auth_token, agency_id } }),
  signup: (payload) => request("/auth/signup", { method: "POST", body: payload }),
  acceptInvite: (payload) => request("/invites/accept", { method: "POST", body: payload }),

  myAgency: (token) => request("/agency/me", { token }),
  members: (token) => request("/agency/members", { token }),

  clients: (token) => request("/clients", { token }),
  createClient: (token, name) => request("/clients", { method: "POST", token, body: { name } }),

  projects: (token) => request("/projects", { token }),
  project: (token, id) => request(`/projects/${id}`, { token }),
  createProject: (token, body) => request("/projects", { method: "POST", token, body }),
  assignments: (token, projectId) => request(`/projects/${projectId}/assignments`, { token }),
  assignMember: (token, projectId, userId) =>
    request(`/projects/${projectId}/assignments`, { method: "POST", token, body: { user_id: userId } }),
  removeMember: (token, projectId, userId) =>
    request(`/projects/${projectId}/assignments/${userId}`, { method: "DELETE", token }),

  tasks: (token, projectId) => request(`/projects/${projectId}/tasks`, { token }),
  task: (token, id) => request(`/tasks/${id}`, { token }),
  createTask: (token, projectId, body) =>
    request(`/projects/${projectId}/tasks`, { method: "POST", token, body }),
  updateTask: (token, id, body) => request(`/tasks/${id}`, { method: "PATCH", token, body }),

  comments: (token, taskId) => request(`/tasks/${taskId}/comments`, { token }),
  addComment: (token, taskId, body) => request(`/tasks/${taskId}/comments`, { method: "POST", token, body }),

  files: (token, taskId) => request(`/tasks/${taskId}/files`, { token }),
  uploadFile: (token, taskId, file, visibility) => {
    const form = new FormData();
    form.append("upload", file);
    return request(`/tasks/${taskId}/files?visibility=${visibility}`, { method: "POST", token, form });
  },
  setApproval: (token, fileId, approval_status) =>
    request(`/files/${fileId}/approval`, { method: "PATCH", token, body: { approval_status } }),
  downloadUrl: (fileId) => `${BASE_URL}/files/${fileId}/download`,

  timeEntries: (token, taskId) => request(`/tasks/${taskId}/time-entries`, { token }),
  logTime: (token, taskId, body) => request(`/tasks/${taskId}/time-entries`, { method: "POST", token, body }),

  dashboard: (token, projectId) => request(`/projects/${projectId}/dashboard`, { token }),

  invites: (token) => request("/invites", { token }),
  createInvite: (token, body) => request("/invites", { method: "POST", token, body }),
};

export { BASE_URL };

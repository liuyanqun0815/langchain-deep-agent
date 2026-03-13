import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail ?? err.message ?? "请求失败";
    console.error("[API]", msg);
    return Promise.reject(new Error(typeof msg === "string" ? msg : JSON.stringify(msg)));
  }
);

export interface SessionOut {
  id: number;
  title: string;
  config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: number;
  session_id: number;
  role: string;
  content: string;
  metadata_?: Record<string, unknown> | null;
  created_at: string;
}

export interface SkillOut {
  id: number;
  name: string;
  description: string;
  type: string;
  config: Record<string, unknown> | null;
  enabled: boolean;
  source_type: string;
  source_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigOut {
  default_model: string;
  planner_model: string | null;
  max_tokens: number;
  temperature: number;
}

export const sessionsApi = {
  list: (params?: { limit?: number; offset?: number }) =>
    api.get<{ items: SessionOut[]; total: number }>("/sessions", { params }).then((r) => r.data),
  create: (data?: { title?: string }) =>
    api.post<SessionOut>("/sessions", data ?? {}).then((r) => r.data),
  get: (id: number) =>
    api.get<{ session: SessionOut; messages: MessageOut[] }>(`/sessions/${id}`).then((r) => r.data),
  sendMessage: (sessionId: number, user_message: string) =>
    api
      .post<{
        role: string;
        content: string;
        message_id: number;
        created_at: string;
        inference_steps: { kind: string; name?: string; content: string }[];
      }>(`/sessions/${sessionId}/messages`, { user_message })
      .then((r) => r.data),
  sendMessageWithFiles: (sessionId: number, user_message: string, files: File[]) => {
    const form = new FormData();
    form.append("user_message", user_message);
    files.forEach((f) => form.append("files", f));
    return api
      .post<{
        role: string;
        content: string;
        message_id: number;
        created_at: string;
        inference_steps: { kind: string; name?: string; content: string }[];
      }>(`/sessions/${sessionId}/messages/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data);
  },
  delete: (id: number) => api.delete(`/sessions/${id}`),
  clearAll: () => api.delete("/sessions"),
};

export const skillsApi = {
  list: () => api.get<SkillOut[]>("/skills").then((r) => r.data),
  addFromLocal: (source_path: string) =>
    api.post<SkillOut>("/skills/from-local", { source_path }).then((r) => r.data),
  addFromGitHub: (repo_url: string) =>
    api.post<SkillOut[]>("/skills/from-github", { repo_url }).then((r) => r.data),
  toggle: (id: number, enabled: boolean) =>
    api.patch<SkillOut>(`/skills/${id}/toggle`, { enabled }).then((r) => r.data),
  delete: (id: number) => api.delete(`/skills/${id}`),
};

export const agentConfigApi = {
  get: () => api.get<AgentConfigOut>("/agent/config").then((r) => r.data),
  update: (data: Partial<AgentConfigOut>) =>
    api.put<AgentConfigOut>("/agent/config", data).then((r) => r.data),
};

export const modelsApi = {
  list: () => api.get<{ id: string; name: string; provider: string; description: string }[]>("/models").then((r) => r.data),
  test: () => api.post<{ success: boolean; message: string }>("/models/test").then((r) => r.data),
};

export default api;

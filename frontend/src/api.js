import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 30000,
});

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || "Request failed";
    return Promise.reject(new Error(msg));
  }
);

// ── Channels ───────────────────────────────────────────────────────────────
export const channelsApi = {
  listSecretFiles: () => api.get("/channels/client-secrets-files"),
  list: () => api.get("/channels/"),
  get: (id) => api.get(`/channels/${id}`),
  create: (data) => api.post("/channels/", data),
  update: (id, data) => api.patch(`/channels/${id}`, data),
  delete: (id) => api.delete(`/channels/${id}`),
  startOAuth: (id) => api.get(`/channels/${id}/oauth/start`),
  revokeOAuth: (id) => api.post(`/channels/${id}/oauth/revoke`),
  resetQuota: (id) => api.post(`/channels/${id}/quota/reset`),
  categories: () => api.get("/channels/categories/list"),
};

// ── Downloads / Jobs ───────────────────────────────────────────────────────
export const downloadsApi = {
  getInfo: (url) => api.post("/downloads/info", { url }),
  createJob: (data) => api.post("/downloads/jobs", data),
  getCookiesStatus: () => api.get("/downloads/cookies/status"),
  uploadCookies: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post("/downloads/cookies/upload", fd);
  },
  deleteCookies: () => api.delete("/downloads/cookies"),
};

// ── Queue ──────────────────────────────────────────────────────────────────
export const queueApi = {
  list: (params) => api.get("/queue/", { params }),
  get: (id) => api.get(`/queue/${id}`),
  update: (id, data) => api.patch(`/queue/${id}`, data),
  delete: (id) => api.delete(`/queue/${id}`),
  cancel: (id) => api.post(`/queue/${id}/cancel`),
  retry: (id) => api.post(`/queue/${id}/retry`),
  enqueue: (id) => api.post(`/queue/${id}/queue`),
  uploadNow: (id) => api.post(`/queue/${id}/upload-now`),
  reorder: (ids) => api.post("/queue/reorder", ids),
  cleanupUploaded: () => api.post("/queue/cleanup-uploaded"),
};

// ── Schedules ──────────────────────────────────────────────────────────────
export const schedulesApi = {
  list: (params) => api.get("/schedules/", { params }),
  create: (data) => api.post("/schedules/", data),
  update: (id, data) => api.patch(`/schedules/${id}`, data),
  delete: (id) => api.delete(`/schedules/${id}`),
  pause: (id) => api.post(`/schedules/${id}/pause`),
  resume: (id) => api.post(`/schedules/${id}/resume`),
};

// ── Templates ──────────────────────────────────────────────────────────────
export const templatesApi = {
  list: () => api.get("/schedules/templates/"),
  create: (data) => api.post("/schedules/templates/", data),
  update: (id, data) => api.patch(`/schedules/templates/${id}`, data),
  delete: (id) => api.delete(`/schedules/templates/${id}`),
};

// ── Dashboard ──────────────────────────────────────────────────────────────
export const dashboardApi = {
  stats: () => api.get("/dashboard/stats"),
  quota: () => api.get("/dashboard/channels/quota"),
  activity: (params) => api.get("/dashboard/activity", { params }),
  upcoming: (params) => api.get("/dashboard/queue/upcoming", { params }),
  uploadThumbnail: (jobId, file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post(`/dashboard/thumbnail/upload?job_id=${jobId}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  cleanup: (days) => api.delete(`/dashboard/cleanup?older_than_days=${days}`),
};

// ── Auto Creator ──────────────────────────────────────────────────────────
export const autoCreatorApi = {
  analyzeTrend: (data) => api.post("/auto-creator/analyze-trend", data),
  searchVideos: (query, maxResults = 10) =>
    api.get("/auto-creator/search-videos", { params: { query, max_results: maxResults } }),
  channelVideos: (url, maxResults = 12) =>
    api.get("/auto-creator/channel-videos", { params: { url, max_results: maxResults } }),
  reup: (data) => api.post("/auto-creator/reup", data),
  generate: (data) => api.post("/auto-creator/generate", data),
};

// ── TikTok ────────────────────────────────────────────────────────────────
export const tiktokApi = {
  listAccounts: () => api.get("/tiktok/accounts"),
  createAccount: (data) => api.post("/tiktok/accounts", data),
  deleteAccount: (id) => api.delete(`/tiktok/accounts/${id}`),
  startOAuth: (id) => api.get(`/tiktok/accounts/${id}/oauth/start`),
};

// ── Media (preview / review / upload) ────────────────────────────────────────
export const mediaApi = {
  approve: (id) => api.post(`/media/review/${id}/approve`),
  reject: (id) => api.post(`/media/review/${id}/reject`),
  uploadLogo: (file) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/media/upload/logo", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  uploadOutro: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/media/upload/outro", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 300000,
      onUploadProgress: onProgress,
    });
  },
  uploadVideo: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/media/upload/video", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 600000, // 10 phút cho video lớn
      onUploadProgress: onProgress,
    });
  },
  listVideos: () => api.get("/media/files/videos"),
  listOutros: () => api.get("/media/files/outros"),
  listLogos: () => api.get("/media/files/logos"),
};

// ── Trending ──────────────────────────────────────────────────────────────
export const trendingApi = {
  // Videos
  list: (params) => api.get("/trending/", { params }),
  update: (id, data) => api.patch(`/trending/${id}`, data),
  delete: (id) => api.delete(`/trending/${id}`),
  fetch: (data) => api.post("/trending/fetch", data),
  fetchAll: (filterPeople = true) => api.post(`/trending/fetch-all?filter_people=${filterPeople}`),
  fetchTikTokChannel: (data) => api.post("/trending/fetch-tiktok-channel", data),
  import: (data) => api.post("/trending/import", data),
  // Hashtags
  listHashtags: () => api.get("/trending/hashtags"),
  addHashtag: (data) => api.post("/trending/hashtags", data),
  deleteHashtag: (id) => api.delete(`/trending/hashtags/${id}`),
  toggleHashtag: (id) => api.patch(`/trending/hashtags/${id}/toggle`),
};

export default api;

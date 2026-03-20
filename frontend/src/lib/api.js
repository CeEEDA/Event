import axios from "axios";
import { saveAs } from "file-saver";

const BACKEND_URL = (() => {
  // If served behind Caddy/reverse proxy, use relative URL
  if (typeof window !== 'undefined' && window.location) {
    const origin = window.location.origin;
    // On the live server, use same origin (Caddy proxies /api/*)
    if (origin.includes('portal.eventenergie') || origin.includes('localhost')) {
      return '';
    }
  }
  return process.env.REACT_APP_BACKEND_URL || '';
})();

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login" && 
          window.location.pathname !== "/register" &&
          !window.location.pathname.startsWith("/share/")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export { BACKEND_URL };
export default api;

/** Extract human-readable error message from axios error (handles Pydantic validation arrays). */
export const getErrorMsg = (err, fallback = "Fehler") => {
  const d = err?.response?.data?.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(e => (typeof e === "string" ? e : e?.msg || "")).filter(Boolean).join(", ") || fallback;
  return fallback;
};

// Check if running inside a sandboxed iframe
const isInSandboxedIframe = () => {
  try {
    return window.self !== window.top;
  } catch (e) {
    return true;
  }
};

// Build download URLs
export const getDownloadUrl = (fileId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/files/${fileId}/download?token=${token}`;
};

export const getFolderDownloadUrl = (folderId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/folders/${folderId}/download?token=${token}`;
};

// Download callback - set by DashboardPage to show download link modal
let _downloadLinkCallback = null;
export const setDownloadLinkCallback = (cb) => { _downloadLinkCallback = cb; };

// Download file
export const downloadFile = async (fileId, filename) => {
  const url = getDownloadUrl(fileId);

  if (isInSandboxedIframe()) {
    // In sandboxed iframe: show download link to user
    if (_downloadLinkCallback) {
      _downloadLinkCallback(url, filename);
    }
    return;
  }

  // Normal download outside iframe
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const blob = await response.blob();
  saveAs(blob, filename);
};

// Download folder as ZIP
export const downloadFolderZip = async (folderId, folderName) => {
  const url = getFolderDownloadUrl(folderId);

  if (isInSandboxedIframe()) {
    if (_downloadLinkCallback) {
      _downloadLinkCallback(url, `${folderName}.zip`);
    }
    return;
  }

  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const blob = await response.blob();
  saveAs(blob, `${folderName}.zip`);
};

// File upload helper
export const uploadFile = async (file, folderPath = "/") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("folder_path", folderPath);
  return api.post("/files/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

// Public download helper
export const downloadSharedFile = async (token, password = null) => {
  return axios.post(
    `${BACKEND_URL}/api/public/share/${token}/download`,
    { password },
    { responseType: "blob" }
  );
};

// Public upload helper
export const uploadToShare = async (token, file, password = null) => {
  const formData = new FormData();
  formData.append("file", file);
  if (password) formData.append("password", password);
  return axios.post(
    `${BACKEND_URL}/api/public/share/${token}/upload`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
};

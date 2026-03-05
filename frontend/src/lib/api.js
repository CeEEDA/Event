import axios from "axios";
import { saveAs } from "file-saver";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle auth errors
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

export default api;

// Build download URLs
export const getDownloadUrl = (fileId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/files/${fileId}/download?token=${token}`;
};

export const getFolderDownloadUrl = (folderId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/folders/${folderId}/download?token=${token}`;
};

// Download file
export const downloadFile = async (fileId, filename) => {
  const response = await fetch(getDownloadUrl(fileId));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const blob = await response.blob();
  saveAs(blob, filename);
};

// Download folder as ZIP
export const downloadFolderZip = async (folderId, folderName) => {
  const response = await fetch(getFolderDownloadUrl(folderId));
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

import axios from "axios";

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
  (error) => {
    return Promise.reject(error);
  }
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

// Build direct download URL (for <a href> links)
export const getDownloadUrl = (fileId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/files/${fileId}/download?token=${token}`;
};

export const getFolderDownloadUrl = (folderId) => {
  const token = localStorage.getItem("token");
  return `${BACKEND_URL}/api/folders/${folderId}/download?token=${token}`;
};
// File upload helper
export const uploadFile = async (file, folderPath = "/") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("folder_path", folderPath);
  
  return api.post("/files/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
};

import { saveAs } from 'file-saver';

// Download file with full debug logging
export const downloadFile = async (fileId, filename) => {
  const token = localStorage.getItem("token");
  const baseUrl = process.env.REACT_APP_BACKEND_URL;
  console.log('[DL] Start download:', fileId, filename);
  
  const response = await fetch(`${baseUrl}/api/files/${fileId}/download?token=${token}`);
  console.log('[DL] Fetch status:', response.status);
  
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  
  const blob = await response.blob();
  console.log('[DL] Blob:', blob.size, 'bytes, type:', blob.type);
  
  // Try file-saver
  try {
    saveAs(blob, filename);
    console.log('[DL] saveAs called OK');
  } catch (e) {
    console.error('[DL] saveAs failed:', e);
  }
};

// Download folder as ZIP
export const downloadFolderZip = async (folderId, folderName) => {
  const token = localStorage.getItem("token");
  const baseUrl = process.env.REACT_APP_BACKEND_URL;
  console.log('[DL] Start ZIP download:', folderId, folderName);
  
  const response = await fetch(`${baseUrl}/api/folders/${folderId}/download?token=${token}`);
  console.log('[DL] Fetch status:', response.status);
  
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  
  const blob = await response.blob();
  console.log('[DL] Blob:', blob.size, 'bytes');
  
  try {
    saveAs(blob, `${folderName}.zip`);
    console.log('[DL] saveAs called OK');
  } catch (e) {
    console.error('[DL] saveAs failed:', e);
  }
};

// Public download helper
export const downloadSharedFile = async (token, password = null) => {
  const response = await axios.post(
    `${BACKEND_URL}/api/public/share/${token}/download`,
    { password },
    { responseType: "blob" }
  );
  return response;
};

// Public upload helper
export const uploadToShare = async (token, file, password = null) => {
  const formData = new FormData();
  formData.append("file", file);
  if (password) {
    formData.append("password", password);
  }
  
  return axios.post(
    `${BACKEND_URL}/api/public/share/${token}/upload`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    }
  );
};

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

// Download file - uses <a target="_top"> to escape iframe sandbox
export const downloadFile = (fileId, filename) => {
  const token = localStorage.getItem("token");
  const baseUrl = process.env.REACT_APP_BACKEND_URL;
  const url = `${baseUrl}/api/files/${fileId}/download?token=${token}`;
  
  const a = document.createElement('a');
  a.href = url;
  a.target = '_top';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

// Download folder as ZIP
export const downloadFolderZip = (folderId, folderName) => {
  const token = localStorage.getItem("token");
  const baseUrl = process.env.REACT_APP_BACKEND_URL;
  const url = `${baseUrl}/api/folders/${folderId}/download?token=${token}`;
  
  const a = document.createElement('a');
  a.href = url;
  a.target = '_top';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
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

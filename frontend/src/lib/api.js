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

// Download file helper - robust for iframe/preview environments
export const downloadFile = async (fileId, filename) => {
  const response = await api.get(`/files/${fileId}/download`, {
    responseType: "blob",
  });
  
  const blob = new Blob([response.data]);
  const url = window.URL.createObjectURL(blob);
  
  // Method 1: Create anchor with download attribute
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  
  // Force click with timeout for iframe compatibility
  setTimeout(() => {
    link.click();
    // Cleanup after delay
    setTimeout(() => {
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    }, 5000);
  }, 100);
};

// Download folder as ZIP
export const downloadFolderZip = async (folderId, folderName) => {
  const response = await api.get(`/folders/${folderId}/download`, {
    responseType: "blob",
  });
  
  const blob = new Blob([response.data], { type: "application/zip" });
  const url = window.URL.createObjectURL(blob);
  
  const link = document.createElement("a");
  link.href = url;
  link.download = `${folderName}.zip`;
  link.style.display = "none";
  document.body.appendChild(link);
  
  setTimeout(() => {
    link.click();
    setTimeout(() => {
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    }, 5000);
  }, 100);
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

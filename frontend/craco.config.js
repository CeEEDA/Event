// craco.config.js
const path = require("path");
const webpack = require("webpack");

// Explicitly load .env from project root
try {
  require("dotenv").config({ path: path.resolve(__dirname, ".env") });
} catch (e) {
  // dotenv not critical
}

// CRITICAL: Force set backend URL if not set by .env
// This ensures the URL is ALWAYS available during production builds
if (!process.env.REACT_APP_BACKEND_URL) {
  process.env.REACT_APP_BACKEND_URL = "https://portal.eventenergie.com";
}

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // CRITICAL FIX: Force inject REACT_APP_BACKEND_URL into webpack DefinePlugin
      // This bypasses any .env file issues (BOM, encoding, missing file)
      const FALLBACK_URL = "https://portal.eventenergie.com";
      const definePlugin = webpackConfig.plugins.find(
        (p) => p.constructor.name === "DefinePlugin"
      );
      if (definePlugin && definePlugin.definitions) {
        const env = definePlugin.definitions["process.env"];
        if (env && typeof env === "object") {
          if (!env.REACT_APP_BACKEND_URL || env.REACT_APP_BACKEND_URL === '""' || env.REACT_APP_BACKEND_URL === "undefined") {
            env.REACT_APP_BACKEND_URL = JSON.stringify(FALLBACK_URL);
          }
        }
      }

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}

module.exports = webpackConfig;

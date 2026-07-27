const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:3003',
      changeOrigin: true,
      pathRewrite: {
        '^/api': '', // remove /api prefix
      },
    })
  );

  // AI assistant (FastAPI) during `npm start` dev
  app.use(
    '/ai',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
      pathRewrite: {
        '^/ai': '', // /ai/ask -> /ask
      },
    })
  );
};

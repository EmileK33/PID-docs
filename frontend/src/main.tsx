// SPA bootstrap (Vite entry). Mounts <App/> into #root.
//
// [LOAD-BEARING entry point] Do not touch after merge.
import React from 'react';
import ReactDOM from 'react-dom/client';

import App from './App';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error('Root element #root not found');
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

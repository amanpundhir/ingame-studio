import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { installSessionFetch } from './services/session';

// Every API call from this tab carries its own match session id.
installSessionFetch();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

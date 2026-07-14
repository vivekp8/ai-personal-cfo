import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import ErrorBoundary from "./components/ErrorBoundary";
import { MotionProvider } from "./lib/motion";
import "./index.css";

const AppErrorFallback = (
  <div className="ambient-bg flex min-h-screen flex-col items-center justify-center px-6 text-center">
    <div className="glass-strong max-w-md rounded-2xl p-8">
      <div className="mb-3 text-4xl">⚠️</div>
      <h1 className="text-xl font-bold">Something went wrong</h1>
      <p className="mt-2 text-sm text-slate-400">
        The app hit an unexpected error while rendering. Check the browser
        console for details, then reload.
      </p>
      <button
        onClick={() => location.reload()}
        className="mt-4 rounded-xl bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900"
      >
        Reload
      </button>
    </div>
  </div>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary fallback={AppErrorFallback}>
      <MotionProvider>
        <App />
      </MotionProvider>
    </ErrorBoundary>
  </React.StrictMode>
);

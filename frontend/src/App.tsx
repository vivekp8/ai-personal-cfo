import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Capabilities,
  DashboardData,
  getCapabilities,
  getHealth,
} from "./api";
import Dashboard from "./components/Dashboard";
import Header from "./components/Header";
import Landing from "./components/Landing";

type BackendState = "checking" | "online" | "offline";

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [backend, setBackend] = useState<BackendState>("checking");

  useEffect(() => {
    getHealth()
      .then(() => setBackend("online"))
      .catch(() => setBackend("offline"));
    getCapabilities()
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
  }, []);

  if (backend === "offline") {
    return (
      <div className="ambient-bg flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <div className="glass-strong max-w-md rounded-2xl p-8">
          <div className="mb-3 text-4xl">🔌</div>
          <h1 className="text-xl font-bold">Backend not reachable</h1>
          <p className="mt-2 text-sm text-slate-400">
            Start the FastAPI server, then reload:
          </p>
          <pre className="mt-3 rounded-lg bg-black/40 px-4 py-3 text-left text-xs text-teal-accent">
            cd backend{"\n"}uvicorn main:app --reload
          </pre>
          <button
            onClick={() => location.reload()}
            className="mt-4 rounded-xl bg-teal-accent px-4 py-2 text-sm font-semibold text-navy-900"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <Header
        capabilities={capabilities}
        showReset={!!data}
        onReset={() => setData(null)}
      />
      <AnimatePresence mode="wait">
        {!data ? (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: 0.4 }}
          >
            <Landing onLoaded={setData} />
          </motion.div>
        ) : (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Dashboard data={data} capabilities={capabilities} />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

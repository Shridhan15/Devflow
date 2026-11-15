import { useState, useEffect } from "react";
import TaskForm from "./TaskForm";
import ReviewPanel from "./ReviewPanel";
import { startTask, sendFeedback } from "../services/api";
import { Activity, CheckCircle2, XCircle } from "lucide-react";

export default function WorkspaceView({ workspace, onWorkspaceCreated }) {
  const [loading, setLoading] = useState(false);
  const [sessionData, setSessionData] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState("");

  // Depend on a stable key (the workspace id), not the object itself, so a
  // sidebar refresh that recreates workspace objects can't wipe an active session.
  const workspaceKey = workspace === "NEW" ? "NEW" : workspace?.workspace_id;

  useEffect(() => {
    setSessionData(null);
    setStatusMessage("");
    setError("");
  }, [workspaceKey]);

  // Shared handling for /start and /feedback responses
  const applyResult = (data, doneMessage) => {
    setSessionData(data);
    setError("");
    setStatusMessage("");
    if (data.status === "completed") {
      setStatusMessage(doneMessage);
    } else if (data.status === "failed" || data.status === "aborted") {
      setError(data.message || "The run ended without producing changes.");
    }
  };

  const errorText = (err, fallback) => err?.response?.data?.detail || fallback;

  const handleStartTask = async (task, repoUrl) => {
    setLoading(true);
    setError("");
    setStatusMessage(
      "Syncing Git workspace, calculating deltas, and updating AST index...",
    );
    try {
      const data = await startTask(task, repoUrl);
      applyResult(data, "Task completed!");
      if (workspace === "NEW") {
        onWorkspaceCreated(); // refresh sidebar only; Dashboard no longer switches views
      }
    } catch (err) {
      setStatusMessage("");
      setError(errorText(err, "Error executing task. Check server terminal."));
    }
    setLoading(false);
  };

  const handleFeedback = async (feedback) => {
    setLoading(true);
    setError("");
    setStatusMessage(
      "Processing human feedback and resuming LangGraph loop...",
    );
    try {
      const data = await sendFeedback(sessionData.thread_id, feedback);
      applyResult(data, "Pull Request created successfully!");
    } catch (err) {
      setStatusMessage("");
      setError(errorText(err, "Error resuming task."));
    }
    setLoading(false);
  };

  const wsName =
    workspace === "NEW" ? "New Workspace" : workspace?.workspace_id;

  const runFinished =
    sessionData &&
    ["completed", "failed", "aborted"].includes(sessionData.status);

  return (
    <div className="flex-1 bg-gray-950 p-10 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <header className="mb-10">
          <h2 className="text-3xl font-bold text-white mb-2">{wsName}</h2>
          <p className="text-gray-400">
            {workspace === "NEW"
              ? "Initialize a new repository into DevFlow."
              : `Connected to ${workspace?.repo_url}`}
          </p>
        </header>

        {/* Show the form on first load and again after any finished run, so failures can be retried */}
        {(!sessionData || runFinished) && (
          <TaskForm
            workspace={workspace}
            onSubmit={handleStartTask}
            isLoading={loading}
          />
        )}

        {loading && statusMessage && (
          <div className="mt-8 p-4 bg-cyan-900/20 border border-cyan-800/50 rounded-lg flex items-center text-cyan-400 animate-pulse">
            <Activity className="mr-3 animate-spin" size={20} />
            <span className="font-medium">{statusMessage}</span>
          </div>
        )}

        {!loading && error && (
          <div className="mt-8 p-4 bg-red-900/20 border border-red-800/50 rounded-lg flex items-start text-red-400">
            <XCircle className="mr-3 mt-0.5 shrink-0" size={20} />
            <span className="font-medium">{error}</span>
          </div>
        )}

        {sessionData?.status === "awaiting_approval" && !loading && (
          <ReviewPanel
            // Remount (clearing the feedback textarea) whenever the stage or thread changes
            key={`${sessionData.thread_id}-${sessionData.stage}`}
            sessionData={sessionData}
            onFeedback={handleFeedback}
            isLoading={loading}
          />
        )}

        {sessionData?.status === "completed" && !loading && (
          <div className="mt-8 p-6 bg-green-900/20 border border-green-800/50 rounded-lg flex items-center text-green-400 animate-in fade-in zoom-in-95">
            <CheckCircle2 className="mr-3" size={24} />
            <span className="font-medium text-lg">
              Mission Accomplished. Check GitHub for the PR.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

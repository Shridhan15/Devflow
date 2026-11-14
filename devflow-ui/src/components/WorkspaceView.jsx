import { useState, useEffect } from "react";
import TaskForm from "./TaskForm";
import ReviewPanel from "./ReviewPanel";
import { startTask, sendFeedback } from "../services/api";
import { Activity, CheckCircle2 } from "lucide-react";

export default function WorkspaceView({ workspace, onWorkspaceCreated }) {
  const [loading, setLoading] = useState(false);
  const [sessionData, setSessionData] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");

  // Reset view when switching workspaces
  useEffect(() => {
    setSessionData(null);
    setStatusMessage("");
  }, [workspace]);

  const handleStartTask = async (task, repoUrl) => {
    setLoading(true);
    setStatusMessage(
      "Syncing Git workspace, calculating deltas, and updating AST index...",
    );
    try {
      const data = await startTask(task, repoUrl);
      setSessionData(data);
      if (workspace === "NEW") {
        onWorkspaceCreated(); // Trigger sidebar refresh
      }
      if (data.status === "completed") setStatusMessage("Task completed!");
    } catch (error) {
      setStatusMessage("Error executing task. Check server terminal.");
    }
    setLoading(false);
  };

  const handleFeedback = async (feedback) => {
    setLoading(true);
    setStatusMessage(
      "Processing human feedback and resuming LangGraph loop...",
    );
    try {
      const data = await sendFeedback(sessionData.thread_id, feedback);
      setSessionData(data);
      if (data.status === "completed") {
        setStatusMessage("Pull Request created successfully!");
      }
    } catch (error) {
      setStatusMessage("Error resuming task.");
    }
    setLoading(false);
  };

  const wsName =
    workspace === "NEW" ? "New Workspace" : workspace?.workspace_id;

  return (
    <div className="flex-1 bg-gray-950 p-10 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <header className="mb-10">
          <h2 className="text-3xl font-bold text-white mb-2">{wsName}</h2>
          <p className="text-gray-400">
            {workspace === "NEW"
              ? "Initialize a new repository into DevFlow."
              : `Connected to ${workspace.repo_url}`}
          </p>
        </header>

        {(!sessionData || sessionData.status === "completed") && (
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

        {sessionData?.status === "awaiting_approval" && !loading && (
          <ReviewPanel
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

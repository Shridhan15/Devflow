import { useState } from "react";
import { startTask, sendFeedback } from "../services/api";
import TaskForm from "../components/TaskForm";
import ReviewPanel from "../components/ReviewPanel";
import { Activity } from "lucide-react";

export default function Dashboard() {
  const [loading, setLoading] = useState(false);
  const [sessionData, setSessionData] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");

  const handleStartTask = async (task, repoUrl) => {
    setLoading(true);
    setStatusMessage("Initializing agents and indexing repository...");
    try {
      const data = await startTask(task, repoUrl);
      setSessionData(data);
      if (data.status === "completed") {
        setStatusMessage("Task completed successfully!");
      } else {
        setStatusMessage("");
      }
    } catch (error) {
      console.error(error);
      setStatusMessage("Error executing task. Check server logs.");
    }
    setLoading(false);
  };

  const handleFeedback = async (feedback) => {
    setLoading(true);
    setStatusMessage("Processing feedback and resuming graph...");
    try {
      const data = await sendFeedback(sessionData.thread_id, feedback);
      setSessionData(data);
      if (data.status === "completed") {
        setStatusMessage("Pull Request created successfully!");
      } else {
        setStatusMessage("");
      }
    } catch (error) {
      console.error(error);
      setStatusMessage("Error resuming task.");
    }
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto py-10 px-4">
      <div className="flex items-center mb-8">
        <Activity className="text-cyan-500 mr-3" size={32} />
        <h1 className="text-3xl font-bold text-white tracking-tight">
          DevFlow Dashboard
        </h1>
      </div>

      {!sessionData || sessionData.status === "completed" ? (
        <TaskForm onSubmit={handleStartTask} isLoading={loading} />
      ) : null}

      {loading && statusMessage && (
        <div className="mt-6 p-4 bg-blue-900/30 border border-blue-800 rounded text-blue-300 flex items-center animate-pulse">
          <Activity className="mr-3 animate-spin" size={18} />
          {statusMessage}
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
        <div className="mt-6 p-4 bg-green-900/30 border border-green-800 rounded text-green-400">
          ✓ {sessionData.message || statusMessage}
        </div>
      )}
    </div>
  );
}

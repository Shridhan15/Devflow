import { useState, useEffect } from "react";
import { Play } from "lucide-react";
import { FaGithub } from "react-icons/fa";

export default function TaskForm({ workspace, onSubmit, isLoading }) {
  const [task, setTask] = useState("");
  const [repoUrl, setRepoUrl] = useState("");

  const isNew = workspace === "NEW";
  // Stable identity: only reset the form when the selected workspace really changes,
  // not when the parent hands us a new object with the same contents.
  const workspaceKey = isNew ? "NEW" : workspace?.workspace_id;
  const workspaceRepo = isNew ? "" : workspace?.repo_url || "";

  useEffect(() => {
    setRepoUrl(workspaceRepo);
    setTask(""); // Clear task on workspace change
  }, [workspaceKey, workspaceRepo]);

  const canSubmit = !isLoading && task.trim() && repoUrl.trim();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit(task.trim(), repoUrl.trim());
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-gray-800 p-8 rounded-xl border border-gray-700 shadow-sm"
    >
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide">
          Target Repository
        </label>
        <div className="relative">
          <FaGithub
            className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500"
            size={18}
          />
          <input
            type="text"
            required
            readOnly={!isNew}
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/username/repo.git"
            className={`w-full bg-gray-900 border border-gray-700 rounded-lg py-3 pl-10 pr-4 text-white focus:outline-none focus:border-cyan-500 transition-colors ${
              !isNew ? "opacity-70 cursor-not-allowed" : ""
            }`}
          />
        </div>
      </div>

      <div className="mb-8">
        <label className="block text-sm font-semibold text-gray-300 mb-2 uppercase tracking-wide">
          Agent Task Directive
        </label>
        <textarea
          required
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Describe exactly what DevFlow should build, modify, or delete in this repository..."
          className="w-full bg-gray-900 border border-gray-700 rounded-lg p-4 text-white h-32 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all resize-y"
        />
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-3.5 px-4 rounded-lg flex items-center justify-center transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? (
          <span className="flex items-center">
            <span className="animate-spin mr-2">⚙️</span> Executing Agent
            Loop...
          </span>
        ) : (
          <>
            <Play size={18} className="mr-2" /> Dispatch Engineering Agent
          </>
        )}
      </button>
    </form>
  );
}

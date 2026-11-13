import { useState } from "react";
import { Play } from "lucide-react";

export default function TaskForm({ onSubmit, isLoading }) {
  const [task, setTask] = useState("");
  const [repoUrl, setRepoUrl] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(task, repoUrl);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-gray-800 p-6 rounded-lg shadow-md border border-gray-700"
    >
      <h2 className="text-xl font-semibold text-white mb-4">
        Start New Agent Task
      </h2>

      <div className="mb-4">
        <label className="block text-gray-400 mb-2 text-sm">
          GitHub Repository URL
        </label>
        <input
          type="text"
          required
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          placeholder="https://github.com/username/repo.git"
          className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white focus:outline-none focus:border-cyan-500"
        />
      </div>

      <div className="mb-4">
        <label className="block text-gray-400 mb-2 text-sm">
          Task Description
        </label>
        <textarea
          required
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g., Add a divide function that handles division by zero..."
          className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white h-24 focus:outline-none focus:border-cyan-500"
        />
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium py-2 px-4 rounded flex items-center justify-center transition-colors disabled:opacity-50"
      >
        {isLoading ? (
          "Executing Task..."
        ) : (
          <>
            <Play size={18} className="mr-2" /> Start DevFlow
          </>
        )}
      </button>
    </form>
  );
}

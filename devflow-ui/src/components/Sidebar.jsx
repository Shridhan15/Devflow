import { FolderGit2, Plus, TerminalSquare } from "lucide-react";
import { FaGithub } from "react-icons/fa";

export default function Sidebar({
  workspaces,
  activeWorkspace,
  onSelectWorkspace,
}) {
  return (
    <div className="w-72 bg-gray-900 border-r border-gray-800 h-screen flex flex-col">
      <div className="p-6 border-b border-gray-800 flex items-center">
        <TerminalSquare className="text-cyan-500 mr-3" size={28} />
        <h1 className="text-xl font-bold text-white tracking-tight">DevFlow</h1>
      </div>

      <div className="p-4">
        <button
          onClick={() => onSelectWorkspace("NEW")}
          className={`w-full flex items-center px-4 py-3 rounded-md transition-colors ${
            activeWorkspace === "NEW"
              ? "bg-cyan-900/40 text-cyan-400 border border-cyan-800/50"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700 border border-transparent"
          }`}
        >
          <Plus size={18} className="mr-2" />
          <span className="font-medium">New Workspace</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-2">
          Active Workspaces
        </h2>
        <div className="space-y-1">
          {workspaces.map((ws) => (
            <button
              key={ws.workspace_id}
              onClick={() => onSelectWorkspace(ws)}
              className={`w-full flex items-center px-3 py-2.5 rounded-md transition-colors text-sm ${
                activeWorkspace?.workspace_id === ws.workspace_id
                  ? "bg-gray-800 text-white border border-gray-700"
                  : "text-gray-400 hover:bg-gray-800/50 hover:text-gray-200 border border-transparent"
              }`}
            >
              <FolderGit2 size={16} className="mr-3 text-gray-500" />
              <div className="text-left truncate">
                <div className="truncate font-medium">{ws.workspace_id}</div>
                <div className="text-[10px] text-gray-500 truncate">
                  <FaGithub size={18} />
                  {ws.repo_url.replace("https://github.com/", "")}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

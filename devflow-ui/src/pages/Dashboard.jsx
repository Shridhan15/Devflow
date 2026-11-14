import { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import WorkspaceView from "../components/WorkspaceView";
import { getWorkspaces } from "../services/api";

export default function Dashboard() {
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWorkspace, setActiveWorkspace] = useState("NEW");

  const fetchWorkspaces = async () => {
    try {
      const data = await getWorkspaces();
      setWorkspaces(data);
      // Auto-select the first workspace if it exists and we're currently on NEW
      if (data.length > 0 && activeWorkspace === "NEW") {
        setActiveWorkspace(data[0]);
      }
    } catch (error) {
      console.error("Failed to load workspaces", error);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 font-sans selection:bg-cyan-900">
      <Sidebar
        workspaces={workspaces}
        activeWorkspace={activeWorkspace}
        onSelectWorkspace={setActiveWorkspace}
      />
      <WorkspaceView
        workspace={activeWorkspace}
        onWorkspaceCreated={fetchWorkspaces}
      />
    </div>
  );
}

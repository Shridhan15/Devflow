import { useState } from "react";
import { Check, X, GitPullRequest, Code2, AlertTriangle } from "lucide-react";

export default function ReviewPanel({ sessionData, onFeedback, isLoading }) {
  const [feedbackMsg, setFeedbackMsg] = useState("");

  if (!sessionData) return null;

  // Prefer the explicit stage from the backend; fall back to the question text.
  const isPRStage = sessionData.stage
    ? sessionData.stage === "pr_approval"
    : /\bPR\b/.test(sessionData.question || "");

  const files = sessionData.proposed_files || {};
  const fileNames = Object.keys(files);

  // path -> added | modified | deleted (cumulative across all rounds, from git)
  const statusMap = sessionData.file_status || {};
  const allChanged = Object.keys(statusMap).length
    ? Object.keys(statusMap)
    : fileNames;
  const deletedNames = allChanged.filter((n) => statusMap[n] === "deleted");

  const badgeStyles = {
    added: "bg-green-900/40 text-green-400 border-green-700/50",
    modified: "bg-yellow-900/30 text-yellow-400 border-yellow-700/50",
    deleted: "bg-red-900/40 text-red-400 border-red-700/50",
  };
  const StatusBadge = ({ name }) =>
    statusMap[name] ? (
      <span
        className={`ml-3 text-xs px-2 py-0.5 rounded border ${badgeStyles[statusMap[name]] || ""}`}
      >
        {statusMap[name]}
      </span>
    ) : null;

  const trimmed = feedbackMsg.trim();
  // The backend treats exactly "approve" as approval, so never send that as an edit request.
  const feedbackLooksLikeApproval = trimmed.toLowerCase() === "approve";

  // Approve ALWAYS sends the literal "approve", even if the textarea has text.
  const handleApprove = () => onFeedback("approve");

  // Stage 1: request changes with the typed text. Stage 2: abort.
  const handleReject = () => onFeedback(isPRStage ? "abort" : trimmed);

  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-xl mt-6 animate-in fade-in slide-in-from-bottom-4">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700">
        <div className="flex items-center space-x-3">
          <div
            className={`p-2 rounded-lg ${isPRStage ? "bg-purple-900/50" : "bg-blue-900/50"}`}
          >
            {isPRStage ? (
              <GitPullRequest className="text-purple-400" size={24} />
            ) : (
              <Code2 className="text-blue-400" size={24} />
            )}
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">
              {isPRStage
                ? "Stage 2: GitHub PR Authorization"
                : "Stage 1: Code Review"}
            </h2>
            <p className="text-sm text-gray-400">
              Human approval required to proceed.
            </p>
          </div>
        </div>
        <span className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 text-xs px-3 py-1.5 rounded-full font-medium flex items-center">
          <AlertTriangle size={14} className="mr-1.5" /> Awaiting Action
        </span>
      </div>

      <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700/50 mb-6">
        <p className="text-gray-200 font-medium">{sessionData.question}</p>
      </div>

      {/* Stage 1: full file contents */}
      {!isPRStage && fileNames.length > 0 && (
        <div className="mb-8">
          <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">
            Proposed Modifications
          </h3>
          {Object.entries(files).map(([filename, content]) => (
            <div
              key={filename}
              className="mb-4 rounded-lg overflow-hidden border border-gray-700"
            >
              <div className="bg-gray-800 px-4 py-2 text-sm font-mono text-gray-300 border-b border-gray-700 flex items-center">
                {filename}
                <StatusBadge name={filename} />
              </div>
              <pre className="bg-gray-950 p-4 overflow-x-auto text-sm text-green-400 font-mono">
                {content}
              </pre>
            </div>
          ))}
          {deletedNames.map((name) => (
            <div
              key={name}
              className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-2 text-sm font-mono text-red-300 flex items-center"
            >
              {name}
              <StatusBadge name={name} />
            </div>
          ))}
        </div>
      )}

      {/* Stage 2: just list what will be pushed */}
      {isPRStage && allChanged.length > 0 && (
        <div className="mb-8">
          <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">
            Files changed in this PR ({allChanged.length})
          </h3>
          <ul className="bg-gray-950 border border-gray-700 rounded-lg p-4 text-sm font-mono text-gray-300 space-y-2">
            {allChanged.map((name) => (
              <li key={name} className="flex items-center">
                {name}
                <StatusBadge name={name} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-col space-y-4">
        {!isPRStage && (
          <textarea
            value={feedbackMsg}
            onChange={(e) => setFeedbackMsg(e.target.value)}
            placeholder="Describe the changes you want, then click Request Changes. Click Approve to accept the code as-is."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-white h-20 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        )}

        <div className="flex space-x-4 pt-2">
          <button
            onClick={handleApprove}
            disabled={isLoading}
            className={`flex-1 text-white py-3 px-4 rounded-lg flex items-center justify-center font-medium transition-all shadow-lg hover:shadow-xl disabled:opacity-50 ${
              isPRStage
                ? "bg-purple-600 hover:bg-purple-500"
                : "bg-green-600 hover:bg-green-500"
            }`}
          >
            <Check size={18} className="mr-2" />
            {isPRStage ? "Authorize PR Creation" : "Approve Code Modifications"}
          </button>

          <button
            onClick={handleReject}
            disabled={
              isLoading ||
              (!isPRStage && (!trimmed || feedbackLooksLikeApproval))
            }
            className="flex-1 bg-red-600/10 text-red-500 border border-red-500/20 hover:bg-red-600 hover:text-white py-3 px-4 rounded-lg flex items-center justify-center font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X size={18} className="mr-2" />
            {isPRStage ? "Abort PR" : "Request Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Check, X, GitPullRequest, Code2, AlertTriangle } from "lucide-react";

export default function ReviewPanel({ sessionData, onFeedback, isLoading }) {
  const [feedbackMsg, setFeedbackMsg] = useState("");

  if (!sessionData) return null;

  // Determine which stage we are in based on the backend interrupt payload
  const isPRStage =
    sessionData.stage === "pr_approval" || sessionData.question?.includes("PR");

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

      {!isPRStage &&
        sessionData.proposed_files &&
        Object.keys(sessionData.proposed_files).length > 0 && (
          <div className="mb-8">
            <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">
              Proposed Modifications
            </h3>
            {Object.entries(sessionData.proposed_files).map(
              ([filename, content]) => (
                <div
                  key={filename}
                  className="mb-4 rounded-lg overflow-hidden border border-gray-700"
                >
                  <div className="bg-gray-800 px-4 py-2 text-sm font-mono text-gray-300 border-b border-gray-700">
                    {filename}
                  </div>
                  <pre className="bg-gray-950 p-4 overflow-x-auto text-sm text-green-400 font-mono">
                    {content}
                  </pre>
                </div>
              ),
            )}
          </div>
        )}

      <div className="flex flex-col space-y-4">
        {!isPRStage && (
          <textarea
            value={feedbackMsg}
            onChange={(e) => setFeedbackMsg(e.target.value)}
            placeholder="Request specific changes to the code (or leave blank to approve)..."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-white h-20 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
          />
        )}

        <div className="flex space-x-4 pt-2">
          <button
            onClick={() => onFeedback(feedbackMsg || "Approve")}
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
            onClick={() => onFeedback(feedbackMsg || "Abort/Reject")}
            disabled={isLoading || (!isPRStage && !feedbackMsg)}
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

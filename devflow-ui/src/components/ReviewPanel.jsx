import { useState } from "react";
import { Check, X, MessageSquare } from "lucide-react";

export default function ReviewPanel({ sessionData, onFeedback, isLoading }) {
  const [feedbackMsg, setFeedbackMsg] = useState("");

  if (!sessionData) return null;

  return (
    <div className="bg-gray-800 p-6 rounded-lg shadow-md border border-gray-700 mt-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-cyan-400">
          Human Approval Required
        </h2>
        <span className="bg-yellow-900 text-yellow-300 text-xs px-2 py-1 rounded border border-yellow-700">
          Awaiting Action
        </span>
      </div>

      <p className="text-gray-300 mb-6 bg-gray-900 p-3 rounded border border-gray-700">
        {sessionData.question}
      </p>

      {sessionData.proposed_files &&
        Object.keys(sessionData.proposed_files).length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-400 mb-2">
              Proposed File Changes:
            </h3>
            {Object.entries(sessionData.proposed_files).map(
              ([filename, content]) => (
                <div key={filename} className="mb-4">
                  <div className="bg-gray-700 px-3 py-1 text-sm font-mono text-gray-200 rounded-t border border-gray-600 border-b-0">
                    {filename}
                  </div>
                  <pre className="bg-gray-950 p-4 rounded-b border border-gray-700 overflow-x-auto text-sm text-green-400 font-mono">
                    {content}
                  </pre>
                </div>
              ),
            )}
          </div>
        )}

      <div className="flex flex-col space-y-3">
        <textarea
          value={feedbackMsg}
          onChange={(e) => setFeedbackMsg(e.target.value)}
          placeholder="Request changes (or leave blank to just approve)..."
          className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white h-16 focus:outline-none focus:border-cyan-500"
        />

        <div className="flex space-x-3">
          <button
            onClick={() => onFeedback(feedbackMsg || "Approve")}
            disabled={isLoading}
            className="flex-1 bg-green-600 hover:bg-green-500 text-white py-2 px-4 rounded flex items-center justify-center transition-colors disabled:opacity-50"
          >
            <Check size={18} className="mr-2" /> Approve & Continue
          </button>

          <button
            onClick={() => onFeedback(feedbackMsg || "Reject and retry")}
            disabled={isLoading || !feedbackMsg}
            className="flex-1 bg-red-600 hover:bg-red-500 text-white py-2 px-4 rounded flex items-center justify-center transition-colors disabled:opacity-50"
          >
            <X size={18} className="mr-2" /> Request Changes
          </button>
        </div>
      </div>
    </div>
  );
}

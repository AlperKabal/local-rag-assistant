import { useState, useRef, useEffect } from "react";

function Header({ chatName, activeConversationId, onRename }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef(null);

  const [showInfo, setShowInfo] = useState(false);
  const infoRef = useRef(null);
  function startEditing() {
    setEditValue(chatName || "");
    setIsEditing(true);
  }

  function submitRename() {
    setIsEditing(false);
    if (editValue.trim() && editValue !== chatName) {
      onRename(activeConversationId, editValue.trim());
    }
  }
  useEffect(() => {
    if (isEditing) inputRef.current?.focus();
  }, [isEditing]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (infoRef.current && !infoRef.current.contains(event.target)) {
        setShowInfo(false);
      }
    }
    if (showInfo) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showInfo]);

  return (
    <header className="flex items-center justify-center px-4 py-8 relative">
      <div className="flex items-center gap-2">
        {isEditing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={submitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitRename();
              if (e.key === "Escape") setIsEditing(false);
            }}
            className="text-lg font-medium text-center border-b border-blue-400 focus:outline-none px-1"
          />
        ) : (
          <h1 className="text-xl font-medium">
            {chatName
              ? chatName.length > 50
                ? chatName.slice(0, 50) + "..."
                : chatName
              : "New Chat"}
          </h1>
        )}

        {activeConversationId && !isEditing && (
          <button
            onClick={startEditing}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-blue-300"
          >
            <span className="text-sm">✎</span>
          </button>
        )}
      </div>

      <button
        onClick={() => setShowInfo(() => !showInfo)}
        className="absolute right-4 w-6 h-6 flex items-center justify-center rounded-full hover:bg-blue-500 bg-blue-300"
      >
        <span className="text-sm">i</span>
      </button>

      {showInfo && (
        <div
          className="animate-fade-slide-in absolute top-12 right-4 w-72 max-h-96 overflow-y-auto no-scrollbar bg-white border rounded-lg shadow-lg p-4 z-10"
          ref={infoRef}
        >
          <p className="text-lg font-bold text-gray-800 mb-2">
            Foundry RAG Assistant
          </p>

          <p className="text-xs text-gray-400 mb-3">
            An offline document Q&A assistant that answers questions using your
            local knowledge base — no internet connection required.
          </p>

          <p className="text-xs text-gray-400 mb-1">
            This assistant knows about:
          </p>
          <ul className="text-xs text-gray-400 list-disc list-inside space-y-0.5 mb-3">
            <li>What Foundry Local is and how it runs models on-device</li>
            <li>
              Its SDKs and supported languages (Python, JavaScript, C#, Rust)
            </li>
            <li>The CLI and local REST server</li>
            <li>Text embeddings and vector similarity search</li>
            <li>The model catalog and hardware acceleration (GPU/NPU/CPU)</li>
            <li>The Retrieval-Augmented Generation (RAG) pattern itself</li>
            <li>Prompt engineering basics for guiding model behavior</li>
          </ul>

          <div className="text-xs text-gray-400 space-y-1 border-t pt-2">
            <p>
              <span className="font-medium text-gray-500">Chat model:</span>{" "}
              Phi-3.5 Mini
            </p>
            <p>
              <span className="font-medium text-gray-500">
                Embedding model:
              </span>{" "}
              Qwen3 Embedding 0.6B
            </p>
            <p>
              <span className="font-medium text-gray-500">Runtime:</span>{" "}
              Microsoft Foundry Local
            </p>
          </div>
        </div>
      )}
    </header>
  );
}

export default Header;

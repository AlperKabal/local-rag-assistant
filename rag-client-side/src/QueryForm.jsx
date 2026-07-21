import { useState } from "react";

function QueryForm({ onSubmit }) {
  const [text, setText] = useState("");
  const handleChange = (e) => {
    setText(e.target.value);
    e.target.style.height = "auto"; // reset first, so it can shrink too
    e.target.style.height = Math.min(e.target.scrollHeight, 80) + "px"; // 160px ≈ max-h-40
  };
  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSubmit(text);
    setText("");
  };
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit(e);
    }
  };
  return (
    <form
      onSubmit={handleFormSubmit}
      className=" w-full flex items-center justify-center  gap-3 px-4 py-9 bg-blue-50"
    >
      <div className="flex  items-center justify-center gap-3 w-full max-w-2xl">
        <textarea
          id="queryForm"
          name="queryForm"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          rows={1}
          className="no-scrollbar flex-1 resize-none rounded-3xl bg-gray-200 px-4 py-2.5 max-h-20 overflow-y-auto border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-300 focus:bg-white transition-colors"
          required
        />
        <button
          type="submit"
          className="w-10 h-10 flex items-center justify-center rounded-full bg-blue-500 hover:bg-blue-600 active:bg-blue-700 transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="text-white text-lg">↑</span>
        </button>
      </div>
    </form>
  );
}
export default QueryForm;

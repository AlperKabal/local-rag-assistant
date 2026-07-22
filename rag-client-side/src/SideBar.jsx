function Sidebar({
  sidebarOpen,
  onToggleSidebar,
  conversations,
  onSelectConversation,
  onNewChat,
  activeConversationId,
  onDeleteConversation,
}) {
  if (!sidebarOpen) {
    // Collapsed: narrow icon strip
    return (
      <aside className="row-span-2 flex flex-col items-center gap-5 pt-6 border-r border-gray-500 h-full">
        <button onClick={onNewChat} className="w-6 h-6 mb-2">
          <img src="/locag.png" alt="App Icon" />
        </button>
        <button
          onClick={onToggleSidebar}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-blue-300"
        >
          <span className="text-sm ">→</span>
        </button>
        <button
          onClick={onNewChat}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-blue-300 "
        >
          <span className="text-lg">+</span>
        </button>
      </aside>
    );
  }

  // Expanded: full sidebar
  return (
    <aside className="no-scrollbar row-span-2 flex flex-col border-r overflow-y-auto overflow-x-hidden h-full">
      {/* Icon + name + collapse button */}
      <div className="flex items-center gap-2 px-4 py-4">
        <button
          onClick={onNewChat}
          className="flex items-center gap-2 hover:opacity-70 flex-1"
        >
          <img src="/locag.png" alt="App Icon" className="w-6 h-6" />
          <span className="font-semibold">LOCAG</span>
        </button>
        <button
          onClick={onToggleSidebar}
          className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-blue-300 shrink-0"
        >
          <span className="text-sm">←</span>
        </button>
      </div>

      {/* New Chat */}
      <button
        onClick={onNewChat}
        className={`mx-2 mb-2 px-4 py-2 text-left text-sm font-medium rounded-full ${
          activeConversationId === null ? "bg-gray-200" : "hover:bg-gray-200"
        }`}
      >
        <span className="text-base">+</span>
        <span>New Chat</span>
      </button>

      {/* Old chats list */}
      <div className="flex flex-col">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => onSelectConversation(conv.id)}
            className={`group flex items-center justify-between px-4 py-2 rounded-full mx-2 cursor-pointer ${
              conv.id === activeConversationId
                ? "bg-gray-300"
                : "hover:bg-gray-200"
            }`}
          >
            <span className="text-sm truncate">
              {conv.title || "Untitled chat"}
            </span>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteConversation(conv.id);
              }}
              className="opacity-0 group-hover:opacity-100 shrink-0 ml-2 px-1 hover:bg-gray-300 rounded-full text-red-500"
            >
              🗑
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default Sidebar;

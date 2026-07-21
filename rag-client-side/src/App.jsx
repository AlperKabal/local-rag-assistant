import Header from "./Header.jsx";
import { useEffect, useState } from "react";
import Sidebar from "./SideBar.jsx";
import QueryForm from "./QueryForm.jsx";
import ChatWindow from "./ChatWindow.jsx";

const API_BASE = "http://localhost:8000";

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [activeConversationTitle, setActiveConversationTitle] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAppLoading, setIsAppLoading] = useState(true);
  const [isSwitchingChat, setIsSwitchingChat] = useState(false);

  useEffect(() => {
    async function init() {
      await fetchConversations();
      setIsAppLoading(false);
    }
    init();
  }, []);

  async function fetchConversations() {
    const res = await fetch(`${API_BASE}/conversations`);
    const data = await res.json();
    setConversations(data);
  }

  function handleNewChat() {
    setActiveConversationId(null);
    setActiveConversationTitle(null);
    setMessages([]);
  }

  async function handleSelectConversation(conversationId) {
    setIsSwitchingChat(true);
    const res = await fetch(`${API_BASE}/conversations/${conversationId}`);
    const data = await res.json();
    setMessages(data);
    setActiveConversationId(conversationId);
    const conv = conversations.find((c) => c.id === conversationId);
    setActiveConversationTitle(conv?.title || null);
    setIsSwitchingChat(false);
  }

  async function handleSubmit(questionText) {
    setIsLoading(true);
    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: questionText,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: questionText,
          conversation_id: activeConversationId,
        }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          isError: data.error,
          created_at: new Date().toISOString(),
        },
      ]);

      if (!activeConversationId && data.conversation_id) {
        setActiveConversationId(data.conversation_id);
        setActiveConversationTitle(questionText.slice(0, 50));
        fetchConversations();
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Could not reach the server. Please try again.",
          isError: true,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteConversation(conversationId) {
    const confirmed = window.confirm(
      "Delete this conversation? This can't be undone.",
    );
    if (!confirmed) return;
    await fetch(`${API_BASE}/conversations/${conversationId}`, {
      method: "DELETE",
    });
    setConversations((prev) => prev.filter((c) => c.id !== conversationId));

    if (activeConversationId === conversationId) {
      handleNewChat();
    }
  }

  async function handleRename(conversationId, newTitle) {
    await fetch(`${API_BASE}/conversations/${conversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newTitle }),
    });
    setConversations((prev) =>
      prev.map((c) =>
        c.id === conversationId ? { ...c, title: newTitle } : c,
      ),
    );
    if (activeConversationId === conversationId) {
      setActiveConversationTitle(newTitle);
    }
  }
  if (isAppLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-white">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-gray-200 border-t-blue-500 rounded-full animate-spin"></div>
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`grid h-screen grid-rows-[60px_1fr] ${
        sidebarOpen ? "grid-cols-[260px_1fr]" : "grid-cols-[56px_1fr]"
      } transition-[grid-template-columns] duration-200 bg-blue-50`}
    >
      <Sidebar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        activeConversationId={activeConversationId}
        onDeleteConversation={handleDeleteConversation}
      />

      <Header
        chatName={activeConversationTitle}
        activeConversationId={activeConversationId}
        onRename={handleRename}
      />

      <main className="flex flex-col h-full overflow-hidden">
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          isSwitchingChat={isSwitchingChat}
        />
        <QueryForm onSubmit={handleSubmit} />
      </main>
    </div>
  );
}

export default App;

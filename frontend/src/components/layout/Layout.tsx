import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { FloatingAssistant } from "../ai/FloatingAssistant";

export function Layout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div>
        <Topbar />
        <main className="content">
          <Outlet />
        </main>
      </div>
      <FloatingAssistant />
    </div>
  );
}

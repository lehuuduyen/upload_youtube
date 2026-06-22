import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Youtube,
  PlusCircle,
  ListVideo,
  Clock,
  FileText,
  Menu,
  X,
  Zap,
  Music2,
  Film,
} from "lucide-react";
import { useState } from "react";
import clsx from "clsx";

const NAV = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/channels", icon: Youtube, label: "Kênh YouTube" },
  { to: "/new-job", icon: PlusCircle, label: "Tạo Video Mới" },
  { to: "/movie-downloader", icon: Film, label: "Tải Phim" },
  { to: "/auto-creator", icon: Zap, label: "Tạo Tự Động (AI)" },
  { to: "/queue", icon: ListVideo, label: "Hàng Chờ" },
  { to: "/schedules", icon: Clock, label: "Lịch Đăng" },
  { to: "/templates", icon: FileText, label: "Templates" },
  { to: "/tiktok", icon: Music2, label: "TikTok" },
];

export default function Layout({ children }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-20 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          "fixed lg:static inset-y-0 left-0 z-30 w-64 bg-gray-900 border-r border-gray-800 flex flex-col transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-800">
          <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
            <Youtube size={18} className="text-white" />
          </div>
          <div>
            <div className="font-bold text-white text-sm">YT Auto Upload</div>
            <div className="text-gray-500 text-xs">v1.0.0</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 space-y-1 px-3 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-red-600/20 text-red-400 border border-red-600/30"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          YouTube Data API v3
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar (mobile) */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-gray-900 border-b border-gray-800">
          <button onClick={() => setOpen(true)} className="text-gray-400 hover:text-white">
            <Menu size={22} />
          </button>
          <span className="font-semibold text-white">YT Auto Upload</span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

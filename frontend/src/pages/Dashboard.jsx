import { useQuery } from "react-query";
import { dashboardApi } from "../api";
import { Youtube, Upload, AlertCircle, CheckCircle, Clock, Zap } from "lucide-react";
import StatusBadge from "../components/StatusBadge";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";

function StatCard({ icon: Icon, label, value, sub, color = "text-red-400" }) {
  return (
    <div className="card flex items-start gap-4">
      <div className={`p-3 rounded-lg bg-gray-800 ${color}`}>
        <Icon size={22} />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-sm text-gray-400">{label}</div>
        {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

function QuotaBar({ name, used, limit, pct, canUpload }) {
  const barColor = pct > 80 ? "bg-red-500" : pct > 50 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-300 truncate">{name}</span>
          <span className="text-gray-500 ml-2 shrink-0">{used}/{limit} units</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className={`text-xs shrink-0 ${canUpload ? "text-green-400" : "text-red-400"}`}>
        {canUpload ? "OK" : "Hết quota"}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: stats } = useQuery("stats", dashboardApi.stats, { refetchInterval: 15000 });
  const { data: quotas } = useQuery("quotas", dashboardApi.quota, { refetchInterval: 30000 });
  const { data: activity } = useQuery("activity", () => dashboardApi.activity({ limit: 10 }), {
    refetchInterval: 10000,
  });
  const { data: upcoming } = useQuery("upcoming", () => dashboardApi.upcoming({ hours: 24 }));

  const jobs = stats?.jobs || {};
  const channels = stats?.channels || {};

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Youtube} label="Kênh đã xác thực" value={`${channels.authenticated || 0}/${channels.total || 0}`} color="text-red-400" />
        <StatCard icon={CheckCircle} label="Đã upload hôm nay" value={jobs.uploaded_today || 0} color="text-green-400" />
        <StatCard icon={Clock} label="Trong hàng chờ" value={jobs.by_status?.queued || 0} color="text-purple-400" />
        <StatCard icon={AlertCircle} label="Lỗi" value={jobs.failed || 0} color="text-red-500" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Quota overview */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <Zap size={16} className="text-yellow-400" /> Quota API hôm nay
            </h2>
            <span className="text-xs text-gray-500">max ~6 video/ngày/project</span>
          </div>
          {quotas?.length ? (
            <div className="space-y-3">
              {quotas.map((q) => (
                <QuotaBar key={q.id} {...q} />
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm">Chưa có kênh nào</p>
          )}
        </div>

        {/* Upcoming uploads */}
        <div className="card space-y-3">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <Clock size={16} className="text-purple-400" /> Sắp đăng (24h tới)
          </h2>
          {upcoming?.length ? (
            <div className="space-y-2">
              {upcoming.map((j) => (
                <div key={j.id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-300 truncate">{j.title || `Job #${j.id}`}</span>
                  <span className="text-gray-500 shrink-0 ml-2">
                    {j.upload_at ? new Date(j.upload_at).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }) : "—"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm">Không có video nào được lên lịch</p>
          )}
        </div>
      </div>

      {/* Activity log */}
      <div className="card">
        <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
          <Upload size={16} className="text-blue-400" /> Hoạt động gần đây
        </h2>
        {activity?.length ? (
          <div className="divide-y divide-gray-800">
            {activity.map((j) => (
              <div key={j.id} className="py-3 flex items-center gap-3">
                <StatusBadge status={j.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{j.title || `Job #${j.id}`}</div>
                  {j.error_message && (
                    <div className="text-xs text-red-400 truncate">{j.error_message}</div>
                  )}
                </div>
                <div className="text-xs text-gray-600 shrink-0">
                  {j.updated_at
                    ? formatDistanceToNow(new Date(j.updated_at), { addSuffix: true, locale: vi })
                    : "—"}
                </div>
                {j.youtube_url && (
                  <a
                    href={j.youtube_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-red-400 hover:text-red-300 shrink-0"
                  >
                    Xem ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 text-sm">Chưa có hoạt động nào</p>
        )}
      </div>
    </div>
  );
}

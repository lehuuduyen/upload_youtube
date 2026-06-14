import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { channelsApi } from "../api";
import { Key } from "lucide-react";
import { Plus, Trash2, Link, Unlink, RefreshCw, Youtube } from "lucide-react";

const TIMEZONES = [
  "Asia/Ho_Chi_Minh",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Tokyo",
  "UTC",
  "America/New_York",
  "America/Phoenix",
  "Europe/London",
];

const PRIVACY_OPTIONS = [
  { value: "private", label: "Private" },
  { value: "unlisted", label: "Unlisted" },
  { value: "public", label: "Public" },
];

function ChannelCard({ channel, onOAuth, onRevoke, onDelete, onResetQuota }) {
  const pct = Math.round((channel.quota_used ?? channel.daily_quota_used) / channel.daily_quota_limit * 100);
  const barColor = pct > 80 ? "bg-red-500" : pct > 50 ? "bg-yellow-500" : "bg-green-500";

  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center ${channel.is_authenticated ? "bg-red-600" : "bg-gray-700"}`}>
            <Youtube size={20} className="text-white" />
          </div>
          <div>
            <div className="font-semibold text-white">{channel.name}</div>
            <div className="text-xs text-gray-500">{channel.channel_id || "Chưa xác thực"}</div>
          </div>
        </div>
        <span className={`badge text-xs ${channel.is_authenticated ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-500"}`}>
          {channel.is_authenticated ? "Đã kết nối" : "Chưa kết nối"}
        </span>
      </div>

      {/* Quota bar */}
      <div>
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Quota hôm nay</span>
          <span>{channel.daily_quota_used}/{channel.daily_quota_limit} units (~{Math.floor(channel.quota_remaining / 1600)} video)</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div className={`h-full ${barColor} rounded-full`} style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
        <span>Timezone: <span className="text-gray-300">{channel.default_timezone}</span></span>
        <span>Privacy: <span className="text-gray-300">{channel.default_privacy}</span></span>
        <span>Interval: <span className="text-gray-300">{channel.min_upload_interval_minutes}m</span></span>
        <span>
          {channel.last_upload_at
            ? `Upload: ${new Date(channel.last_upload_at).toLocaleDateString("vi-VN")}`
            : "Chưa upload"}
        </span>
      </div>

      <div className="flex gap-2 flex-wrap">
        {channel.is_authenticated ? (
          <button onClick={() => onRevoke(channel.id)} className="btn-ghost text-xs">
            <Unlink size={14} /> Huỷ kết nối
          </button>
        ) : (
          <button onClick={() => onOAuth(channel.id)} className="btn-primary text-xs">
            <Link size={14} /> Kết nối OAuth2
          </button>
        )}
        <button onClick={() => onResetQuota(channel.id)} className="btn-ghost text-xs">
          <RefreshCw size={14} /> Reset quota
        </button>
        <button onClick={() => onDelete(channel.id)} className="btn-danger text-xs ml-auto">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

function AddChannelModal({ onClose, onCreated }) {
  const { register, handleSubmit } = useForm({
    defaultValues: { default_timezone: "Asia/Ho_Chi_Minh", default_privacy: "private", min_upload_interval_minutes: 30 },
  });
  const { data: secretFiles = [] } = useQuery("secret-files", channelsApi.listSecretFiles);
  const { mutate, isLoading } = useMutation(channelsApi.create, {
    onSuccess: (data) => { toast.success("Đã tạo kênh!"); onCreated(data); },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white">Thêm kênh YouTube</h2>
        <form onSubmit={handleSubmit(mutate)} className="space-y-3">
          <div>
            <label className="label">Tên kênh *</label>
            <input className="input" {...register("name", { required: true })} placeholder="Kênh của tôi" />
          </div>
          <div>
            <label className="label">Mô tả</label>
            <input className="input" {...register("description")} placeholder="Tuỳ chọn" />
          </div>
          <div>
            <label className="label flex items-center gap-1"><Key size={12} /> Google OAuth App (client secrets)</label>
            <select className="input" {...register("client_secrets_file")}>
              {secretFiles.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <p className="text-xs text-gray-600 mt-1">Mỗi kênh dùng 1 Google Cloud project riêng</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Timezone</label>
              <select className="input" {...register("default_timezone")}>
                {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Privacy mặc định</label>
              <select className="input" {...register("default_privacy")}>
                {PRIVACY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Khoảng cách tối thiểu (phút)</label>
            <input type="number" className="input" {...register("min_upload_interval_minutes")} min={0} />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Huỷ</button>
            <button type="submit" disabled={isLoading} className="btn-primary flex-1">
              {isLoading ? "Đang tạo..." : "Tạo kênh"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Channels() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: channels = [], isLoading } = useQuery("channels", channelsApi.list);

  const mutOAuth = useMutation(channelsApi.startOAuth, {
    onSuccess: ({ auth_url }) => { window.location.href = auth_url; },
    onError: (e) => toast.error(e.message),
  });
  const mutRevoke = useMutation(channelsApi.revokeOAuth, {
    onSuccess: () => { toast.success("Đã huỷ kết nối"); qc.invalidateQueries("channels"); },
  });
  const mutDelete = useMutation(channelsApi.delete, {
    onSuccess: () => { toast.success("Đã xóa kênh"); qc.invalidateQueries("channels"); },
  });
  const mutResetQuota = useMutation(channelsApi.resetQuota, {
    onSuccess: () => { toast.success("Đã reset quota"); qc.invalidateQueries("channels"); },
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Kênh YouTube</h1>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          <Plus size={18} /> Thêm kênh
        </button>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Đang tải...</div>
      ) : channels.length === 0 ? (
        <div className="card text-center py-12 text-gray-500">
          <Youtube size={40} className="mx-auto mb-3 opacity-30" />
          <p>Chưa có kênh nào. Thêm kênh để bắt đầu!</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {channels.map(c => (
            <ChannelCard
              key={c.id}
              channel={c}
              onOAuth={(id) => mutOAuth.mutate(id)}
              onRevoke={(id) => { if (confirm("Huỷ kết nối OAuth2?")) mutRevoke.mutate(id); }}
              onDelete={(id) => { if (confirm("Xóa kênh này?")) mutDelete.mutate(id); }}
              onResetQuota={(id) => mutResetQuota.mutate(id)}
            />
          ))}
        </div>
      )}

      {showAdd && (
        <AddChannelModal
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); qc.invalidateQueries("channels"); }}
        />
      )}
    </div>
  );
}

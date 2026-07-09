import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import toast from "react-hot-toast";
import { queueApi, channelsApi, mediaApi, apiUrl } from "../api";
import StatusBadge from "../components/StatusBadge";
import { RefreshCw, Trash2, Play, X, Upload, ExternalLink, ChevronDown, ChevronUp, Eye, CheckCircle, XCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { vi } from "date-fns/locale";

function VideoPreviewModal({ jobId, title, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-gray-900 rounded-xl overflow-hidden max-w-sm w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <span className="text-white font-medium text-sm truncate">{title || `Job #${jobId}`}</span>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X size={18} /></button>
        </div>
        <video
          className="w-full max-h-[70vh]"
          controls
          autoPlay
          src={apiUrl(`/media/preview/${jobId}`)}
        />
      </div>
    </div>
  );
}

const STATUS_FILTERS = [
  { value: "", label: "Tất cả" },
  { value: "pending", label: "Chờ" },
  { value: "downloading", label: "Đang tải" },
  { value: "processing", label: "Xử lý" },
  { value: "ready", label: "Sẵn sàng" },
  { value: "queued", label: "Trong hàng" },
  { value: "uploading", label: "Đang upload" },
  { value: "uploaded", label: "Đã upload" },
  { value: "failed", label: "Lỗi" },
];

function ProgressBar({ value }) {
  return (
    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
      <div
        className="h-full bg-red-500 rounded-full transition-all duration-500"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function JobRow({ job, onRetry, onCancel, onDelete, onUploadNow, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  return (
    <>
    {previewing && <VideoPreviewModal jobId={job.id} title={job.title} onClose={() => setPreviewing(false)} />}
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <div className="p-4 flex items-start gap-3">
        <StatusBadge status={job.status} className="mt-0.5 shrink-0" />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-medium text-white truncate">{job.title || `Job #${job.id}`}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                #{job.id} · {job.video_quality} · {job.output_format}
                {job.upload_at && (() => {
                  const d = new Date(job.upload_at + "Z");
                  const phoenix = d.toLocaleString("en-US", {
                    timeZone: "America/Phoenix",
                    month: "numeric", day: "numeric",
                    hour: "2-digit", minute: "2-digit", hour12: false,
                  });
                  return ` · 🕐 ${phoenix} (Phoenix)`;
                })()}
              </div>
            </div>
            <div className="text-xs text-gray-600 shrink-0">
              {job.updated_at ? formatDistanceToNow(new Date(job.updated_at), { addSuffix: true, locale: vi }) : ""}
            </div>
          </div>

          {(job.status === "downloading" || job.status === "processing" || job.status === "uploading") && (
            <div className="mt-2">
              <ProgressBar value={job.progress} />
              <div className="text-xs text-gray-500 mt-1">{job.progress?.toFixed(1)}%</div>
            </div>
          )}

          {job.error_message && (
            <div className="text-xs text-red-400 mt-1 truncate">{job.error_message}</div>
          )}

          {job.youtube_url && (
            <a href={job.youtube_url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-red-400 hover:text-red-300 mt-1 inline-flex items-center gap-1">
              <ExternalLink size={12} /> Xem trên YouTube
            </a>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {/* Preview */}
          {job.status === "ready" && (
            <button onClick={() => setPreviewing(true)} className="btn-ghost p-2 text-purple-400" title="Xem trước video">
              <Eye size={14} />
            </button>
          )}
          {/* Review: approve / reject */}
          {job.status === "ready" && job.review_status === "pending" && (
            <>
              <button onClick={() => onApprove(job.id)} className="btn-ghost p-2 text-green-400" title="Duyệt & Upload">
                <CheckCircle size={14} />
              </button>
              <button onClick={() => onReject(job.id)} className="btn-ghost p-2 text-red-400" title="Từ chối">
                <XCircle size={14} />
              </button>
            </>
          )}
          {/* Upload now — video đang chờ (kể cả chờ lịch) hoặc đã ready, trừ khi chờ duyệt */}
          {["pending", "queued", "ready"].includes(job.status) && job.review_status !== "pending" && (
            <button onClick={() => onUploadNow(job.id)} className="btn-ghost p-2 text-green-400"
              title={job.status === "ready" ? "Upload ngay" : "Bỏ qua lịch chờ — xử lý & upload ngay"}>
              <Upload size={14} />
            </button>
          )}
          {/* Retry */}
          {["failed", "cancelled", "queued"].includes(job.status) && (
            <button onClick={() => onRetry(job.id)} className="btn-ghost p-2 text-blue-400" title="Chạy lại">
              <RefreshCw size={14} />
            </button>
          )}
          {!["uploaded", "uploading", "cancelled"].includes(job.status) && (
            <button onClick={() => onCancel(job.id)} className="btn-ghost p-2 text-yellow-500" title="Huỷ">
              <X size={14} />
            </button>
          )}
          <button onClick={() => onDelete(job.id)} className="btn-ghost p-2 text-red-500" title="Xóa">
            <Trash2 size={14} />
          </button>
          <button onClick={() => setExpanded(e => !e)} className="btn-ghost p-2 text-gray-500">
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-800 bg-gray-950 p-4 space-y-2">
          {job.auto_topic && <div className="text-xs text-blue-400">🤖 Auto-created: {job.auto_topic}</div>}
          {job.platform && job.platform !== "youtube" && (
            <div className="text-xs text-pink-400">Platform: {job.platform}</div>
          )}
          {job.review_status && job.review_status !== "auto" && (
            <div className="text-xs text-gray-500">
              Review: <span className={job.review_status === "approved" ? "text-green-400" : job.review_status === "rejected" ? "text-red-400" : "text-yellow-400"}>
                {job.review_status}
              </span>
            </div>
          )}
          {job.video_url && <div className="text-xs text-gray-500">Video: <span className="text-gray-300 truncate">{job.video_url}</span></div>}
          {job.music_url && <div className="text-xs text-gray-500">Nhạc: <span className="text-gray-300 truncate">{job.music_url}</span></div>}
          {job.tiktok_url && (
            <a href={job.tiktok_url} target="_blank" rel="noopener noreferrer"
              className="text-xs text-pink-400 hover:text-pink-300 inline-flex items-center gap-1">
              <ExternalLink size={12} /> Xem trên TikTok
            </a>
          )}
          {job.log && (
            <pre className="text-xs text-gray-600 bg-gray-900 rounded p-3 overflow-x-auto max-h-48 whitespace-pre-wrap">
              {job.log}
            </pre>
          )}
        </div>
      )}
    </div>
    </>
  );
}

export default function Queue() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");

  const { data: channels = [] } = useQuery("channels", channelsApi.list);
  const { data, isLoading, refetch } = useQuery(
    ["queue", statusFilter, channelFilter],
    () => queueApi.list({ status: statusFilter || undefined, channel_id: channelFilter || undefined, limit: 100 }),
    { refetchInterval: 5000 }
  );

  const mutRetry = useMutation(queueApi.retry, {
    onSuccess: () => { toast.success("Đã đặt lại job"); qc.invalidateQueries("queue"); },
  });
  const mutCancel = useMutation(queueApi.cancel, {
    onSuccess: () => { toast.success("Đã huỷ job"); qc.invalidateQueries("queue"); },
  });
  const mutDelete = useMutation(queueApi.delete, {
    onSuccess: () => { toast.success("Đã xoá job"); qc.invalidateQueries("queue"); },
  });
  const mutUploadNow = useMutation(queueApi.uploadNow, {
    onSuccess: () => { toast.success("Đang upload..."); qc.invalidateQueries("queue"); },
    onError: (e) => toast.error(e.message),
  });
  const mutApprove = useMutation(mediaApi.approve, {
    onSuccess: () => { toast.success("Đã duyệt, đang upload..."); qc.invalidateQueries("queue"); },
    onError: (e) => toast.error(e.message),
  });
  const mutReject = useMutation(mediaApi.reject, {
    onSuccess: () => { toast.success("Đã từ chối"); qc.invalidateQueries("queue"); },
    onError: (e) => toast.error(e.message),
  });
  const mutCleanup = useMutation(queueApi.cleanupUploaded, {
    onSuccess: (res) => { toast.success(res.message || "Đã dọn file"); qc.invalidateQueries("queue"); },
    onError: (e) => toast.error(e.message),
  });

  const jobs = data?.items || [];

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Hàng Chờ Upload</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">{data?.total || 0} jobs</span>
          <button
            onClick={() => {
              if (window.confirm("Xoá file video (gốc + đã xử lý) của tất cả job đã upload để nhẹ ổ đĩa?")) {
                mutCleanup.mutate();
              }
            }}
            disabled={mutCleanup.isLoading}
            className="btn-ghost p-2 text-gray-400 hover:text-red-400"
            title="Dọn file video đã upload"
          >
            <Trash2 size={16} />
          </button>
          <button onClick={() => refetch()} className="btn-ghost p-2">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select className="input w-auto" value={channelFilter} onChange={e => setChannelFilter(e.target.value)}>
          <option value="">Tất cả kênh</option>
          {channels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div className="flex gap-1 flex-wrap">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === f.value
                  ? "bg-red-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Đang tải...</div>
      ) : jobs.length === 0 ? (
        <div className="card text-center py-10 text-gray-500">Không có job nào</div>
      ) : (
        <div className="space-y-2">
          {jobs.map(j => (
            <JobRow
              key={j.id}
              job={j}
              onRetry={(id) => mutRetry.mutate(id)}
              onCancel={(id) => { if (confirm("Huỷ job này?")) mutCancel.mutate(id); }}
              onDelete={(id) => { if (confirm("Xóa job?")) mutDelete.mutate(id); }}
              onUploadNow={(id) => mutUploadNow.mutate(id)}
              onApprove={(id) => mutApprove.mutate(id)}
              onReject={(id) => { if (confirm("Từ chối và không upload?")) mutReject.mutate(id); }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

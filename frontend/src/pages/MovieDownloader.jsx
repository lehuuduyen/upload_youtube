import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import {
  Film, Search, Upload, Trash2, Cookie, CheckCircle, AlertCircle,
  Clock, Tag, Youtube, ChevronDown, ChevronUp, Loader2,
} from "lucide-react";
import { channelsApi, downloadsApi } from "../api";

const QUALITY_OPTIONS = ["best", "4k", "1080p", "720p", "480p"];
const PRIVACY_OPTIONS = [
  { value: "private", label: "Private" },
  { value: "unlisted", label: "Unlisted" },
  { value: "public", label: "Public" },
];

function formatDuration(sec) {
  if (!sec) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (!bytes) return "—";
  if (bytes > 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  return `${(bytes / 1e6).toFixed(0)} MB`;
}

export default function MovieDownloader() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const cookieInputRef = useRef(null);

  const [url, setUrl] = useState("");
  const [videoInfo, setVideoInfo] = useState(null);
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Form state
  const [channelId, setChannelId] = useState("");
  const [quality, setQuality] = useState("1080p");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [privacyStatus, setPrivacyStatus] = useState("private");
  const [uploadMode, setUploadMode] = useState("manual");

  const { data: channels = [] } = useQuery("channels", channelsApi.list);
  const { data: cookieStatus, refetch: refetchCookies } = useQuery(
    "cookie-status",
    downloadsApi.getCookiesStatus,
    { refetchOnWindowFocus: false }
  );

  const fetchInfo = async () => {
    if (!url.trim()) return;
    setFetchingInfo(true);
    setVideoInfo(null);
    try {
      const info = await downloadsApi.getInfo(url.trim());
      setVideoInfo(info);
      if (info.title) setTitle(info.title);
    } catch (e) {
      toast.error(`Không lấy được thông tin: ${e.message}`);
    } finally {
      setFetchingInfo(false);
    }
  };

  const handleUploadCookies = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await downloadsApi.uploadCookies(file);
      toast.success("Đã lưu cookies.txt");
      refetchCookies();
    } catch (err) {
      toast.error(err.message);
    }
    e.target.value = "";
  };

  const handleDeleteCookies = async () => {
    try {
      await downloadsApi.deleteCookies();
      toast.success("Đã xóa cookies.txt");
      refetchCookies();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const submitMutation = useMutation(downloadsApi.createJob, {
    onSuccess: (data) => {
      toast.success(`Job #${data.id} đã tạo — ${data.message}`);
      navigate("/queue");
    },
    onError: (e) => toast.error(e.message),
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!channelId) { toast.error("Chọn kênh YouTube"); return; }
    if (!url.trim()) { toast.error("Nhập URL video"); return; }

    submitMutation.mutate({
      channel_id: parseInt(channelId),
      video_url: url.trim(),
      video_quality: quality,
      title: title || undefined,
      description: description || undefined,
      tags: tags ? tags.split(",").map((t) => t.trim()).filter(Boolean) : undefined,
      privacy_status: privacyStatus,
      upload_mode: uploadMode,
      output_format: "original",
      mute_original: false,
    });
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Film size={24} className="text-red-400" /> Tải Phim
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Dán URL phim từ bất kỳ site nào — yt-dlp sẽ tự download và đưa vào hàng chờ upload YouTube.
        </p>
      </div>

      {/* Cookies.txt panel */}
      <div className="card space-y-3">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Cookie size={16} className="text-yellow-400" /> Cookies (bypass Cloudflare)
        </h3>
        <p className="text-xs text-gray-400">
          Nếu site bị Cloudflare chặn hoặc cần đăng nhập, export cookies bằng extension{" "}
          <span className="text-yellow-300">"Get cookies.txt LOCALLY"</span> rồi upload lên đây.
        </p>
        <div className="flex items-center gap-3">
          {cookieStatus?.exists ? (
            <>
              <span className="flex items-center gap-1.5 text-green-400 text-sm">
                <CheckCircle size={14} /> cookies.txt ({cookieStatus.size_kb} KB)
              </span>
              <button
                onClick={handleDeleteCookies}
                className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 border border-red-800 rounded px-2 py-1"
              >
                <Trash2 size={12} /> Xóa
              </button>
            </>
          ) : (
            <span className="flex items-center gap-1.5 text-gray-500 text-sm">
              <AlertCircle size={14} /> Chưa có cookies.txt
            </span>
          )}
          <button
            onClick={() => cookieInputRef.current?.click()}
            className="ml-auto flex items-center gap-1.5 text-sm bg-yellow-600/20 hover:bg-yellow-600/30 text-yellow-300 border border-yellow-700/40 rounded-lg px-3 py-1.5 transition-colors"
          >
            <Upload size={14} /> Upload cookies.txt
          </button>
          <input
            ref={cookieInputRef}
            type="file"
            accept=".txt"
            className="hidden"
            onChange={handleUploadCookies}
          />
        </div>
      </div>

      {/* URL input */}
      <div className="card space-y-3">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Search size={16} className="text-red-400" /> URL Video / Phim
        </h3>
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchInfo()}
            placeholder="https://example.com/movie..."
            className="input flex-1"
          />
          <button
            onClick={fetchInfo}
            disabled={fetchingInfo || !url.trim()}
            className="btn-primary flex items-center gap-2 whitespace-nowrap"
          >
            {fetchingInfo ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Lấy Info
          </button>
        </div>

        {/* Video info preview */}
        {videoInfo && (
          <div className="flex gap-3 p-3 bg-gray-800/60 rounded-lg border border-gray-700">
            {videoInfo.thumbnail && (
              <img
                src={videoInfo.thumbnail}
                alt=""
                className="w-24 h-16 object-cover rounded flex-shrink-0"
              />
            )}
            <div className="min-w-0 space-y-1">
              <p className="text-white font-medium text-sm truncate">{videoInfo.title}</p>
              <p className="text-gray-400 text-xs">{videoInfo.uploader}</p>
              <div className="flex gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock size={11} /> {formatDuration(videoInfo.duration)}
                </span>
                {videoInfo.formats?.length > 0 && (
                  <span>
                    {videoInfo.formats.filter((f) => f.height).slice(-1)[0]?.height}p max
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Main form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="card space-y-4">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Youtube size={16} className="text-red-400" /> Cài đặt Upload
          </h3>

          {/* Channel */}
          <div>
            <label className="label">Kênh YouTube *</label>
            <select
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              className="input"
              required
            >
              <option value="">-- Chọn kênh --</option>
              {channels.map((ch) => (
                <option key={ch.id} value={ch.id}>{ch.name}</option>
              ))}
            </select>
          </div>

          {/* Quality */}
          <div>
            <label className="label">Chất lượng tải</label>
            <div className="flex gap-2 flex-wrap">
              {QUALITY_OPTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuality(q)}
                  className={`px-3 py-1 rounded text-sm border transition-colors ${
                    quality === q
                      ? "bg-red-600/20 border-red-600/50 text-red-300"
                      : "border-gray-700 text-gray-400 hover:border-gray-500"
                  }`}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* Upload mode */}
          <div>
            <label className="label">Sau khi tải xong</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="uploadMode"
                  value="manual"
                  checked={uploadMode === "manual"}
                  onChange={() => setUploadMode("manual")}
                  className="accent-red-500"
                />
                <span className="text-sm text-gray-300">Dừng lại, xem trước rồi mới up</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="uploadMode"
                  value="immediate"
                  checked={uploadMode === "immediate"}
                  onChange={() => setUploadMode("immediate")}
                  className="accent-red-500"
                />
                <span className="text-sm text-gray-300">Upload YouTube ngay</span>
              </label>
            </div>
          </div>
        </div>

        {/* Advanced: metadata */}
        <div className="card space-y-3">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between text-sm font-medium text-gray-300 hover:text-white transition-colors"
          >
            <span className="flex items-center gap-2">
              <Tag size={15} className="text-red-400" /> Metadata YouTube (tuỳ chọn)
            </span>
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showAdvanced && (
            <div className="space-y-3 pt-2 border-t border-gray-800">
              <div>
                <label className="label">Tiêu đề</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Để trống = lấy tiêu đề gốc"
                  className="input"
                />
              </div>
              <div>
                <label className="label">Mô tả</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="input resize-none"
                  placeholder="Mô tả video..."
                />
              </div>
              <div>
                <label className="label">Tags (cách nhau bằng dấu phẩy)</label>
                <input
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="phim, hành động, 2024"
                  className="input"
                />
              </div>
              <div>
                <label className="label">Quyền riêng tư</label>
                <select
                  value={privacyStatus}
                  onChange={(e) => setPrivacyStatus(e.target.value)}
                  className="input"
                >
                  {PRIVACY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={submitMutation.isLoading || !url.trim() || !channelId}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
        >
          {submitMutation.isLoading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Film size={18} />
          )}
          {submitMutation.isLoading ? "Đang tạo job..." : "Tải Phim & Thêm Vào Hàng Chờ"}
        </button>
      </form>
    </div>
  );
}

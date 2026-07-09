import { useState, useRef } from "react";
import { useQuery, useMutation } from "react-query";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { channelsApi, downloadsApi, templatesApi, mediaApi, trendingApi, apiUrl } from "../api";
import { Search, Music, Video, Settings2, FileText, Zap, Clock, Upload, Film, X, RefreshCw, FolderOpen, TrendingUp, ChevronDown, ChevronUp, Eye, RotateCcw, CalendarClock, CheckSquare, Plus } from "lucide-react";

const QUALITY_OPTIONS = ["best", "4k", "1080p", "720p", "480p"];
const FORMAT_OPTIONS = [
  { value: "16:9", label: "16:9 (Ngang)" },
  { value: "9:16", label: "9:16 (Dọc / Shorts)" },
  { value: "1:1", label: "1:1 (Vuông)" },
  { value: "original", label: "Giữ nguyên" },
];
const PRIVACY_OPTIONS = [
  { value: "private", label: "Private" },
  { value: "unlisted", label: "Unlisted" },
  { value: "public", label: "Public" },
];

function Section({ icon: Icon, title, children }) {
  return (
    <div className="card space-y-4">
      <h3 className="font-semibold text-white flex items-center gap-2">
        <Icon size={16} className="text-red-400" /> {title}
      </h3>
      {children}
    </div>
  );
}

function MultiClipUpload({ clips, onAdd, onRemove, uploading, setUploading }) {
  const inputRef = useRef(null);
  const [showBrowser, setShowBrowser] = useState(false);
  const { data: serverFiles = [], isLoading: loadingFiles, refetch } = useQuery(
    "media-video-files",
    mediaApi.listVideos,
    { enabled: showBrowser }
  );

  const handleFiles = async (files) => {
    for (const file of Array.from(files)) {
      setUploading(true);
      try {
        const res = await mediaApi.uploadVideo(file);
        onAdd({ path: res.path, name: file.name, size_mb: res.size_mb });
        toast.success(`Đã upload: ${file.name}`);
      } catch (e) {
        toast.error(`${file.name}: ${e.message}`);
      } finally {
        setUploading(false);
      }
    }
  };

  const handlePickServer = (f) => {
    const alreadyAdded = clips.some(c => c.path === f.path);
    if (alreadyAdded) {
      toast.error("File này đã được thêm rồi");
      return;
    }
    onAdd({ path: f.path, name: f.filename, size_mb: f.size_mb });
    toast.success(`Đã thêm: ${f.filename}`);
  };

  return (
    <div className="space-y-2">
      {clips.length > 0 && (
        <div className="space-y-1">
          {clips.map((clip, i) => (
            <div key={i} className="flex items-center gap-2 p-2 bg-gray-800 rounded border border-gray-700">
              <span className="text-gray-500 text-xs w-5 text-center">{i + 1}</span>
              <Film size={14} className="text-blue-400 flex-shrink-0" />
              <span className="text-sm text-gray-300 truncate flex-1">{clip.name}</span>
              <span className="text-gray-600 text-xs flex-shrink-0">{clip.size_mb}MB</span>
              <button type="button" onClick={() => onRemove(i)}
                className="text-gray-500 hover:text-red-400 flex-shrink-0">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <div
          onClick={() => !uploading && inputRef.current?.click()}
          className={`flex items-center gap-3 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors flex-1 ${uploading
              ? "border-gray-700 opacity-50 cursor-not-allowed"
              : "border-gray-700 hover:border-blue-600 hover:bg-blue-950/20"
            }`}
        >
          {uploading
            ? <RefreshCw size={16} className="animate-spin text-gray-400" />
            : <Upload size={16} className="text-gray-500" />}
          <span className="text-sm text-gray-500">
            {uploading ? "Đang upload..." : "Upload clip mới (MP4/MOV)"}
          </span>
        </div>
        <button
          type="button"
          onClick={() => { setShowBrowser(v => !v); if (!showBrowser) refetch(); }}
          className="flex items-center gap-2 px-3 py-2 border border-gray-600 rounded-lg text-sm text-gray-400 hover:border-gray-400 hover:text-white transition-colors"
        >
          <FolderOpen size={15} />
          File có sẵn
        </button>
      </div>

      {showBrowser && (
        <div className="border border-gray-700 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
            <span className="text-xs text-gray-400 font-medium">File đã upload trên server</span>
            <button type="button" onClick={() => setShowBrowser(false)} className="text-gray-500 hover:text-gray-300">
              <X size={14} />
            </button>
          </div>
          {loadingFiles ? (
            <div className="p-4 text-center text-gray-500 text-sm">Đang tải...</div>
          ) : serverFiles.length === 0 ? (
            <div className="p-4 text-center text-gray-500 text-sm">Chưa có file nào trên server</div>
          ) : (
            <div className="max-h-48 overflow-y-auto divide-y divide-gray-800">
              {serverFiles.map((f) => {
                const added = clips.some(c => c.path === f.path);
                return (
                  <button
                    key={f.path}
                    type="button"
                    onClick={() => handlePickServer(f)}
                    disabled={added}
                    className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${added
                        ? "opacity-40 cursor-not-allowed"
                        : "hover:bg-gray-700 cursor-pointer"
                      }`}
                  >
                    <Film size={14} className="text-blue-400 flex-shrink-0" />
                    <span className="text-sm text-gray-300 truncate flex-1">{f.filename}</span>
                    <span className="text-gray-600 text-xs flex-shrink-0">{f.size_mb}MB</span>
                    {added && <span className="text-green-500 text-xs">✓</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.mkv,.webm,.avi"
        multiple
        className="hidden"
        onChange={e => handleFiles(e.target.files)}
      />
    </div>
  );
}

function OutroBrowser({ onPick, onClose }) {
  const { data: files = [], isLoading } = useQuery("outro-files", mediaApi.listOutros);
  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-medium">Outro đã upload trên server</span>
        <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={14} /></button>
      </div>
      {isLoading ? (
        <div className="p-4 text-center text-gray-500 text-sm">Đang tải...</div>
      ) : files.length === 0 ? (
        <div className="p-4 text-center text-gray-500 text-sm">Chưa có outro nào trên server</div>
      ) : (
        <div className="max-h-40 overflow-y-auto divide-y divide-gray-800">
          {files.map(f => (
            <button key={f.path} type="button" onClick={() => onPick(f)}
              className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-700 cursor-pointer">
              <Film size={14} className="text-green-400 flex-shrink-0" />
              <span className="text-sm text-gray-300 truncate flex-1">{f.filename}</span>
              <span className="text-gray-600 text-xs flex-shrink-0">{f.size_mb}MB</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LogoBrowser({ onPick, onClose }) {
  const { data: files = [], isLoading } = useQuery("logo-files", mediaApi.listLogos);
  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-medium">Logo đã upload trên server</span>
        <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={14} /></button>
      </div>
      {isLoading ? (
        <div className="p-4 text-center text-gray-500 text-sm">Đang tải...</div>
      ) : files.length === 0 ? (
        <div className="p-4 text-center text-gray-500 text-sm">Chưa có logo nào — upload logo trước</div>
      ) : (
        <div className="max-h-40 overflow-y-auto divide-y divide-gray-800">
          {files.map(f => (
            <button key={f.path} type="button" onClick={() => onPick(f)}
              className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-700">
              <img src={apiUrl(`/media/logo-preview?path=${encodeURIComponent(f.path)}`)}
                onError={e => { e.target.style.display = "none"; }}
                className="w-8 h-8 object-contain rounded bg-gray-700 flex-shrink-0" alt="" />
              <span className="text-sm text-gray-300 truncate flex-1">{f.filename}</span>
              <span className="text-gray-600 text-xs flex-shrink-0">{f.size_kb}KB</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// selectedIds: number[] — mảng ID các video đã chọn, theo thứ tự chọn
function TrendingInbox({ onToggle, onSelectAll, onClearAll, selectedIds }) {
  const [open, setOpen] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showHashtags, setShowHashtags] = useState(false);
  const [showTikTokChannels, setShowTikTokChannels] = useState(false);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [newTag, setNewTag] = useState("");
  const [newChannel, setNewChannel] = useState("");
  const [fetchingChannel, setFetchingChannel] = useState(null);
  const [tiktokMaxCount, setTiktokMaxCount] = useState(50);
  const [filterHashtag, setFilterHashtag] = useState(""); // "" = tất cả

  // Chỉ lấy pending — rejected/published không hiện nữa
  const { data: items = [], isLoading, refetch } = useQuery(
    ["trending-pending", filterHashtag],
    () => trendingApi.list({ limit: 300, hashtag: filterHashtag || undefined }),
    { refetchInterval: 30000 }
  );

  const { data: hashtags = [], refetch: refetchTags } = useQuery(
    "trending-hashtags",
    trendingApi.listHashtags
  );

  // Fetch tất cả hashtag active
  const handleFetchAll = async () => {
    setFetching(true);
    try {
      const res = await trendingApi.fetchAll(true);
      toast.success(res.message || "Fetch xong!");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setFetching(false);
      refetch(); // luôn refresh list dù fetch thành công hay lỗi
    }
  };

  // Reject = xóa hẳn khỏi DB (không hiện lại)
  const handleReject = async (e, item) => {
    e.stopPropagation();
    try {
      await trendingApi.delete(item.id);
      refetch();
    } catch (_) {}
  };

  // Import TikTok URLs thủ công
  const handleImport = async () => {
    const urls = importText.split(/[\n,]+/).map(u => u.trim()).filter(Boolean);
    if (!urls.length) return toast.error("Chưa có URL nào");
    setImporting(true);
    try {
      const res = await trendingApi.import({ urls, hashtag: "manual", platform: "tiktok" });
      toast.success(res.message || `Đang import ${urls.length} URL...`);
      setImportText("");
      setShowImport(false);
      setTimeout(() => refetch(), 5000);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setImporting(false);
    }
  };

  // Thêm hashtag mới
  const handleAddTag = async () => {
    const tag = newTag.trim().replace(/^#/, "");
    if (!tag) return;
    try {
      await trendingApi.addHashtag({ hashtag: tag, platform: "instagram_reels", browser: "chrome" });
      setNewTag("");
      refetchTags();
      toast.success(`Đã thêm #${tag}`);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDeleteTag = async (id) => {
    try {
      await trendingApi.deleteHashtag(id);
      refetchTags();
    } catch (_) {}
  };

  // Thêm TikTok channel vào danh sách theo dõi
  const handleAddChannel = async () => {
    let ch = newChannel.trim();
    if (!ch) return;
    if (!ch.startsWith("http")) {
      ch = `https://www.tiktok.com/@${ch.replace(/^@/, "")}`;
    }
    try {
      await trendingApi.addHashtag({ hashtag: ch, platform: "tiktok_channel", browser: "chrome" });
      setNewChannel("");
      refetchTags();
      toast.success(`Đã thêm kênh TikTok`);
    } catch (err) {
      toast.error(err.message);
    }
  };

  // Fetch video từ một kênh TikTok ngay lập tức
  const handleFetchChannel = async (channel) => {
    setFetchingChannel(channel);
    try {
      const res = await trendingApi.fetchTikTokChannel({ channel, max_count: tiktokMaxCount });
      toast.success(res.message || "Fetch xong!");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setFetchingChannel(null);
      refetch(); // luôn refresh list dù fetch thành công hay lỗi
    }
  };

  const tiktokChannels = hashtags.filter(h => h.platform === "tiktok_channel");
  const igHashtags = hashtags.filter(h => h.platform !== "tiktok_channel");

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button type="button" onClick={() => setOpen(v => !v)}
          className="flex items-center gap-2 text-white font-semibold">
          <TrendingUp size={16} className="text-pink-400" />
          Video Inbox
          {items.length > 0 && (
            <span className="bg-pink-600 text-white text-xs px-2 py-0.5 rounded-full">
              {items.length}{filterHashtag ? " (lọc)" : ""}
            </span>
          )}
          {selectedIds.length > 0 && (
            <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
              <CheckSquare size={10} /> {selectedIds.length} đã chọn
            </span>
          )}
          {open ? <ChevronUp size={15} className="text-gray-500" /> : <ChevronDown size={15} className="text-gray-500" />}
        </button>

        <div className="flex items-center gap-1.5">
          {/* Lọc theo kênh/hashtag */}
          <select
            value={filterHashtag}
            onChange={e => setFilterHashtag(e.target.value)}
            className="text-xs bg-gray-800 border border-gray-600 rounded px-2 py-1 text-gray-300 hover:border-gray-400 transition-colors max-w-[140px]"
            title="Lọc theo nguồn"
          >
            <option value="">Tất cả nguồn</option>
            {hashtags.map(h => {
              const label = h.platform === "tiktok_channel"
                ? h.hashtag.replace("https://www.tiktok.com/@", "@")
                : `#${h.hashtag}`;
              return <option key={h.id} value={h.hashtag}>{label}</option>;
            })}
          </select>
          {/* Quản lý hashtag */}
          <button type="button" onClick={() => setShowHashtags(v => !v)}
            className={`text-xs px-2 py-1 border rounded transition-colors ${showHashtags ? "border-pink-500 text-pink-400" : "border-gray-600 text-gray-400 hover:border-gray-400 hover:text-white"}`}
            title="Quản lý hashtag theo dõi">
            # Tags ({igHashtags.length})
          </button>
          {/* Kênh TikTok */}
          <button type="button" onClick={() => setShowTikTokChannels(v => !v)}
            className={`text-xs px-2 py-1 border rounded transition-colors ${showTikTokChannels ? "border-cyan-500 text-cyan-400" : "border-gray-600 text-gray-400 hover:border-gray-400 hover:text-white"}`}
            title="Kênh TikTok theo dõi">
            TikTok ({tiktokChannels.length})
          </button>
          {/* Import URLs */}
          <button type="button" onClick={() => setShowImport(v => !v)}
            className="flex items-center gap-1 text-xs px-2 py-1 border border-gray-600 rounded text-gray-400 hover:text-white hover:border-gray-400 transition-colors">
            <Upload size={11} /> URLs
          </button>
          {/* Fetch tất cả */}
          <button type="button" onClick={handleFetchAll} disabled={fetching}
            className="flex items-center gap-1 text-xs px-2 py-1 border border-gray-600 rounded text-gray-400 hover:text-white hover:border-gray-400 transition-colors"
            title="Fetch Instagram Reels cho tất cả hashtag">
            <RotateCcw size={11} className={fetching ? "animate-spin" : ""} />
            {fetching ? "Đang lấy..." : "Fetch"}
          </button>
        </div>
      </div>

      {/* Hashtag manager */}
      {open && showHashtags && (
        <div className="mt-3 p-3 bg-gray-800/60 rounded-lg border border-gray-700 space-y-2">
          <p className="text-xs text-gray-400 font-medium">Hashtag đang theo dõi (Instagram Reels)</p>
          <div className="flex flex-wrap gap-1.5">
            {igHashtags.map(h => (
              <span key={h.id}
                className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${h.is_active ? "border-pink-600/50 bg-pink-950/30 text-pink-300" : "border-gray-600 text-gray-500"}`}>
                #{h.hashtag}
                <button type="button" onClick={() => handleDeleteTag(h.id)}
                  className="text-gray-500 hover:text-red-400 ml-0.5">
                  <X size={10} />
                </button>
              </span>
            ))}
            {igHashtags.length === 0 && (
              <span className="text-xs text-gray-600">Chưa có — thêm tag đầu tiên bên dưới</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              value={newTag}
              onChange={e => setNewTag(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAddTag()}
              className="input flex-1 text-xs py-1"
              placeholder="#nailart hoặc naildesign"
            />
            <button type="button" onClick={handleAddTag} disabled={!newTag.trim()}
              className="text-xs px-3 py-1 bg-pink-600 hover:bg-pink-500 text-white rounded disabled:opacity-40">
              Thêm
            </button>
          </div>
        </div>
      )}

      {/* TikTok channel manager */}
      {open && showTikTokChannels && (
        <div className="mt-3 p-3 bg-gray-800/60 rounded-lg border border-cyan-900/50 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-cyan-400 font-medium">Kênh TikTok đang theo dõi</p>
            <div className="flex items-center gap-1 text-xs text-gray-400">
              <span>Lấy tối đa</span>
              <input
                type="number" min={10} max={200} step={10}
                value={tiktokMaxCount}
                onChange={e => setTiktokMaxCount(Number(e.target.value))}
                className="w-14 text-center bg-gray-700 border border-gray-600 rounded px-1 py-0.5 text-white text-xs"
              />
              <span>video</span>
            </div>
          </div>
          <div className="space-y-1.5">
            {tiktokChannels.map(h => {
              const isFetching = fetchingChannel === h.hashtag;
              const username = h.hashtag.replace("https://www.tiktok.com/@", "@");
              return (
                <div key={h.id} className="flex items-center justify-between gap-2 text-xs">
                  <a href={h.hashtag} target="_blank" rel="noreferrer"
                    className="text-cyan-300 hover:underline truncate flex-1">{username}</a>
                  <div className="flex gap-1 flex-shrink-0">
                    <button type="button" onClick={() => handleFetchChannel(h.hashtag)}
                      disabled={!!fetchingChannel}
                      className="px-2 py-0.5 rounded bg-cyan-700/40 hover:bg-cyan-600/60 text-cyan-300 disabled:opacity-40 flex items-center gap-1">
                      <RotateCcw size={10} className={isFetching ? "animate-spin" : ""} />
                      {isFetching ? "Đang lấy..." : "Fetch"}
                    </button>
                    <button type="button" onClick={() => handleDeleteTag(h.id)}
                      className="text-gray-500 hover:text-red-400">
                      <X size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
            {tiktokChannels.length === 0 && (
              <span className="text-xs text-gray-600">Chưa có kênh nào — thêm bên dưới</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              value={newChannel}
              onChange={e => setNewChannel(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAddChannel()}
              className="input flex-1 text-xs py-1"
              placeholder="@softlux.nails hoặc URL đầy đủ"
            />
            <button type="button" onClick={handleAddChannel} disabled={!newChannel.trim()}
              className="text-xs px-3 py-1 bg-cyan-700 hover:bg-cyan-600 text-white rounded disabled:opacity-40">
              Thêm
            </button>
          </div>
        </div>
      )}

      {/* Import URLs panel */}
      {open && showImport && (
        <div className="mt-3 p-3 bg-gray-800/60 rounded-lg space-y-2 border border-gray-700">
          <p className="text-xs text-gray-400">Dán link TikTok/Instagram (mỗi link 1 dòng):</p>
          <textarea value={importText} onChange={e => setImportText(e.target.value)}
            rows={3} className="input w-full text-xs font-mono resize-none"
            placeholder={"https://www.tiktok.com/@user/video/123...\nhttps://www.instagram.com/reel/ABC..."} />
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setShowImport(false)}
              className="text-xs px-3 py-1.5 rounded border border-gray-600 text-gray-400 hover:text-white">Huỷ</button>
            <button type="button" onClick={handleImport} disabled={importing || !importText.trim()}
              className="text-xs px-3 py-1.5 rounded bg-pink-600 hover:bg-pink-500 text-white disabled:opacity-50">
              {importing ? "Đang import..." : "Import"}
            </button>
          </div>
        </div>
      )}

      {/* Video list — chỉ pending */}
      {open && (
        <div className="mt-3">
          {isLoading ? (
            <div className="text-center text-gray-500 text-sm py-4">Đang tải...</div>
          ) : items.length === 0 ? (
            <div className="text-center text-gray-600 text-sm py-5 space-y-1">
              <p>Inbox trống.</p>
              <p className="text-xs">
                Nhấn <span className="text-gray-400 font-medium">Fetch</span> để lấy Reels tự động,
                hoặc <span className="text-gray-400 font-medium">URLs</span> để paste link thủ công.
              </p>
            </div>
          ) : (
            <>
              {/* Chọn tất cả / bỏ chọn */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  {selectedIds.length > 0 ? `${selectedIds.length}/${items.length} đã chọn` : `${items.length} video`}
                </span>
                <div className="flex gap-1.5">
                  <button type="button" onClick={() => onSelectAll(items)}
                    disabled={items.length === 0 || selectedIds.length >= items.length}
                    className="flex items-center gap-1 text-xs px-2 py-1 border border-gray-600 rounded text-gray-400 hover:text-white hover:border-gray-400 transition-colors disabled:opacity-40">
                    <CheckSquare size={11} /> Chọn tất cả
                  </button>
                  {selectedIds.length > 0 && (
                    <button type="button" onClick={onClearAll}
                      className="flex items-center gap-1 text-xs px-2 py-1 border border-gray-600 rounded text-gray-400 hover:text-red-400 hover:border-red-500/60 transition-colors">
                      <X size={11} /> Bỏ chọn
                    </button>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
              {items.map((item) => {
                const selIdx = selectedIds.indexOf(item.id);
                const isSelected = selIdx !== -1;
                return (
                  <div key={item.id} onClick={() => onToggle(item)}
                    className={`relative flex gap-2 p-2 rounded-lg border cursor-pointer transition-colors ${
                      isSelected ? "border-pink-500 bg-pink-950/30" : "border-gray-700 hover:border-gray-500 hover:bg-gray-800"
                    }`}>
                    {/* Checkbox badge */}
                    <div className={`absolute top-1.5 left-1.5 w-4 h-4 rounded flex items-center justify-center text-xs font-bold border transition-colors ${
                      isSelected ? "bg-pink-500 border-pink-500 text-white" : "border-gray-600 bg-gray-900"
                    }`}>
                      {isSelected ? selIdx + 1 : ""}
                    </div>
                    {/* Thumbnail */}
                    <div className="w-12 h-12 flex-shrink-0 rounded overflow-hidden bg-gray-800 ml-4">
                      {item.thumbnail_url
                        ? <img src={item.thumbnail_url} alt="" className="w-full h-full object-cover" />
                        : <div className="w-full h-full flex items-center justify-center"><Video size={18} className="text-gray-600" /></div>
                      }
                    </div>
                    {/* Info */}
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <p className="text-xs text-gray-200 line-clamp-2 leading-tight">
                        {item.video_title || <span className="text-gray-500 italic">No title</span>}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {item.platform === "tiktok" || item.platform === "tiktok_channel" ? "🎵" : item.platform === "instagram_reels" ? "📷" : "▶"}{" "}
                        @{item.author || "?"}
                      </p>
                      {item.view_count > 0 && (
                        <p className="text-xs text-gray-600 flex items-center gap-0.5">
                          <Eye size={9} /> {item.view_count.toLocaleString()}
                        </p>
                      )}
                    </div>
                    {/* Reject/delete button */}
                    <button type="button" onClick={e => handleReject(e, item)}
                      className="absolute top-1 right-1 text-gray-600 hover:text-red-400 transition-colors" title="Loại">
                      <X size={12} />
                    </button>
                  </div>
                );
              })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function NewJob() {
  const navigate = useNavigate();
  const [videoInfo, setVideoInfo] = useState(null);
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [clips, setClips] = useState([]);
  const [uploadingClip, setUploadingClip] = useState(false);
  const [outroPath, setOutroPath] = useState(null);
  const [outroName, setOutroName] = useState("");
  const [showOutroBrowser, setShowOutroBrowser] = useState(false);
  const [uploadingOutro, setUploadingOutro] = useState(false);
  const outroInputRef = useRef(null);

  const [logoPath, setLogoPath] = useState(null);
  const [logoName, setLogoName] = useState("");
  const [logoPosition, setLogoPosition] = useState("top-left");
  const [logoSize, setLogoSize] = useState(80);
  const [showLogoBrowser, setShowLogoBrowser] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = useRef(null);
  // Multi-select: [{item, upload_at: ""}]
  const [selectedTrendings, setSelectedTrendings] = useState([]);
  const [batchStartTime, setBatchStartTime] = useState("");
  const [timeSlots, setTimeSlots] = useState(["11:00", "18:00"]);
  const [batchTimezone, setBatchTimezone] = useState("America/Phoenix");
  const [isCreatingBatch, setIsCreatingBatch] = useState(false);

  const { data: channels = [] } = useQuery("channels", channelsApi.list);
  const { data: templates = [] } = useQuery("templates", templatesApi.list);

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm({
    defaultValues: {
      upload_mode: "immediate",
      video_quality: "1080p",
      output_format: "9:16",
      mute_original: true,
      original_volume: 0.2,
      music_volume: 0.8,
      loop_music: true,
      fade_in_duration: 0,
      fade_out_duration: 2,
      privacy_status: "public",
      language: "en",
      category_id: "22",
      priority: 0,
    },
  });

  const videoUrl = watch("video_url");
  const muteOriginal = watch("mute_original");
  const uploadMode = watch("upload_mode");

  const { mutate: createJob, isLoading: isCreatingSingle } = useMutation(downloadsApi.createJob, {
    onSuccess: (data) => {
      toast.success(`Job #${data.id} đã được tạo!`);
      navigate("/queue");
    },
    onError: (e) => toast.error(e.message),
  });

  const handleToggleTrending = (item) => {
    setSelectedTrendings(prev => {
      const exists = prev.find(s => s.item.id === item.id);
      if (exists) return prev.filter(s => s.item.id !== item.id);
      return [...prev, { item, upload_at: "" }];
    });
  };

  // Chọn tất cả video đang hiển thị trong inbox (giữ những cái đã chọn trước đó)
  const handleSelectAllTrending = (items) => {
    setSelectedTrendings(prev => {
      const have = new Set(prev.map(s => s.item.id));
      const added = items.filter(i => !have.has(i.id)).map(item => ({ item, upload_at: "" }));
      return [...prev, ...added];
    });
  };

  const handleClearTrending = () => setSelectedTrendings([]);

  const handleSetUploadAt = (itemId, val) => {
    setSelectedTrendings(prev =>
      prev.map(s => s.item.id === itemId ? { ...s, upload_at: val } : s)
    );
  };

  const handleAutoSchedule = () => {
    if (!batchStartTime) return toast.error("Chọn ngày bắt đầu");
    if (timeSlots.length === 0) return toast.error("Cần ít nhất 1 khung giờ");
    const [year, month, day] = batchStartTime.split("-").map(Number);
    const pad = n => String(n).padStart(2, "0");
    setSelectedTrendings(prev => prev.map((s, i) => {
      const slotIdx = i % timeSlots.length;
      const dayOffset = Math.floor(i / timeSlots.length);
      const d = new Date(year, month - 1, day + dayOffset);
      const dt = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${timeSlots[slotIdx]}`;
      return { ...s, upload_at: dt };
    }));
  };

  const handleFetchInfo = async () => {
    if (!videoUrl) return;
    setFetchingInfo(true);
    try {
      const info = await downloadsApi.getInfo(videoUrl);
      setVideoInfo(info);
      if (info.title && !watch("title")) setValue("title", info.title.slice(0, 100));
      toast.success("Đã lấy thông tin video");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setFetchingInfo(false);
    }
  };

  const handleTemplateChange = (e) => {
    const id = parseInt(e.target.value);
    const tmpl = templates.find(t => t.id === id);
    if (tmpl) {
      if (tmpl.title_template) setValue("title", tmpl.title_template);
      if (tmpl.description_template) setValue("description", tmpl.description_template);
      if (tmpl.tags) setValue("tags", tmpl.tags.join(", "));
      if (tmpl.category_id) setValue("category_id", tmpl.category_id);
      if (tmpl.privacy_status) setValue("privacy_status", tmpl.privacy_status);
      setValue("template_id", id);
    }
  };

  const handleUploadLogo = async (file) => {
    setUploadingLogo(true);
    try {
      const res = await mediaApi.uploadLogo(file);
      setLogoPath(res.path);
      setLogoName(file.name);
      toast.success(`Logo: ${file.name}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setUploadingLogo(false);
    }
  };

  const handleUploadOutro = async (file) => {
    setUploadingOutro(true);
    try {
      const res = await mediaApi.uploadOutro(file);
      setOutroPath(res.path);
      setOutroName(file.name);
      toast.success(`Outro: ${file.name}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setUploadingOutro(false);
    }
  };

  const buildBasePayload = (data) => ({
    channel_id: parseInt(data.channel_id),
    template_id: data.template_id ? parseInt(data.template_id) : undefined,
    tags: data.tags ? data.tags.split(",").map(t => t.trim()).filter(Boolean) : [],
    original_volume: parseFloat(data.original_volume),
    music_volume: parseFloat(data.music_volume),
    fade_in_duration: parseFloat(data.fade_in_duration),
    fade_out_duration: parseFloat(data.fade_out_duration),
    priority: parseInt(data.priority),
    music_url: data.music_url || undefined,
    music_start_time: data.music_start_time ? parseFloat(data.music_start_time) : undefined,
    music_end_time: data.music_end_time ? parseFloat(data.music_end_time) : undefined,
    mute_original: data.mute_original,
    mute_range_start: data.mute_range_start ? parseFloat(data.mute_range_start) : undefined,
    mute_range_end: data.mute_range_end ? parseFloat(data.mute_range_end) : undefined,
    loop_music: data.loop_music,
    video_quality: data.video_quality,
    output_format: data.output_format,
    description: data.description,
    category_id: data.category_id,
    privacy_status: data.privacy_status,
    language: data.language,
    upload_mode: data.upload_mode,
    outro_path: outroPath || undefined,
    logo_path: logoPath || undefined,
    logo_position: logoPosition,
    logo_size: logoSize,
  });

  // UTC offset (minutes) cho các timezone — Phoenix không có DST nên cố định -420
  const TZ_OFFSETS = {
    "America/Phoenix":   -7 * 60,
    "America/New_York":  -5 * 60,
    "UTC":                0,
    "Asia/Ho_Chi_Minh":  7 * 60,
    "Asia/Bangkok":       7 * 60,
    "Asia/Singapore":     8 * 60,
  };

  // Convert "YYYY-MM-DDTHH:mm[...]" (naive, trong timezone tz) → UTC ISO string
  const toUTCInTZ = (localDT, tz) => {
    if (!localDT) return undefined;
    const offsetMin = TZ_OFFSETS[tz] ?? 0;
    // slice(0,16) chuẩn hoá về "YYYY-MM-DDTHH:MM" dù browser có trả về seconds hay không
    const asUTCMs = new Date(localDT.slice(0, 16) + ":00Z").getTime();
    if (isNaN(asUTCMs)) return undefined;
    return new Date(asUTCMs - offsetMin * 60000).toISOString();
  };

  // Convert browser local datetime-local → UTC (dùng cho single job)
  const toUTC = (localDT) => localDT ? new Date(localDT).toISOString() : undefined;

  const onSubmit = async (data) => {
    if (!data.channel_id) return toast.error("Vui lòng chọn kênh YouTube");
    const base = buildBasePayload(data);

    // Batch mode: tạo job cho từng video đã chọn
    if (selectedTrendings.length > 0) {
      setIsCreatingBatch(true);
      let ok = 0;
      for (let i = 0; i < selectedTrendings.length; i++) {
        const { item, upload_at } = selectedTrendings[i];
        try {
          const job = await downloadsApi.createJob({
            ...base,
            video_url: item.video_url,
            title: (item.video_title || "").slice(0, 100) || data.title || undefined,
            upload_at: toUTCInTZ(upload_at, batchTimezone) || toUTCInTZ(data.upload_at, batchTimezone),
          });
          await trendingApi.update(item.id, { status: "published", job_id: job.id }).catch(() => {});
          ok++;
        } catch (e) {
          toast.error(`Video ${i + 1}/${selectedTrendings.length}: ${e.message}`);
        }
      }
      setIsCreatingBatch(false);
      if (ok > 0) {
        toast.success(`Đã tạo ${ok}/${selectedTrendings.length} job!`);
        navigate("/queue");
      }
      return;
    }

    // Single mode
    if (!data.video_url && clips.length === 0) {
      return toast.error("Nhập URL video hoặc upload ít nhất 1 clip");
    }
    createJob({
      ...base,
      video_url: data.video_url || undefined,
      title: data.title,
      clip_paths: clips.map(c => c.path),
      upload_at: toUTC(data.upload_at),
    });
  };

  const authenticatedChannels = channels.filter(c => c.is_authenticated);

  return (
    <div className="max-w-2xl space-y-5">
      <h1 className="text-2xl font-bold text-white">Tạo Video Mới</h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

        {/* Trending Inbox */}
        <TrendingInbox
          onToggle={handleToggleTrending}
          onSelectAll={handleSelectAllTrending}
          onClearAll={handleClearTrending}
          selectedIds={selectedTrendings.map(s => s.item.id)}
        />

        {/* Batch schedule panel */}
        {selectedTrendings.length > 0 && (
          <div className="card space-y-3 border border-green-800/50">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <CalendarClock size={16} className="text-green-400" />
              Lịch đăng — {selectedTrendings.length} video đã chọn
            </h3>

            {/* Auto-fill */}
            <div className="p-3 bg-gray-800/60 rounded-lg border border-gray-700 space-y-3">
              <div className="flex gap-3 items-end">
                <div className="flex-1">
                  <label className="label text-xs">Ngày bắt đầu</label>
                  <input type="date" className="input text-sm py-1"
                    value={batchStartTime} onChange={e => setBatchStartTime(e.target.value)} />
                </div>
                <button type="button" onClick={handleAutoSchedule}
                  className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-sm rounded whitespace-nowrap">
                  Tự điền
                </button>
              </div>
              <div>
                <label className="label text-xs">Timezone lịch đăng</label>
                <select className="input text-sm py-1" value={batchTimezone} onChange={e => setBatchTimezone(e.target.value)}>
                  {Object.keys(TZ_OFFSETS).map(tz => <option key={tz} value={tz}>{tz}</option>)}
                </select>
              </div>
              <div>
                <label className="label text-xs">Khung giờ đăng ({batchTimezone})</label>
                <div className="flex flex-wrap gap-2 mt-1.5">
                  {timeSlots.map((slot, i) => (
                    <div key={i} className="flex items-center gap-1 bg-gray-700 border border-gray-600 rounded px-2 py-1">
                      <input
                        type="time"
                        value={slot}
                        onChange={e => setTimeSlots(prev => prev.map((s, j) => j === i ? e.target.value : s))}
                        className="bg-transparent text-sm text-white w-20 focus:outline-none"
                      />
                      <button type="button" onClick={() => setTimeSlots(prev => prev.filter((_, j) => j !== i))}
                        className="text-gray-500 hover:text-red-400">
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                  <button type="button"
                    onClick={() => setTimeSlots(prev => [...prev, "12:00"])}
                    className="flex items-center gap-1 text-xs px-2 py-1 border border-dashed border-gray-600 rounded text-gray-400 hover:border-gray-400 hover:text-white">
                    <Plus size={12} /> Thêm giờ
                  </button>
                </div>
                <p className="text-xs text-gray-600 mt-1">
                  Mỗi ngày {timeSlots.length} video — {selectedTrendings.length} video cần ~{Math.ceil(selectedTrendings.length / Math.max(timeSlots.length, 1))} ngày
                </p>
              </div>
            </div>

            {/* Per-video schedule */}
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {selectedTrendings.map(({ item, upload_at }, i) => (
                <div key={item.id} className="flex items-center gap-2 p-2 bg-gray-800 rounded-lg border border-gray-700">
                  <span className="text-xs text-gray-500 w-5 text-center flex-shrink-0">{i + 1}</span>
                  {item.thumbnail_url
                    ? <img src={item.thumbnail_url} className="w-9 h-9 object-cover rounded flex-shrink-0" alt="" />
                    : <div className="w-9 h-9 bg-gray-700 rounded flex-shrink-0" />
                  }
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-200 truncate">
                      {item.video_title || item.video_url}
                    </p>
                    <p className="text-xs text-gray-500">@{item.author || "?"}</p>
                  </div>
                  <div className="flex-shrink-0 flex flex-col items-end gap-0.5">
                    <input type="datetime-local" className="input text-xs py-1 w-44"
                      value={upload_at}
                      onChange={e => handleSetUploadAt(item.id, e.target.value)}
                      placeholder="Không đặt = đăng ngay"
                    />
                    {upload_at && (
                      <span className="text-xs text-amber-400">
                        = {new Date(toUTCInTZ(upload_at, batchTimezone)).toLocaleString("en-US", {
                          timeZone: "America/Phoenix",
                          month: "numeric", day: "numeric",
                          hour: "2-digit", minute: "2-digit", hour12: false,
                        })} Phoenix
                      </span>
                    )}
                  </div>
                  <button type="button" onClick={() => handleToggleTrending(item)}
                    className="text-gray-500 hover:text-red-400 flex-shrink-0">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500">Để trống thời gian = xử lý và đăng liền. Đặt thời gian = upload đúng giờ đó.</p>
          </div>
        )}

        {/* Channel */}
        <Section icon={Settings2} title="Kênh & Template">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Kênh YouTube *</label>
              <select className="input" {...register("channel_id", { required: true })}>
                <option value="">-- Chọn kênh --</option>
                {authenticatedChannels.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              {errors.channel_id && <p className="text-red-400 text-xs mt-1">Vui lòng chọn kênh</p>}
              {authenticatedChannels.length === 0 && (
                <p className="text-yellow-500 text-xs mt-1">Chưa có kênh nào đã xác thực OAuth2</p>
              )}
            </div>
            <div>
              <label className="label">Template metadata</label>
              <select className="input" {...register("template_id")} onChange={handleTemplateChange}>
                <option value="">-- Không dùng --</option>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>
        </Section>

        {/* Video source */}
        <Section icon={Video} title="Nguồn Video">
          <div>
            <label className="label">Link video (YouTube / TikTok)</label>
            <div className="flex gap-2">
              <input className="input flex-1" {...register("video_url")} placeholder="https://youtube.com/watch?v=..." />
              <button type="button" onClick={handleFetchInfo} disabled={fetchingInfo || !videoUrl} className="btn-secondary shrink-0">
                <Search size={16} /> {fetchingInfo ? "..." : "Lấy info"}
              </button>
            </div>
          </div>
          {videoInfo && (
            <div className="bg-gray-800 rounded-lg p-3 text-sm space-y-1">
              <div className="text-white font-medium truncate">{videoInfo.title}</div>
              <div className="text-gray-500">{videoInfo.uploader} · {Math.floor((videoInfo.duration || 0) / 60)}:{String((videoInfo.duration || 0) % 60).padStart(2, "0")}</div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Chất lượng</label>
              <select className="input" {...register("video_quality")}>
                {QUALITY_OPTIONS.map(q => <option key={q} value={q}>{q}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Tỷ lệ khung hình</label>
              <select className="input" {...register("output_format")}>
                {FORMAT_OPTIONS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </div>
          </div>
        </Section>

        {/* Video clips upload */}
        <Section icon={Film} title="Upload Video Clips để ghép">
          <p className="text-gray-500 text-xs">
            Upload nhiều clip — sẽ được ghép lại theo thứ tự. Có thể dùng thay hoặc kết hợp với URL ở trên.
          </p>
          <MultiClipUpload
            clips={clips}
            onAdd={clip => setClips(prev => [...prev, clip])}
            onRemove={i => setClips(prev => prev.filter((_, idx) => idx !== i))}
            uploading={uploadingClip}
            setUploading={setUploadingClip}
          />
          {clips.length > 1 && (
            <p className="text-blue-400 text-xs">
              {clips.length} clips sẽ được ghép theo thứ tự trên → 1 video đầu ra.
            </p>
          )}
        </Section>

        {/* Logo overlay */}
        <Section icon={Upload} title="Logo / Icon góc video">
          <p className="text-gray-500 text-xs">Ảnh PNG/JPG được đặt đè lên video (mặc định góc trên bên trái).</p>
          {logoPath ? (
            <div className="flex items-center gap-2 p-2 bg-gray-800 rounded border border-purple-700">
              <Upload size={14} className="text-purple-400 flex-shrink-0" />
              <span className="text-sm text-gray-200 truncate flex-1">{logoName}</span>
              <button type="button" onClick={() => { setLogoPath(null); setLogoName(""); }}
                className="text-gray-500 hover:text-red-400 flex-shrink-0"><X size={14} /></button>
            </div>
          ) : (
            <div className="flex gap-2">
              <div onClick={() => !uploadingLogo && logoInputRef.current?.click()}
                className={`flex items-center gap-3 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors flex-1 ${uploadingLogo ? "border-gray-700 opacity-50 cursor-not-allowed" : "border-gray-700 hover:border-purple-600 hover:bg-purple-950/20"}`}>
                {uploadingLogo ? <RefreshCw size={16} className="animate-spin text-gray-400" /> : <Upload size={16} className="text-gray-500" />}
                <span className="text-sm text-gray-500">{uploadingLogo ? "Đang upload..." : "Upload logo (PNG/JPG)"}</span>
              </div>
              <button type="button" onClick={() => setShowLogoBrowser(v => !v)}
                className="flex items-center gap-2 px-3 py-2 border border-gray-600 rounded-lg text-sm text-gray-400 hover:border-gray-400 hover:text-white transition-colors">
                <FolderOpen size={15} /> File có sẵn
              </button>
            </div>
          )}
          {showLogoBrowser && !logoPath && (
            <LogoBrowser onPick={f => { setLogoPath(f.path); setLogoName(f.filename); setShowLogoBrowser(false); }} onClose={() => setShowLogoBrowser(false)} />
          )}
          {logoPath && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label text-xs">Vị trí</label>
                <select className="input text-sm py-1" value={logoPosition} onChange={e => setLogoPosition(e.target.value)}>
                  <option value="top-left">Trên trái</option>
                  <option value="top-right">Trên phải</option>
                  <option value="bottom-left">Dưới trái</option>
                  <option value="bottom-right">Dưới phải</option>
                </select>
              </div>
              <div>
                <label className="label text-xs">Kích thước (px rộng)</label>
                <input type="number" className="input text-sm py-1" value={logoSize} min={20} max={300}
                  onChange={e => setLogoSize(Number(e.target.value))} />
              </div>
            </div>
          )}
          <input ref={logoInputRef} type="file" accept=".png,.jpg,.jpeg,.webp" className="hidden"
            onChange={e => e.target.files[0] && handleUploadLogo(e.target.files[0])} />
        </Section>

        {/* Outro */}
        <Section icon={Film} title="Outro (ghép cuối video)">
          <p className="text-gray-500 text-xs">Clip được ghép tự động vào cuối sau khi xử lý xong.</p>
          {outroPath ? (
            <div className="flex items-center gap-2 p-2 bg-gray-800 rounded border border-green-700">
              <Film size={14} className="text-green-400 flex-shrink-0" />
              <span className="text-sm text-gray-200 truncate flex-1">{outroName}</span>
              <button type="button" onClick={() => { setOutroPath(null); setOutroName(""); }}
                className="text-gray-500 hover:text-red-400 flex-shrink-0"><X size={14} /></button>
            </div>
          ) : (
            <div className="flex gap-2">
              <div onClick={() => !uploadingOutro && outroInputRef.current?.click()}
                className={`flex items-center gap-3 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors flex-1 ${uploadingOutro ? "border-gray-700 opacity-50 cursor-not-allowed" : "border-gray-700 hover:border-green-600 hover:bg-green-950/20"}`}>
                {uploadingOutro ? <RefreshCw size={16} className="animate-spin text-gray-400" /> : <Upload size={16} className="text-gray-500" />}
                <span className="text-sm text-gray-500">{uploadingOutro ? "Đang upload..." : "Upload outro mới (MP4/MOV)"}</span>
              </div>
              <button type="button" onClick={() => setShowOutroBrowser(v => !v)}
                className="flex items-center gap-2 px-3 py-2 border border-gray-600 rounded-lg text-sm text-gray-400 hover:border-gray-400 hover:text-white transition-colors">
                <FolderOpen size={15} /> File có sẵn
              </button>
            </div>
          )}
          {showOutroBrowser && !outroPath && (
            <OutroBrowser onPick={(f) => { setOutroPath(f.path); setOutroName(f.filename); setShowOutroBrowser(false); }} onClose={() => setShowOutroBrowser(false)} />
          )}
          <input ref={outroInputRef} type="file" accept=".mp4,.mov,.mkv,.webm" className="hidden"
            onChange={e => e.target.files[0] && handleUploadOutro(e.target.files[0])} />
        </Section>

        {/* Music */}
        <Section icon={Music} title="Nhạc nền">
          <div>
            <label className="label">Link nhạc (YouTube / SoundCloud / MP3)</label>
            <input className="input" {...register("music_url")} placeholder="https://youtube.com/watch?v=..." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Bắt đầu từ (giây)</label>
              <input type="number" step="0.1" className="input" {...register("music_start_time")} placeholder="0" />
            </div>
            <div>
              <label className="label">Kết thúc lúc (giây)</label>
              <input type="number" step="0.1" className="input" {...register("music_end_time")} placeholder="Hết bài" />
            </div>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" {...register("mute_original")} className="w-4 h-4 accent-red-500" />
              <span className="text-sm text-gray-300">Tắt tiếng gốc của video</span>
            </label>
            {!muteOriginal && (
              <>
                <div>
                  <label className="label">Âm lượng tiếng gốc ({Math.round(watch("original_volume") * 100)}%)</label>
                  <input type="range" min="0" max="1" step="0.05" className="w-full" {...register("original_volume")} />
                </div>
                <div>
                  <label className="label">Tắt tiếng gốc trong khoảng thời gian (tuỳ chọn)</label>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label text-xs text-gray-500">Từ giây</label>
                      <input type="number" step="0.5" min="0" className="input" {...register("mute_range_start")} placeholder="VD: 0" />
                    </div>
                    <div>
                      <label className="label text-xs text-gray-500">Đến giây</label>
                      <input type="number" step="0.5" min="0" className="input" {...register("mute_range_end")} placeholder="VD: 30" />
                    </div>
                  </div>
                  <p className="text-gray-600 text-xs mt-1">Để trống nếu không cần tắt tiếng theo khoảng</p>
                </div>
              </>
            )}
            <div>
              <label className="label">Âm lượng nhạc nền ({Math.round(watch("music_volume") * 100)}%)</label>
              <input type="range" min="0" max="1" step="0.05" className="w-full" {...register("music_volume")} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <label className="flex items-center gap-2 cursor-pointer col-span-1">
                <input type="checkbox" {...register("loop_music")} className="w-4 h-4 accent-red-500" />
                <span className="text-sm text-gray-300">Loop nhạc</span>
              </label>
              <div>
                <label className="label">Fade in (giây)</label>
                <input type="number" step="0.5" className="input" {...register("fade_in_duration")} />
              </div>
              <div>
                <label className="label">Fade out (giây)</label>
                <input type="number" step="0.5" className="input" {...register("fade_out_duration")} />
              </div>
            </div>
          </div>
        </Section>

        {/* Metadata */}
        <Section icon={FileText} title="Metadata YouTube">
          <div>
            <label className="label">
              Tiêu đề {selectedTrendings.length > 0
                ? <span className="text-gray-500 font-normal text-xs">(để trống = tự lấy theo từng video)</span>
                : "*"}
            </label>
            <input className="input"
              {...register("title", { required: selectedTrendings.length === 0, maxLength: 100 })}
              placeholder={selectedTrendings.length > 0 ? "Tự lấy theo tiêu đề từng video" : "Tiêu đề video (tối đa 100 ký tự)"} />
          </div>
          <div>
            <label className="label">Mô tả</label>
            <textarea className="input" rows={3} {...register("description")} placeholder="Mô tả video..." />
          </div>
          <div>
            <label className="label">Tags (phân cách bởi dấu phẩy)</label>
            <input className="input" {...register("tags")} placeholder="tag1, tag2, tag3" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Privacy</label>
              <select className="input" {...register("privacy_status")}>
                {PRIVACY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Ngôn ngữ</label>
              <input className="input" {...register("language")} placeholder="vi" />
            </div>
            <div>
              <label className="label">Độ ưu tiên</label>
              <input type="number" className="input" {...register("priority")} min={0} />
            </div>
          </div>
          <div>
            <label className="label">Lên lịch upload lúc (tuỳ chọn)</label>
            <input type="datetime-local" className="input" {...register("upload_at")} />
          </div>
        </Section>

        {/* Upload mode */}
        <div className="card space-y-3">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Zap size={16} className="text-red-400" /> Chế độ đăng
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <label
              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${uploadMode === "immediate"
                  ? "border-red-500 bg-red-600/10 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-600"
                }`}
            >
              <input type="radio" value="immediate" {...register("upload_mode")} className="hidden" />
              <Zap size={18} className={uploadMode === "immediate" ? "text-red-400" : "text-gray-500"} />
              <div>
                <div className="font-medium text-sm">Đăng liền</div>
                <div className="text-xs text-gray-500">Xử lý xong → upload YouTube ngay</div>
              </div>
            </label>
            <label
              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${uploadMode === "manual"
                  ? "border-blue-500 bg-blue-600/10 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-600"
                }`}
            >
              <input type="radio" value="manual" {...register("upload_mode")} className="hidden" />
              <Clock size={18} className={uploadMode === "manual" ? "text-blue-400" : "text-gray-500"} />
              <div>
                <div className="font-medium text-sm">Xử lý trước</div>
                <div className="text-xs text-gray-500">Xử lý xong → chờ bấm upload sau</div>
              </div>
            </label>
          </div>
        </div>

        <button type="submit" disabled={isCreatingSingle || isCreatingBatch} className="btn-primary w-full py-3 text-base">
          {isCreatingBatch ? (
            <><RefreshCw size={18} className="animate-spin" /> Đang tạo job...</>
          ) : selectedTrendings.length > 0 ? (
            <><CalendarClock size={18} /> Tạo {selectedTrendings.length} Job</>
          ) : uploadMode === "immediate" ? (
            <><Zap size={18} /> {isCreatingSingle ? "Đang tạo job..." : "Tạo & Đăng Liền"}</>
          ) : (
            <><Clock size={18} /> {isCreatingSingle ? "Đang tạo job..." : "Tạo & Xử Lý Trước"}</>
          )}
        </button>
      </form>
    </div>
  );
}

import { useState, useRef } from "react";
import { useQuery, useMutation } from "react-query";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { channelsApi, autoCreatorApi, tiktokApi, mediaApi } from "../api";
import {
  Zap, TrendingUp, Download, Search, Video, Eye, RefreshCw,
  ChevronDown, ChevronUp, CheckCircle, Clock, Upload, X, Image, Film, FolderOpen, Facebook,
} from "lucide-react";

const PLATFORM_OPTIONS = [
  { value: "youtube", label: "YouTube" },
  { value: "tiktok", label: "TikTok" },
  { value: "both", label: "Cả hai" },
];

const VOICE_OPTIONS = [
  { value: "nu_mien_bac", label: "Giọng nữ miền Bắc" },
  { value: "nam_mien_bac", label: "Giọng nam miền Bắc" },
];

function Section({ icon: Icon, title, children, collapsible = false }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="card space-y-4">
      <div
        className={`flex items-center justify-between ${collapsible ? "cursor-pointer" : ""}`}
        onClick={collapsible ? () => setOpen(o => !o) : undefined}
      >
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Icon size={16} className="text-red-400" /> {title}
        </h3>
        {collapsible && (open ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />)}
      </div>
      {open && children}
    </div>
  );
}

function FileUpload({ label, hint, accept, icon: Icon, uploadFn, value, onChange, uploading, setUploading }) {
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await uploadFn(file);
      onChange(res.path, file.name);
      toast.success(`Đã upload: ${file.name}`);
    } catch (e) {
      toast.error(`Upload thất bại: ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <label className="label">{label}</label>
      {value.path ? (
        <div className="flex items-center gap-2 p-2 bg-gray-800 rounded-lg border border-gray-700">
          <Icon size={16} className="text-green-400 flex-shrink-0" />
          <span className="text-sm text-gray-300 truncate flex-1">{value.name}</span>
          <button
            type="button"
            onClick={() => onChange("", "")}
            className="text-gray-500 hover:text-red-400 flex-shrink-0"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div
          onClick={() => !uploading && inputRef.current?.click()}
          className={`flex items-center gap-3 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
            uploading
              ? "border-gray-700 opacity-50 cursor-not-allowed"
              : "border-gray-700 hover:border-gray-500 hover:bg-gray-800/50"
          }`}
        >
          {uploading ? (
            <RefreshCw size={16} className="animate-spin text-gray-400" />
          ) : (
            <Upload size={16} className="text-gray-500" />
          )}
          <span className="text-sm text-gray-500">
            {uploading ? "Đang upload..." : `Chọn file ${accept}`}
          </span>
        </div>
      )}
      {hint && <p className="text-gray-600 text-xs mt-1">{hint}</p>}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => handleFile(e.target.files?.[0])}
      />
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
          className={`flex items-center gap-3 p-3 border-2 border-dashed rounded-lg cursor-pointer transition-colors flex-1 ${
            uploading
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
                    className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${
                      added
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

function VideoCard({ video, selected, onSelect }) {
  const views = video.view_count >= 1_000_000
    ? `${(video.view_count / 1_000_000).toFixed(1)}M`
    : video.view_count >= 1_000
    ? `${Math.round(video.view_count / 1_000)}K`
    : video.view_count?.toString() || "?";

  const usedLabel = video.used
    ? video.used_status === "uploaded" ? "Đã đăng" : "Đã có job"
    : null;

  return (
    <div
      onClick={() => onSelect(video)}
      className={`relative rounded-lg border cursor-pointer transition-all overflow-hidden ${
        selected
          ? "border-red-500 ring-2 ring-red-500/30 bg-red-600/5"
          : "border-gray-700 hover:border-gray-500 bg-gray-900"
      } ${video.used ? "opacity-60" : ""}`}
    >
      {usedLabel && (
        <span className={`absolute top-2 left-2 z-10 text-white text-[10px] font-medium px-1.5 py-0.5 rounded ${
          video.used_status === "uploaded" ? "bg-green-600" : "bg-yellow-600"
        }`}>
          ✓ {usedLabel}
        </span>
      )}
      {selected && (
        <div className="absolute top-2 right-2 z-10 bg-red-600 rounded-full p-0.5">
          <CheckCircle size={14} className="text-white" />
        </div>
      )}
      <div className="relative aspect-video bg-gray-800">
        {video.thumbnail ? (
          <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Video size={32} className="text-gray-600" />
          </div>
        )}
        {video.duration && (
          <span className="absolute bottom-1 right-1 bg-black/80 text-white text-xs px-1 rounded">
            {video.duration}
          </span>
        )}
      </div>
      <div className="p-2 space-y-1">
        <p className="text-white text-xs font-medium line-clamp-2 leading-tight">{video.title}</p>
        <div className="flex items-center gap-2 text-gray-500 text-xs">
          <span className="flex items-center gap-1"><Eye size={10} /> {views}</span>
          {video.uploader && <span className="truncate max-w-[80px]">{video.uploader}</span>}
        </div>
        {video.uploaded_ago && (
          <p className="flex items-center gap-1 text-gray-500 text-xs">
            <Clock size={9} /> {video.uploaded_ago}
            {video.upload_date && <span className="text-gray-700">· {video.upload_date}</span>}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Reup Mode ───────────────────────────────────────────────────────────────
function ReupForm({ channels, tiktokAccounts }) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [submitting, setSubmitting] = useState(false);
  const [manualUrl, setManualUrl] = useState("");
  const [channelUrl, setChannelUrl] = useState("");
  const [loadingChannel, setLoadingChannel] = useState(false);
  const [logoFile, setLogoFile] = useState({ path: "", name: "" });
  const [outroFile, setOutroFile] = useState({ path: "", name: "" });
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingOutro, setUploadingOutro] = useState(false);

  const { register, handleSubmit, watch, formState: { errors } } = useForm({
    defaultValues: {
      platform: "youtube",
      review_before_upload: true,
      privacy_status: "private",
      category_id: "22",
      custom_title: "",
      watermark_text: "",
      watermark_bottom: "",
      logo_position: "top-right",
      bg_music_volume: 0.08,
      original_volume: 1.0,
    },
  });

  const platform = watch("platform");

  const selectedVideos = searchResults.filter(v => selectedIds.has(v.id));

  const toggleSelect = (video) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(video.id)) next.delete(video.id);
      else next.add(video.id);
      return next;
    });
  };

  const selectAllUnused = () => {
    const ids = searchResults.filter(v => !v.used).map(v => v.id);
    if (!ids.length) {
      toast.error("Tất cả video đều đã đăng / đã có job");
      return;
    }
    setSelectedIds(new Set(ids));
    const skipped = searchResults.length - ids.length;
    toast.success(`Đã chọn ${ids.length} video${skipped ? ` (bỏ qua ${skipped} đã đăng)` : ""}`);
  };

  const clearSelection = () => setSelectedIds(new Set());

  const handleSearch = async () => {
    if (!searchQuery.trim()) return toast.error("Nhập từ khoá tìm kiếm");
    setSearching(true);
    setSelectedIds(new Set());
    try {
      const data = await autoCreatorApi.searchVideos(searchQuery, 10);
      setSearchResults(data.results || []);
      if (!data.results?.length) toast.error("Không tìm thấy video nào");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSearching(false);
    }
  };

  const handleFetchChannel = async () => {
    if (!channelUrl.trim()) return toast.error("Dán URL kênh Facebook/YouTube");
    setLoadingChannel(true);
    setSelectedIds(new Set());
    try {
      const data = await autoCreatorApi.channelVideos(channelUrl.trim(), 12);
      setSearchResults(data.results || []);
      if (!data.results?.length) {
        toast.error("Không lấy được video nào từ kênh này");
      } else {
        toast.success(`Đã lấy ${data.results.length} video từ kênh`);
      }
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoadingChannel(false);
    }
  };

  const onSubmit = async (data) => {
    // Branding + cấu hình chung áp dụng cho mọi video được chọn
    const branding = {
      channel_id: parseInt(data.channel_id),
      watermark_text: data.watermark_text || "",
      watermark_bottom: data.watermark_bottom || "",
      logo_path: logoFile.path || "",
      logo_position: data.logo_position || "top-right",
      outro_path: outroFile.path || "",
      bg_music_path: "",
      bg_music_volume: parseFloat(data.bg_music_volume) || 0.08,
      original_volume: parseFloat(data.original_volume) || 1.0,
      tiktok_account_id: data.tiktok_account_id ? parseInt(data.tiktok_account_id) : undefined,
      platform: data.platform,
      review_before_upload: data.review_before_upload,
      privacy_status: data.privacy_status,
      category_id: data.category_id,
    };

    // Xác định danh sách video cần reup
    let targets;
    if (selectedVideos.length > 0) {
      targets = selectedVideos.map(v => ({ url: v.url, title: v.title }));
    } else if (manualUrl.trim()) {
      targets = [{ url: manualUrl.trim(), title: null }];
    } else if (searchQuery.trim()) {
      targets = [{ url: undefined, title: searchQuery.trim() }]; // để backend tự tìm
    } else {
      return toast.error("Chọn ít nhất 1 video hoặc nhập URL video");
    }

    // custom_title chỉ áp dụng khi reup đúng 1 video (nhiều video sẽ giữ tiêu đề gốc)
    const customTitle = targets.length === 1 ? (data.custom_title?.trim() || undefined) : undefined;

    setSubmitting(true);
    let ok = 0, fail = 0;
    for (const t of targets) {
      try {
        await autoCreatorApi.reup({
          ...branding,
          topic: t.title || searchQuery.trim() || "video",
          source_video_url: t.url || undefined,
          custom_title: customTitle,
        });
        ok++;
      } catch {
        fail++;
      }
    }
    setSubmitting(false);

    if (ok) {
      toast.success(`Đã tạo ${ok} job reup${fail ? `, ${fail} lỗi` : ""}! Đang tải video...`);
      navigate("/queue");
    } else {
      toast.error(`Tạo job thất bại (${fail} lỗi)`);
    }
  };

  const authenticatedChannels = channels.filter(c => c.is_authenticated);
  const authenticatedTikTok = tiktokAccounts.filter(a => a.is_authenticated);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

      {/* Search */}
      <Section icon={Search} title="Tìm video trending">
        <div className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="VD: học tiếng Anh 2025, review iPhone 16..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && (e.preventDefault(), handleSearch())}
          />
          <button
            type="button"
            onClick={handleSearch}
            disabled={searching}
            className="btn-secondary px-4 flex-shrink-0"
          >
            {searching ? <RefreshCw size={16} className="animate-spin" /> : <Search size={16} />}
          </button>
        </div>

        {searchResults.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2 gap-2">
              <p className="text-gray-500 text-xs">
                {selectedIds.size > 0
                  ? `Đã chọn ${selectedIds.size} video`
                  : "Chọn video muốn reup (bấm để chọn nhiều):"}
              </p>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  type="button"
                  onClick={selectAllUnused}
                  className="text-xs text-red-400 hover:text-red-300 font-medium"
                >
                  Chọn tất cả (bỏ qua đã đăng)
                </button>
                {selectedIds.size > 0 && (
                  <button
                    type="button"
                    onClick={clearSelection}
                    className="text-xs text-gray-500 hover:text-gray-300"
                  >
                    Bỏ chọn
                  </button>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
              {searchResults.map(v => (
                <VideoCard
                  key={v.id}
                  video={v}
                  selected={selectedIds.has(v.id)}
                  onSelect={toggleSelect}
                />
              ))}
            </div>
          </div>
        )}

        {/* Facebook / channel URL */}
        <div className="border-t border-gray-800 pt-4">
          <label className="label flex items-center gap-1.5 text-blue-400">
            <Facebook size={14} /> Lấy reels từ URL kênh Facebook / YouTube
          </label>
          <div className="flex gap-2">
            <input
              className="input flex-1 text-sm"
              placeholder="https://www.facebook.com/profile.php?id=...&sk=reels_tab"
              value={channelUrl}
              onChange={e => setChannelUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && (e.preventDefault(), handleFetchChannel())}
            />
            <button
              type="button"
              onClick={handleFetchChannel}
              disabled={loadingChannel}
              className="btn-secondary px-4 flex-shrink-0"
            >
              {loadingChannel ? <RefreshCw size={16} className="animate-spin" /> : <Download size={16} />}
            </button>
          </div>
          <p className="text-gray-600 text-xs mt-1">
            Dán link tab Reels của kênh → lấy danh sách reel mới nhất để chọn reup.
            Facebook dùng cookies đăng nhập từ <code className="text-gray-500">facebook.com_cookies.txt</code> ở thư mục gốc.
          </p>
        </div>

        {/* Manual URL fallback */}
        <div>
          <label className="label text-xs text-gray-500">
            Hoặc dán URL 1 video / reel trực tiếp
          </label>
          <input
            className="input text-sm"
            placeholder="https://www.youtube.com/watch?v=...  ·  https://www.facebook.com/reel/..."
            value={manualUrl}
            onChange={e => setManualUrl(e.target.value)}
          />
        </div>

        {/* Custom title */}
        <div>
          <label className="label text-xs text-gray-500">
            Tiêu đề tự đặt (tuỳ chọn)
          </label>
          <input
            className="input text-sm"
            placeholder="Để trống = giữ tiêu đề gốc của video"
            maxLength={100}
            {...register("custom_title")}
          />
          <p className="text-gray-600 text-xs mt-1">
            Nhập tiêu đề riêng để đăng lên YouTube/TikTok thay vì dùng tên gốc.
          </p>
        </div>
      </Section>

      {/* Branding */}
      <Section icon={Video} title="Watermark & Branding" collapsible>
        <p className="text-xs text-gray-500">Nội dung video gốc giữ nguyên — chỉ thêm overlay nhẹ.</p>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Watermark góc trên trái</label>
            <input className="input" placeholder="@TênKênh" {...register("watermark_text")} />
          </div>
          <div>
            <label className="label">Text góc dưới phải</label>
            <input className="input" placeholder="Theo dõi ngay!" {...register("watermark_bottom")} />
          </div>
        </div>

        <FileUpload
          label="Logo (PNG/JPG)"
          hint="Logo sẽ được overlay lên video. Nên dùng PNG có nền trong suốt."
          accept=".png,.jpg,.jpeg,.webp"
          icon={Image}
          uploadFn={mediaApi.uploadLogo}
          value={logoFile}
          onChange={(path, name) => setLogoFile({ path, name })}
          uploading={uploadingLogo}
          setUploading={setUploadingLogo}
        />

        {logoFile.path && (
          <div>
            <label className="label">Vị trí logo</label>
            <select className="input" {...register("logo_position")}>
              <option value="top-right">Trên phải</option>
              <option value="top-left">Trên trái</option>
              <option value="bottom-right">Dưới phải</option>
              <option value="bottom-left">Dưới trái</option>
            </select>
          </div>
        )}
      </Section>

      {/* Outro & Music */}
      <Section icon={Film} title="Outro & Âm lượng" collapsible>
        <FileUpload
          label="Clip outro ghép vào cuối (MP4/MOV)"
          hint="Clip sẽ được ghép vào cuối video. Nên cùng độ phân giải với video gốc."
          accept=".mp4,.mov,.mkv,.webm"
          icon={Film}
          uploadFn={mediaApi.uploadOutro}
          value={outroFile}
          onChange={(path, name) => setOutroFile({ path, name })}
          uploading={uploadingOutro}
          setUploading={setUploadingOutro}
        />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Âm lượng nhạc nền ({Math.round((watch("bg_music_volume") || 0.08) * 100)}%)</label>
            <input type="range" min="0" max="0.5" step="0.01"
              className="w-full accent-red-500"
              {...register("bg_music_volume", { valueAsNumber: true })} />
          </div>
          <div>
            <label className="label">Âm lượng video gốc ({Math.round((watch("original_volume") || 1.0) * 100)}%)</label>
            <input type="range" min="0" max="1" step="0.05"
              className="w-full accent-red-500"
              {...register("original_volume", { valueAsNumber: true })} />
          </div>
        </div>
      </Section>

      {/* Platform & Channel */}
      <Section icon={TrendingUp} title="Kênh đăng">
        <div>
          <label className="label">Đăng lên</label>
          <div className="grid grid-cols-3 gap-2">
            {PLATFORM_OPTIONS.map(p => (
              <label key={p.value} className={`flex items-center justify-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors text-sm font-medium ${
                platform === p.value ? "border-red-500 bg-red-600/10 text-white" : "border-gray-700 text-gray-400 hover:border-gray-600"
              }`}>
                <input type="radio" value={p.value} {...register("platform")} className="hidden" />
                {p.label}
              </label>
            ))}
          </div>
        </div>

        {(platform === "youtube" || platform === "both") && (
          <div>
            <label className="label">Kênh YouTube *</label>
            <select className="input" {...register("channel_id", { required: platform !== "tiktok" })}>
              <option value="">-- Chọn kênh --</option>
              {authenticatedChannels.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        )}

        {(platform === "tiktok" || platform === "both") && (
          <div>
            <label className="label">Tài khoản TikTok</label>
            <select className="input" {...register("tiktok_account_id")}>
              <option value="">-- Chọn tài khoản --</option>
              {authenticatedTikTok.map(a => (
                <option key={a.id} value={a.id}>{a.display_name || a.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Privacy</label>
            <select className="input" {...register("privacy_status")}>
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" {...register("review_before_upload")} className="w-4 h-4 accent-red-500" />
              <span className="text-sm text-gray-300">Duyệt trước khi đăng</span>
            </label>
          </div>
        </div>
      </Section>

      <button
        type="submit"
        disabled={submitting || (selectedIds.size === 0 && !manualUrl && !searchQuery)}
        className="btn-primary w-full py-3 text-base"
      >
        <Download size={18} />
        {submitting
          ? "Đang tạo job..."
          : selectedIds.size > 1
          ? `Tải & Reup ${selectedIds.size} Video`
          : "Tải & Reup Video"}
      </button>

      <div className="card bg-gray-900/50 text-xs text-gray-500 space-y-1">
        <div className="text-gray-400 font-medium mb-2">Pipeline Reup (giữ nguyên nội dung):</div>
        <div>① Tìm / chọn video trending YouTube</div>
        <div>② Tải video gốc (yt-dlp, giữ nguyên chất lượng)</div>
        <div>③ Overlay watermark · ghép outro · mix nhạc nền (nếu có)</div>
        <div>④ {watch("review_before_upload") ? "Dừng để duyệt → ⑤ Đăng lên " + platform : "Upload thẳng lên " + platform}</div>
      </div>
    </form>
  );
}

// ─── AI Mode (giữ nguyên từ trước) ──────────────────────────────────────────
function AIForm({ channels, tiktokAccounts }) {
  const navigate = useNavigate();
  const [trendResult, setTrendResult] = useState(null);
  const [analyzingTrend, setAnalyzingTrend] = useState(false);
  const [logoFile, setLogoFile] = useState({ path: "", name: "" });
  const [outroFile, setOutroFile] = useState({ path: "", name: "" });
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingOutro, setUploadingOutro] = useState(false);
  const [extraClips, setExtraClips] = useState([]);
  const [uploadingClip, setUploadingClip] = useState(false);

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm({
    defaultValues: {
      topic: "",
      audience: "giới trẻ 18-30 tuổi",
      platform: "youtube",
      voice_key: "nu_mien_bac",
      duration_seconds: 60,
      review_before_upload: true,
      privacy_status: "private",
      category_id: "22",
      watermark_text: "",
      watermark_bottom: "",
      logo_position: "top-right",
      clip_position: "after",
    },
  });

  const platform = watch("platform");
  const topic = watch("topic");

  const { mutate: generate, isLoading } = useMutation(autoCreatorApi.generate, {
    onSuccess: (data) => {
      toast.success(`Job #${data.id} đã tạo! Pipeline đang chạy...`);
      navigate("/queue");
    },
    onError: (e) => toast.error(e.message),
  });

  const handleAnalyzeTrend = async () => {
    if (!topic) return toast.error("Nhập chủ đề trước");
    setAnalyzingTrend(true);
    try {
      const result = await autoCreatorApi.analyzeTrend({ topic, audience: watch("audience") });
      setTrendResult(result);
      toast.success("Phân tích trend xong!");
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAnalyzingTrend(false);
    }
  };

  const authenticatedChannels = channels.filter(c => c.is_authenticated);
  const authenticatedTikTok = tiktokAccounts.filter(a => a.is_authenticated);

  const TOPIC_SUGGESTIONS = [
    "tài chính cá nhân", "đầu tư chứng khoán", "review công nghệ",
    "làm đẹp da mặt", "giảm cân nhanh", "học tiếng Anh",
  ];

  const onSubmit = (data) => {
    generate({
      ...data,
      channel_id: parseInt(data.channel_id),
      tiktok_account_id: data.tiktok_account_id ? parseInt(data.tiktok_account_id) : undefined,
      duration_seconds: parseInt(data.duration_seconds),
      logo_path: logoFile.path || "",
      outro_path: outroFile.path || "",
      clip_paths: extraClips.map(c => c.path),
      clip_position: data.clip_position || "after",
    });
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <Section icon={TrendingUp} title="Chủ đề & Đối tượng">
        <div>
          <label className="label">Chủ đề video *</label>
          <input className="input" {...register("topic", { required: true })}
            placeholder="VD: tài chính cá nhân, review iPhone 16..." />
          {errors.topic && <p className="text-red-400 text-xs mt-1">Vui lòng nhập chủ đề</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {TOPIC_SUGGESTIONS.map(s => (
            <button key={s} type="button" onClick={() => setValue("topic", s)}
              className="px-2 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-full border border-gray-700">
              {s}
            </button>
          ))}
        </div>
        <div>
          <label className="label">Đối tượng khán giả</label>
          <input className="input" {...register("audience")} placeholder="VD: sinh viên, người đi làm 25-35 tuổi..." />
        </div>
        <button type="button" onClick={handleAnalyzeTrend} disabled={analyzingTrend || !topic}
          className="btn-secondary w-full">
          <TrendingUp size={16} />
          {analyzingTrend ? "Đang phân tích..." : "Phân tích Google Trends (tuỳ chọn)"}
        </button>
        {trendResult && (
          <div className="bg-gray-800 rounded-lg p-4 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Keyword hot nhất:</span>
              <span className="text-yellow-400 font-medium">{trendResult.best_keyword}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Điểm trend:</span>
              <span className="text-white">{trendResult.trend_score}/100</span>
            </div>
            {trendResult.content_angles?.length > 0 && (
              <div>
                <div className="text-gray-400 mb-1">Câu hỏi đang hot:</div>
                <div className="flex flex-wrap gap-1">
                  {trendResult.content_angles.slice(0, 5).map((q, i) => (
                    <span key={i} className="px-2 py-0.5 bg-gray-700 text-gray-300 rounded text-xs">{q}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Section>

      <Section icon={Video} title="Watermark & Branding" collapsible>
        <p className="text-xs text-gray-500">Overlay nhẹ lên video AI — không thay đổi nội dung.</p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Watermark góc trên trái</label>
            <input className="input" placeholder="@TênKênh" {...register("watermark_text")} />
          </div>
          <div>
            <label className="label">Text góc dưới phải</label>
            <input className="input" placeholder="Theo dõi ngay!" {...register("watermark_bottom")} />
          </div>
        </div>
        <FileUpload
          label="Logo (PNG/JPG)"
          hint="PNG có nền trong suốt sẽ trông đẹp hơn."
          accept=".png,.jpg,.jpeg,.webp"
          icon={Image}
          uploadFn={mediaApi.uploadLogo}
          value={logoFile}
          onChange={(path, name) => setLogoFile({ path, name })}
          uploading={uploadingLogo}
          setUploading={setUploadingLogo}
        />
        {logoFile.path && (
          <div>
            <label className="label">Vị trí logo</label>
            <select className="input" {...register("logo_position")}>
              <option value="top-right">Trên phải</option>
              <option value="top-left">Trên trái</option>
              <option value="bottom-right">Dưới phải</option>
              <option value="bottom-left">Dưới trái</option>
            </select>
          </div>
        )}
        <FileUpload
          label="Clip outro ghép vào cuối (MP4/MOV)"
          hint="Clip sẽ được ghép sau phần AI render."
          accept=".mp4,.mov,.mkv,.webm"
          icon={Film}
          uploadFn={mediaApi.uploadOutro}
          value={outroFile}
          onChange={(path, name) => setOutroFile({ path, name })}
          uploading={uploadingOutro}
          setUploading={setUploadingOutro}
        />
      </Section>

      <Section icon={Film} title="Ghép Video Clips" collapsible>
        <p className="text-xs text-gray-500">Upload các clip để ghép với video AI theo thứ tự bạn chọn.</p>

        <div>
          <label className="label">Vị trí ghép</label>
          <div className="grid grid-cols-2 gap-2">
            {[{ v: "before", l: "Trước video AI" }, { v: "after", l: "Sau video AI" }].map(o => (
              <label key={o.v} className={`flex items-center justify-center p-2 rounded border cursor-pointer text-sm transition-colors ${
                watch("clip_position") === o.v
                  ? "border-blue-500 bg-blue-600/10 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-600"
              }`}>
                <input type="radio" value={o.v} {...register("clip_position")} className="hidden" />
                {o.l}
              </label>
            ))}
          </div>
        </div>

        <MultiClipUpload
          clips={extraClips}
          onAdd={clip => setExtraClips(prev => [...prev, clip])}
          onRemove={i => setExtraClips(prev => prev.filter((_, idx) => idx !== i))}
          uploading={uploadingClip}
          setUploading={setUploadingClip}
        />
      </Section>

      <Section icon={Video} title="Kênh & Cài đặt">
        <div>
          <label className="label">Đăng lên</label>
          <div className="grid grid-cols-3 gap-2">
            {PLATFORM_OPTIONS.map(p => (
              <label key={p.value} className={`flex items-center justify-center gap-2 p-3 rounded-lg border cursor-pointer text-sm font-medium ${
                platform === p.value ? "border-red-500 bg-red-600/10 text-white" : "border-gray-700 text-gray-400 hover:border-gray-600"
              }`}>
                <input type="radio" value={p.value} {...register("platform")} className="hidden" />
                {p.label}
              </label>
            ))}
          </div>
        </div>
        {(platform === "youtube" || platform === "both") && (
          <div>
            <label className="label">Kênh YouTube *</label>
            <select className="input" {...register("channel_id", { required: platform !== "tiktok" })}>
              <option value="">-- Chọn kênh --</option>
              {authenticatedChannels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        )}
        {(platform === "tiktok" || platform === "both") && (
          <div>
            <label className="label">Tài khoản TikTok</label>
            <select className="input" {...register("tiktok_account_id")}>
              <option value="">-- Chọn tài khoản --</option>
              {authenticatedTikTok.map(a => <option key={a.id} value={a.id}>{a.display_name || a.name}</option>)}
            </select>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Giọng đọc</label>
            <select className="input" {...register("voice_key")}>
              {VOICE_OPTIONS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Thời lượng</label>
            <select className="input" {...register("duration_seconds")}>
              <option value={30}>30 giây</option>
              <option value={45}>45 giây</option>
              <option value={60}>60 giây</option>
              <option value={90}>90 giây</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Privacy</label>
            <select className="input" {...register("privacy_status")}>
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" {...register("review_before_upload")} className="w-4 h-4 accent-red-500" />
              <span className="text-sm text-gray-300">Duyệt trước khi đăng</span>
            </label>
          </div>
        </div>
      </Section>

      <button
        type="submit"
        disabled={isLoading || (!watch("channel_id") && platform !== "tiktok")}
        className="btn-primary w-full py-3 text-base"
      >
        <Zap size={18} />
        {isLoading ? "Đang khởi động..." : "Tạo Video Tự Động (AI)"}
      </button>

      <div className="card bg-gray-900/50 text-xs text-gray-500 space-y-1">
        <div className="text-gray-400 font-medium mb-2">Pipeline AI:</div>
        <div>① Phân tích Google Trends → ② Claude AI viết script</div>
        <div>③ Edge TTS tạo giọng đọc → ④ FFmpeg render video 9:16</div>
        <div>⑤ {watch("review_before_upload") ? "Dừng để duyệt → ⑥ Đăng lên " + platform : "Upload thẳng lên " + platform}</div>
      </div>
    </form>
  );
}

// ─── Main page ───────────────────────────────────────────────────────────────
export default function AutoCreator() {
  const [mode, setMode] = useState("reup"); // "reup" | "ai"
  const { data: channels = [] } = useQuery("channels", channelsApi.list);
  const { data: tiktokAccounts = [] } = useQuery("tiktok-accounts", tiktokApi.listAccounts);

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Zap size={24} className="text-yellow-400" /> Tạo Video Tự Động
        </h1>
        <p className="text-gray-500 text-sm mt-1">
          Tìm video trending → Tải về → Thêm branding → Upload
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2 p-1 bg-gray-800 rounded-lg">
        <button
          onClick={() => setMode("reup")}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "reup" ? "bg-red-600 text-white" : "text-gray-400 hover:text-gray-300"
          }`}
        >
          <Download size={15} /> Reup Trending
        </button>
        <button
          onClick={() => setMode("ai")}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "ai" ? "bg-red-600 text-white" : "text-gray-400 hover:text-gray-300"
          }`}
        >
          <Zap size={15} /> AI Tạo Mới
        </button>
      </div>

      {mode === "reup"
        ? <ReupForm channels={channels} tiktokAccounts={tiktokAccounts} />
        : <AIForm channels={channels} tiktokAccounts={tiktokAccounts} />
      }
    </div>
  );
}

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import toast, { Toaster } from "react-hot-toast";
import { tiktokApi, apiUrl } from "../api";
import { Plus, Trash2, Link, Unlink, Music2 } from "lucide-react";
import { useEffect } from "react";

export default function TikTokAccounts() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const [showAdd, setShowAdd] = useState(false);
  const { register, handleSubmit, reset } = useForm();

  const { data: accounts = [], isLoading } = useQuery("tiktok-accounts", tiktokApi.listAccounts);

  useEffect(() => {
    const oauth = searchParams.get("oauth");
    if (oauth === "success") toast.success("Kết nối TikTok thành công!");
    if (oauth === "error") toast.error(`Lỗi kết nối: ${searchParams.get("msg") || "unknown"}`);
  }, [searchParams]);

  const mutCreate = useMutation(tiktokApi.createAccount, {
    onSuccess: () => { qc.invalidateQueries("tiktok-accounts"); setShowAdd(false); reset(); },
    onError: (e) => toast.error(e.message),
  });

  const mutDelete = useMutation(tiktokApi.deleteAccount, {
    onSuccess: () => { toast.success("Đã xoá tài khoản"); qc.invalidateQueries("tiktok-accounts"); },
  });

  const handleOAuth = async (accountId) => {
    try {
      const { auth_url } = await tiktokApi.startOAuth(accountId);
      window.location.href = auth_url;
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Music2 size={22} className="text-pink-400" /> TikTok Accounts
          </h1>
          <p className="text-gray-500 text-sm mt-1">Kết nối tài khoản TikTok qua Content Posting API</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          <Plus size={16} /> Thêm tài khoản
        </button>
      </div>

      {/* Setup notice */}
      <div className="card border-yellow-600/30 bg-yellow-900/10 text-sm space-y-2">
        <div className="text-yellow-400 font-medium">⚠️ Yêu cầu cài đặt TikTok API</div>
        <div className="text-gray-400 space-y-1 text-xs">
          <div>1. Vào <span className="text-blue-400">developers.tiktok.com</span> → Tạo app → Bật <strong>Content Posting API</strong></div>
          <div>2. Thêm vào <span className="text-gray-300">.env</span>: <code className="bg-gray-800 px-1 rounded">TIKTOK_CLIENT_KEY=...</code> và <code className="bg-gray-800 px-1 rounded">TIKTOK_CLIENT_SECRET=...</code></div>
          <div>3. Redirect URI: <code className="bg-gray-800 px-1 rounded">{apiUrl("/tiktok/oauth/callback")}</code> (giá trị TIKTOK_REDIRECT_URI trong .env backend)</div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Đang tải...</div>
      ) : accounts.length === 0 ? (
        <div className="card text-center py-10 text-gray-500">
          Chưa có tài khoản TikTok nào. Thêm tài khoản để bắt đầu.
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map(acc => (
            <div key={acc.id} className="card flex items-center gap-4">
              {acc.avatar_url ? (
                <img src={acc.avatar_url} className="w-12 h-12 rounded-full" alt="" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-pink-900/40 flex items-center justify-center text-pink-400 text-lg font-bold">
                  {acc.name[0].toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="text-white font-medium">{acc.display_name || acc.name}</div>
                <div className="text-gray-500 text-xs">
                  {acc.is_authenticated
                    ? `✅ Đã kết nối${acc.open_id ? ` · ${acc.open_id.slice(0, 8)}...` : ""}`
                    : "⚠️ Chưa kết nối OAuth"}
                </div>
                {acc.token_expires_at && (
                  <div className="text-gray-600 text-xs">
                    Token hết hạn: {new Date(acc.token_expires_at).toLocaleDateString("vi-VN")}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {acc.is_authenticated ? (
                  <span className="px-2 py-1 text-xs bg-pink-900/30 text-pink-400 border border-pink-700/40 rounded-lg">
                    Đã kết nối
                  </span>
                ) : (
                  <button onClick={() => handleOAuth(acc.id)} className="btn-primary py-1.5 text-xs">
                    <Link size={14} /> Kết nối OAuth
                  </button>
                )}
                <button
                  onClick={() => { if (confirm("Xoá tài khoản này?")) mutDelete.mutate(acc.id); }}
                  className="btn-ghost p-2 text-red-500"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="card w-full max-w-sm space-y-4">
            <h2 className="text-white font-semibold text-lg">Thêm tài khoản TikTok</h2>
            <form onSubmit={handleSubmit(d => mutCreate.mutate(d))} className="space-y-3">
              <div>
                <label className="label">Tên tài khoản (để phân biệt)</label>
                <input className="input" {...register("name", { required: true })} placeholder="VD: Kênh chính, Kênh phụ..." />
              </div>
              <div className="flex gap-2">
                <button type="submit" className="btn-primary flex-1">Tạo</button>
                <button type="button" onClick={() => { setShowAdd(false); reset(); }} className="btn-secondary flex-1">Huỷ</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

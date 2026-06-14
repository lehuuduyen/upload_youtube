import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { templatesApi } from "../api";
import { Plus, Trash2, Edit, FileText } from "lucide-react";

const PRIVACY_OPTIONS = [
  { value: "private", label: "Private" },
  { value: "unlisted", label: "Unlisted" },
  { value: "public", label: "Public" },
];

function TemplateModal({ template, onClose, onSaved }) {
  const isEdit = !!template;
  const { register, handleSubmit } = useForm({
    defaultValues: template ? {
      ...template,
      tags: Array.isArray(template.tags) ? template.tags.join(", ") : (template.tags || ""),
    } : {
      category_id: "22",
      privacy_status: "private",
      language: "vi",
      default_music_volume: "0.8",
      default_original_volume: "0.2",
    },
  });
  const mutateFn = isEdit ? (d) => templatesApi.update(template.id, d) : templatesApi.create;
  const { mutate, isLoading } = useMutation(mutateFn, {
    onSuccess: () => { toast.success(isEdit ? "Đã cập nhật!" : "Đã tạo template!"); onSaved(); },
    onError: (e) => toast.error(e.message),
  });

  const onSubmit = (data) => {
    const rawTags = Array.isArray(data.tags) ? data.tags.join(",") : (data.tags || "");
    const payload = {
      ...data,
      tags: rawTags.split(",").map(t => t.trim()).filter(Boolean),
    };
    mutate(payload);
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg p-6 space-y-4 overflow-y-auto max-h-[90vh]">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <FileText size={18} className="text-red-400" />
          {isEdit ? "Chỉnh sửa template" : "Tạo template mới"}
        </h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div>
            <label className="label">Tên template *</label>
            <input className="input" {...register("name", { required: true })} placeholder="Template kênh nhạc" />
          </div>
          <div>
            <label className="label">Tiêu đề mặc định</label>
            <input className="input" {...register("title_template")} placeholder="Video #{date}" />
            <p className="text-xs text-gray-600 mt-1">Biến: {"{date}"} = ngày hiện tại</p>
          </div>
          <div>
            <label className="label">Mô tả mặc định</label>
            <textarea className="input" rows={3} {...register("description_template")} placeholder="Mô tả video..." />
          </div>
          <div>
            <label className="label">Tags mặc định (phân cách bởi dấu phẩy)</label>
            <input className="input" {...register("tags")} placeholder="nhạc, chill, lofi" />
          </div>
          <div className="grid grid-cols-2 gap-3">
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
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Âm lượng nhạc mặc định</label>
              <input className="input" {...register("default_music_volume")} placeholder="0.8" />
            </div>
            <div>
              <label className="label">Âm lượng gốc mặc định</label>
              <input className="input" {...register("default_original_volume")} placeholder="0.2" />
            </div>
          </div>
          <div>
            <label className="label">Mô tả template</label>
            <input className="input" {...register("description")} placeholder="Mô tả template này dùng cho gì..." />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Huỷ</button>
            <button type="submit" disabled={isLoading} className="btn-primary flex-1">
              {isLoading ? "Đang lưu..." : "Lưu"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Templates() {
  const qc = useQueryClient();
  const [modal, setModal] = useState(null); // null | "add" | template object

  const { data: templates = [], isLoading } = useQuery("templates", templatesApi.list);

  const mutDelete = useMutation(templatesApi.delete, {
    onSuccess: () => { toast.success("Đã xoá template"); qc.invalidateQueries("templates"); },
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Templates Metadata</h1>
        <button onClick={() => setModal("add")} className="btn-primary">
          <Plus size={18} /> Tạo template
        </button>
      </div>

      <p className="text-sm text-gray-500">
        Templates giúp bạn tái sử dụng tiêu đề, mô tả, tags cho nhiều video mà không cần nhập lại.
      </p>

      {isLoading ? (
        <div className="text-gray-500">Đang tải...</div>
      ) : templates.length === 0 ? (
        <div className="card text-center py-10 text-gray-500">
          <FileText size={40} className="mx-auto mb-3 opacity-30" />
          <p>Chưa có template nào</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {templates.map(t => (
            <div key={t.id} className="card space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium text-white">{t.name}</div>
                  {t.description && <div className="text-xs text-gray-500">{t.description}</div>}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => setModal(t)} className="btn-ghost p-2">
                    <Edit size={14} />
                  </button>
                  <button onClick={() => { if (confirm("Xoá template?")) mutDelete.mutate(t.id); }} className="btn-ghost p-2 text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {t.title_template && (
                <div className="text-sm">
                  <span className="text-gray-500">Tiêu đề: </span>
                  <span className="text-gray-300">{t.title_template}</span>
                </div>
              )}
              {t.tags?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {t.tags.slice(0, 6).map(tag => (
                    <span key={tag} className="bg-gray-800 text-gray-400 text-xs px-2 py-0.5 rounded">{tag}</span>
                  ))}
                  {t.tags.length > 6 && <span className="text-gray-600 text-xs">+{t.tags.length - 6}</span>}
                </div>
              )}
              <div className="flex gap-4 text-xs text-gray-600">
                <span>Privacy: <span className="text-gray-400">{t.privacy_status}</span></span>
                <span>Ngôn ngữ: <span className="text-gray-400">{t.language}</span></span>
                <span>Nhạc: <span className="text-gray-400">{Math.round(parseFloat(t.default_music_volume) * 100)}%</span></span>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <TemplateModal
          template={modal === "add" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); qc.invalidateQueries("templates"); }}
        />
      )}
    </div>
  );
}

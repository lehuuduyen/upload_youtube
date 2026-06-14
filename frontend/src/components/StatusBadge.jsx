import clsx from "clsx";

const STATUS_CONFIG = {
  pending:     { label: "Chờ",         color: "bg-gray-700 text-gray-300" },
  downloading: { label: "Đang tải",    color: "bg-blue-900 text-blue-300" },
  processing:  { label: "Xử lý",       color: "bg-yellow-900 text-yellow-300" },
  ready:       { label: "Sẵn sàng",    color: "bg-teal-900 text-teal-300" },
  queued:      { label: "Trong hàng",  color: "bg-purple-900 text-purple-300" },
  uploading:   { label: "Đang upload", color: "bg-blue-900 text-blue-200 animate-pulse" },
  uploaded:    { label: "Đã upload",   color: "bg-green-900 text-green-300" },
  failed:      { label: "Lỗi",         color: "bg-red-900 text-red-300" },
  cancelled:   { label: "Huỷ",         color: "bg-gray-800 text-gray-500" },
};

export default function StatusBadge({ status, className }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: "bg-gray-700 text-gray-400" };
  return (
    <span className={clsx("badge", cfg.color, className)}>
      {cfg.label}
    </span>
  );
}

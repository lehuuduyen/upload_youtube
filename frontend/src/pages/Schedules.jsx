import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { schedulesApi, channelsApi } from "../api";
import { Plus, Pause, Play, Trash2, Clock } from "lucide-react";

const CRON_PRESETS = [
  { label: "8h sáng mỗi ngày", value: "0 8 * * *" },
  { label: "12h trưa mỗi ngày", value: "0 12 * * *" },
  { label: "18h tối mỗi ngày", value: "0 18 * * *" },
  { label: "Mỗi 6 giờ", value: "0 */6 * * *" },
  { label: "Mỗi 12 giờ", value: "0 */12 * * *" },
  { label: "Thứ 2, 4, 6 lúc 8h", value: "0 8 * * 1,3,5" },
  { label: "Cuối tuần lúc 10h", value: "0 10 * * 6,0" },
];

const TIMEZONES = ["Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Singapore", "UTC", "America/New_York", "America/Phoenix"];

function ScheduleCard({ schedule, onPause, onResume, onDelete }) {
  return (
    <div className="card space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-medium text-white">{schedule.name}</div>
          <div className="text-xs text-gray-500 mt-0.5">Kênh #{schedule.channel_id}</div>
        </div>
        <span className={`badge text-xs ${schedule.is_active ? "bg-green-900 text-green-300" : "bg-gray-800 text-gray-500"}`}>
          {schedule.is_active ? "Đang chạy" : "Tạm dừng"}
        </span>
      </div>

      <div className="bg-gray-800 rounded-lg px-3 py-2 font-mono text-sm text-yellow-300">
        {schedule.cron_expression}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
        <span>Timezone: <span className="text-gray-300">{schedule.timezone}</span></span>
        <span>Interval: <span className="text-gray-300">{schedule.min_interval_minutes}m</span></span>
        <span>Chạy lần cuối: <span className="text-gray-300">{schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString("vi-VN") : "Chưa"}</span></span>
        <span>Lần tiếp theo: <span className="text-gray-300">{schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString("vi-VN") : "—"}</span></span>
      </div>

      <div className="flex gap-2">
        {schedule.is_active ? (
          <button onClick={() => onPause(schedule.id)} className="btn-secondary text-xs flex-1">
            <Pause size={14} /> Tạm dừng
          </button>
        ) : (
          <button onClick={() => onResume(schedule.id)} className="btn-primary text-xs flex-1">
            <Play size={14} /> Tiếp tục
          </button>
        )}
        <button onClick={() => onDelete(schedule.id)} className="btn-danger text-xs">
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

function AddScheduleModal({ channels, onClose, onCreated }) {
  const { register, handleSubmit, watch, setValue } = useForm({
    defaultValues: { timezone: "Asia/Ho_Chi_Minh", min_interval_minutes: 30, cron_expression: "0 8 * * *" },
  });
  const { mutate, isLoading } = useMutation(schedulesApi.create, {
    onSuccess: (data) => { toast.success("Đã tạo lịch!"); onCreated(data); },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Clock size={18} className="text-red-400" /> Tạo lịch đăng
        </h2>
        <form onSubmit={handleSubmit(mutate)} className="space-y-3">
          <div>
            <label className="label">Tên lịch *</label>
            <input className="input" {...register("name", { required: true })} placeholder="Đăng sáng hàng ngày" />
          </div>
          <div>
            <label className="label">Kênh *</label>
            <select className="input" {...register("channel_id", { required: true })}>
              <option value="">-- Chọn kênh --</option>
              {channels.filter(c => c.is_authenticated).map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Preset lịch</label>
            <select className="input" onChange={e => e.target.value && setValue("cron_expression", e.target.value)}>
              <option value="">-- Chọn preset --</option>
              {CRON_PRESETS.map(p => <option key={p.value} value={p.value}>{p.label} ({p.value})</option>)}
            </select>
          </div>
          <div>
            <label className="label">Cron expression *</label>
            <input className="input font-mono" {...register("cron_expression", { required: true })} placeholder="0 8 * * *" />
            <p className="text-xs text-gray-600 mt-1">Định dạng: phút giờ ngày tháng thứ</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Timezone</label>
              <select className="input" {...register("timezone")}>
                {TIMEZONES.map(tz => <option key={tz}>{tz}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Khoảng cách tối thiểu (phút)</label>
              <input type="number" className="input" {...register("min_interval_minutes")} min={0} />
            </div>
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1">Huỷ</button>
            <button type="submit" disabled={isLoading} className="btn-primary flex-1">
              {isLoading ? "Đang tạo..." : "Tạo lịch"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function Schedules() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: channels = [] } = useQuery("channels", channelsApi.list);
  const { data: schedules = [], isLoading } = useQuery("schedules", schedulesApi.list);

  const mutPause = useMutation(schedulesApi.pause, {
    onSuccess: () => { toast.success("Đã tạm dừng"); qc.invalidateQueries("schedules"); },
  });
  const mutResume = useMutation(schedulesApi.resume, {
    onSuccess: () => { toast.success("Đã tiếp tục"); qc.invalidateQueries("schedules"); },
  });
  const mutDelete = useMutation(schedulesApi.delete, {
    onSuccess: () => { toast.success("Đã xoá lịch"); qc.invalidateQueries("schedules"); },
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Lịch Đăng Video</h1>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          <Plus size={18} /> Tạo lịch
        </button>
      </div>

      {/* Cron reference */}
      <div className="card bg-gray-900/50 text-xs text-gray-500">
        <div className="font-medium text-gray-400 mb-2">Tham khảo cron expression:</div>
        <div className="font-mono space-y-1">
          <div><span className="text-yellow-400">0 8 * * *</span> — 8h sáng mỗi ngày</div>
          <div><span className="text-yellow-400">0 */6 * * *</span> — Mỗi 6 giờ</div>
          <div><span className="text-yellow-400">0 8 * * 1,3,5</span> — Thứ 2,4,6 lúc 8h</div>
          <div><span className="text-yellow-400">30 18 * * *</span> — 18:30 mỗi ngày</div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-500">Đang tải...</div>
      ) : schedules.length === 0 ? (
        <div className="card text-center py-10 text-gray-500">Chưa có lịch nào</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {schedules.map(s => (
            <ScheduleCard
              key={s.id}
              schedule={s}
              onPause={(id) => mutPause.mutate(id)}
              onResume={(id) => mutResume.mutate(id)}
              onDelete={(id) => { if (confirm("Xoá lịch này?")) mutDelete.mutate(id); }}
            />
          ))}
        </div>
      )}

      {showAdd && (
        <AddScheduleModal
          channels={channels}
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); qc.invalidateQueries("schedules"); }}
        />
      )}
    </div>
  );
}

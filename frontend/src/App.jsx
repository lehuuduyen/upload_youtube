import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Channels from "./pages/Channels";
import NewJob from "./pages/NewJob";
import Queue from "./pages/Queue";
import Schedules from "./pages/Schedules";
import Templates from "./pages/Templates";
import AutoCreator from "./pages/AutoCreator";
import TikTokAccounts from "./pages/TikTokAccounts";
import MovieDownloader from "./pages/MovieDownloader";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/channels" element={<Channels />} />
        <Route path="/new-job" element={<NewJob />} />
        <Route path="/movie-downloader" element={<MovieDownloader />} />
        <Route path="/queue" element={<Queue />} />
        <Route path="/schedules" element={<Schedules />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/auto-creator" element={<AutoCreator />} />
        <Route path="/tiktok" element={<TikTokAccounts />} />
      </Routes>
    </Layout>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createBatch,
  listBatches,
  createJD,
  listJDs,
  rankCVs,
  getDashboard,
  type BatchListItem,
  type JDListItem,
  type RankedResumeItem,
} from "@/lib/api";
import { DashboardLayout } from "@/components/DashboardLayout";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-amber-100 text-amber-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-emerald-100 text-emerald-800",
    failed: "bg-red-100 text-red-800",
    processed: "bg-emerald-100 text-emerald-800",
  };
  const cls = styles[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {status}
    </span>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem("token")) router.replace("/login");
  }, [router]);

  const [batchName, setBatchName] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [jdTitle, setJdTitle] = useState("");
  const [jdText, setJdText] = useState("");
  const [selectedJdId, setSelectedJdId] = useState("");
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [minScore, setMinScore] = useState<number | "">("");
  const [limit, setLimit] = useState(50);
  const [rankResult, setRankResult] = useState<{
    run_id: string;
    results: RankedResumeItem[];
    total_count: number;
  } | null>(null);

  const { data: batchesData } = useQuery({
    queryKey: ["batches"],
    queryFn: () => listBatches(1, 100).then((r) => r.data),
  });
  const { data: jdsData } = useQuery({
    queryKey: ["jds"],
    queryFn: () => listJDs(1, 100).then((r) => r.data),
  });
  const { data: dashboardData } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => getDashboard().then((r) => r.data),
  });

  const uploadMutation = useMutation({
    mutationFn: (fd: FormData) => createBatch(fd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["batches"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setFiles(null);
      setBatchName("");
    },
  });
  const jdMutation = useMutation({
    mutationFn: ({ title, raw_text }: { title: string; raw_text: string }) => createJD(title, raw_text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jds"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setJdTitle("");
      setJdText("");
    },
  });
  const rankMutation = useMutation({
    mutationFn: (body: { jd_id: string; batch_id?: string; limit?: number; min_score?: number }) =>
      rankCVs(body),
    onSuccess: (res) => {
      setRankResult({
        run_id: res.data.run_id,
        results: res.data.results,
        total_count: res.data.total_count,
      });
    },
  });

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!files?.length) return;
    const fd = new FormData();
    if (batchName) fd.append("batch_name", batchName);
    for (let i = 0; i < files.length; i++) fd.append("files", files[i]);
    uploadMutation.mutate(fd);
  };
  const handleCreateJD = (e: React.FormEvent) => {
    e.preventDefault();
    if (!jdTitle.trim() || !jdText.trim()) return;
    jdMutation.mutate({ title: jdTitle, raw_text: jdText });
  };
  const handleRank = () => {
    if (!selectedJdId) return;
    rankMutation.mutate({
      jd_id: selectedJdId,
      batch_id: selectedBatchId || undefined,
      limit,
      min_score: minScore === "" ? undefined : Number(minScore),
    });
  };

  const batches: BatchListItem[] = batchesData?.items ?? [];
  const jds: JDListItem[] = jdsData?.items ?? [];
  const dash = dashboardData;

  // Build chart data for the last N days. Use UTC dates for keys to match backend (PostgreSQL date() in UTC).
  const CHART_DAYS = 14;
  const chartData = (() => {
    const now = new Date();
    const uploadsMap = new Map<string, number>();
    const runsMap = new Map<string, number>();
    const jdsMap = new Map<string, number>();
    (dash?.uploads_by_date ?? []).forEach((d: { date: string; count: number }) => uploadsMap.set(d.date, d.count));
    (dash?.runs_by_date ?? []).forEach((d: { date: string; count: number }) => runsMap.set(d.date, d.count));
    (dash?.jds_by_date ?? []).forEach((d: { date: string; count: number }) => jdsMap.set(d.date, d.count));
    const rows: { date: string; label: string; uploads: number; runs: number; jds: number }[] = [];
    for (let i = CHART_DAYS - 1; i >= 0; i--) {
      const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - i));
      const dateStr = d.toISOString().slice(0, 10);
      const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      rows.push({
        date: dateStr,
        label,
        uploads: uploadsMap.get(dateStr) ?? 0,
        runs: runsMap.get(dateStr) ?? 0,
        jds: jdsMap.get(dateStr) ?? 0,
      });
    }
    return rows;
  })();

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload CVs, add a job description, and rank candidates by semantic fit.
          </p>
        </div>

        {/* Analytics */}
        {dash && (
          <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
            <h2 className="mb-4 text-lg font-semibold text-slate-900">Analytics</h2>
            <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { label: "Resumes", value: dash.total_resumes },
                { label: "Batches", value: dash.total_batches },
                { label: "Job Descriptions", value: dash.total_jds },
                { label: "Screening Runs", value: dash.total_runs },
              ].map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-xl border border-slate-100 bg-slate-50/80 p-4 transition hover:border-slate-200 hover:shadow-card-hover"
                >
                  <p className="text-sm font-medium text-slate-500">{label}</p>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
                </div>
              ))}
            </div>
            <div className="h-72">
              <p className="mb-2 text-sm text-slate-500">Activity per day (last {CHART_DAYS} days)</p>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: "#e2e8f0" }}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={24}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: "0.5rem",
                      border: "1px solid #e2e8f0",
                      boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.08)",
                    }}
                    labelFormatter={(_, payload) => payload[0]?.payload?.date}
                  />
                  <Bar
                    dataKey="uploads"
                    fill="#4f46e5"
                    name="Batches"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Bar
                    dataKey="runs"
                    fill="#f97316"
                    name="Runs"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Bar
                    dataKey="jds"
                    fill="#22d3ee"
                    name="JDs"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Legend
                    wrapperStyle={{ paddingTop: "8px" }}
                    formatter={(value) => <span className="text-sm text-slate-600">{value}</span>}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Upload CVs */}
        <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Upload CVs</h2>
          <p className="mb-4 text-sm text-slate-500">Upload PDF or DOCX files. One batch can contain multiple CVs.</p>
          <form onSubmit={handleUpload} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Batch name (optional)</label>
              <input
                type="text"
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                className="w-full max-w-md rounded-lg border border-slate-300 px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                placeholder="e.g. January 2025"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Files</label>
              <input
                type="file"
                accept=".pdf,.docx"
                multiple
                onChange={(e) => setFiles(e.target.files)}
                className="block w-full max-w-md text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-primary-50 file:px-4 file:py-2 file:font-medium file:text-primary-700 file:transition file:hover:bg-primary-100"
              />
            </div>
            <button
              type="submit"
              disabled={!files?.length || uploadMutation.isPending}
              className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-primary-700 focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {uploadMutation.isPending ? "Uploading…" : "Upload"}
            </button>
            {uploadMutation.isError && (
              <p className="text-sm text-red-600">Upload failed. Check file types (PDF/DOCX) and size.</p>
            )}
            {batches.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-sm font-medium text-slate-700">Recent batches</p>
                <ul className="flex flex-wrap gap-2">
                  {batches.slice(0, 5).map((b) => (
                    <li
                      key={b.id}
                      className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 text-sm"
                    >
                      <span className="font-medium text-slate-800">
                        {b.batch_name?.trim() || `Batch ${b.id.slice(0, 8)}`}
                      </span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-600">{b.resume_count} CVs</span>
                      <StatusBadge status={b.status} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </form>
        </section>

        {/* Job Description */}
        <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Job Description</h2>
          <p className="mb-4 text-sm text-slate-500">Add a JD to rank CVs against. Paste the full text below.</p>
          <form onSubmit={handleCreateJD} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Title</label>
              <input
                type="text"
                value={jdTitle}
                onChange={(e) => setJdTitle(e.target.value)}
                required
                className="w-full max-w-md rounded-lg border border-slate-300 px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                placeholder="e.g. Senior Backend Engineer"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Description (full JD text)</label>
              <textarea
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                required
                rows={6}
                className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                placeholder="Paste the full job description here..."
              />
            </div>
            <button
              type="submit"
              disabled={jdMutation.isPending}
              className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-primary-700 focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {jdMutation.isPending ? "Saving…" : "Save JD"}
            </button>
          </form>
        </section>

        {/* Rank CVs */}
        <section className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Rank CVs</h2>
          <p className="mb-4 text-sm text-slate-500">
            Select a job description and optionally a batch. Results are ordered by similarity score.
          </p>
          <div className="mb-6 flex flex-wrap items-end gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Job Description</label>
              <select
                value={selectedJdId}
                onChange={(e) => setSelectedJdId(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              >
                <option value="">Select JD</option>
                {jds.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Batch (optional)</label>
              <select
                value={selectedBatchId}
                onChange={(e) => setSelectedBatchId(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              >
                <option value="">All batches</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.batch_name?.trim() || `Batch ${b.id.slice(0, 8)}`} — {b.resume_count} CVs ({b.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Min score (0–1)</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={minScore}
                onChange={(e) => setMinScore(e.target.value === "" ? "" : Number(e.target.value))}
                className="w-24 rounded-lg border border-slate-300 px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Limit</label>
              <input
                type="number"
                min={1}
                max={200}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-20 rounded-lg border border-slate-300 px-3.5 py-2.5 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
              />
            </div>
            <button
              type="button"
              onClick={handleRank}
              disabled={!selectedJdId || rankMutation.isPending}
              className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-primary-700 focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {rankMutation.isPending ? "Ranking…" : "Rank CVs"}
            </button>
          </div>
          {rankResult && (
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <p className="border-b border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                Top {rankResult.results.length} of {rankResult.total_count} matches
              </p>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50/80">
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Rank
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Filename
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Similarity
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankResult.results.map((r) => (
                      <tr
                        key={r.resume_id}
                        className="border-b border-slate-100 transition hover:bg-slate-50/50"
                      >
                        <td className="px-4 py-3 font-medium text-slate-900">{r.rank_position}</td>
                        <td className="px-4 py-3 text-slate-700">{r.filename}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-sm font-medium ${
                              r.similarity_score >= 0.7
                                ? "bg-emerald-100 text-emerald-800"
                                : r.similarity_score >= 0.5
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {(r.similarity_score * 100).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

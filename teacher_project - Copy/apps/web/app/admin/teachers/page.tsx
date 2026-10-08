"use client";
import { useMemo, useState } from "react";
import { DnaLayerModal } from "@/components/dashboard/DnaLayerModal";
import { TeacherCard } from "@/components/dashboard/TeacherCard";
import {
  AdminCard,
  ErrorNote,
  Skeleton,
} from "@/components/dashboard/primitives";
import {
  createTeacher,
  getTeachers,
  regenerate,
  usePolling,
  type AdminTeacher,
} from "@/lib/adminApi";

export default function TeachersPage() {
  const { data: teachers, error, loading, refresh } = usePolling<AdminTeacher[]>(
    getTeachers,
    10_000
  );
  const [query, setQuery] = useState("");
  const [viewing, setViewing] = useState<AdminTeacher | null>(null);
  const [reextractId, setReextractId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const filtered = useMemo(() => {
    const list = teachers ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.subject || "").toLowerCase().includes(q)
    );
  }, [teachers, query]);

  async function handleReextract(t: AdminTeacher) {
    setNotice(null);
    setReextractId(t.id);
    try {
      const res = await regenerate(t.id, t.dna?.model_used || undefined);
      setNotice(`Re-extraction started for “${t.name}” (job ${res.job_id}).`);
      refresh();
    } catch (e: any) {
      setNotice(`⚠️ ${e?.message || "Could not start re-extraction."}`);
    } finally {
      setReextractId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-admin-txt">👨‍🏫 Teachers</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="rounded-lg bg-admin-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-admin-primary/90"
        >
          + Add Teacher
        </button>
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="🔍 Filter by name or subject…"
        className="w-full max-w-sm rounded-lg border border-admin-border bg-admin-surface px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
      />

      {notice && (
        <div className="rounded-lg border border-admin-border bg-admin-surface px-4 py-2.5 text-sm text-admin-txt/90">
          {notice}
        </div>
      )}

      {error && !teachers ? (
        <ErrorNote message={error} onRetry={refresh} />
      ) : loading && !teachers ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <AdminCard key={i}>
              <Skeleton className="h-5 w-32" />
              <Skeleton className="mt-3 h-24 w-full" />
            </AdminCard>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <AdminCard>
          <div className="py-10 text-center text-sm text-admin-sub">
            {teachers && teachers.length === 0
              ? "No teachers yet. Click “+ Add Teacher” to create one."
              : "No teachers match your search."}
          </div>
        </AdminCard>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((t) => (
            <TeacherCard
              key={t.id}
              teacher={t}
              onViewDna={setViewing}
              onReextract={handleReextract}
              reextracting={reextractId === t.id}
            />
          ))}
        </div>
      )}

      {viewing && (
        <DnaLayerModal
          teacherId={viewing.id}
          teacherName={viewing.name}
          onClose={() => setViewing(null)}
        />
      )}

      {showAdd && (
        <AddTeacherModal
          onClose={() => setShowAdd(false)}
          onCreated={() => {
            setShowAdd(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function AddTeacherModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    if (!name.trim()) return setError("Name is required.");
    setSaving(true);
    setError(null);
    try {
      await createTeacher({
        name: name.trim(),
        subject: subject.trim() || undefined,
        description: description.trim() || undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e?.message || "Failed to create teacher.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-admin-border bg-admin-surface p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-admin-txt">Add Teacher</h2>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg border border-admin-border text-admin-sub hover:text-admin-txt"
          >
            ✕
          </button>
        </div>
        <div className="space-y-3">
          <Field label="Name *">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Physics Sir"
              className="w-full rounded-lg border border-admin-border bg-admin-bg px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
            />
          </Field>
          <Field label="Subject">
            <input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Physics"
              className="w-full rounded-lg border border-admin-border bg-admin-bg px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
            />
          </Field>
          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full resize-y rounded-lg border border-admin-border bg-admin-bg px-3 py-2 text-sm text-admin-txt outline-none focus:border-admin-primary"
            />
          </Field>
          {error && <ErrorNote message={error} />}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-admin-border px-4 py-2 text-sm text-admin-sub hover:text-admin-txt"
          >
            Cancel
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-admin-primary px-4 py-2 text-sm font-semibold text-white hover:bg-admin-primary/90 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-admin-sub">{label}</label>
      {children}
    </div>
  );
}

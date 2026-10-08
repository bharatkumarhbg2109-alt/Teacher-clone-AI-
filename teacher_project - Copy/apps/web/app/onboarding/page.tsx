"use client";
import { clsx } from "clsx";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Input, Label, Textarea, TopNav } from "@/components/ui";
import { LEARNING_STYLES, LEVELS, STREAMS, loadStudentProfile, saveStudentProfile } from "@/lib/constants";

export default function Onboarding() {
  const router = useRouter();
  const existing = loadStudentProfile();
  const [level, setLevel] = useState(existing?.level ?? "class_11_12");
  const [stream, setStream] = useState(existing?.stream ?? "");
  const [subject, setSubject] = useState(existing?.subject ?? "");
  const [style, setStyle] = useState(existing?.learning_style ?? "examples");
  const [goal, setGoal] = useState(existing?.goal ?? "");
  const [prior, setPrior] = useState(existing?.prior_knowledge ?? "");
  const [learnAhead, setLearnAhead] = useState(existing?.learn_ahead ?? false);

  const needsStream = level === "class_11_12" || level === "undergrad";

  function save() {
    saveStudentProfile({
      level,
      stream: needsStream ? stream || "other" : undefined,
      subject: subject || "General",
      learning_style: style,
      goal,
      prior_knowledge: prior,
      learn_ahead: learnAhead,
    });
    router.push("/dashboard");
  }

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-2xl px-6 py-10">
        <h1 className="mb-1 text-2xl font-bold">Tell us about you</h1>
        <p className="mb-6 text-sm text-muted">
          The teacher uses this to feed you the right depth — not too much, not too little.
        </p>

        <Card className="space-y-6">
          <div>
            <Label>Your class / level</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {LEVELS.map((l) => (
                <button
                  key={l.value}
                  onClick={() => setLevel(l.value)}
                  className={clsx(
                    "flex flex-col items-center gap-1 rounded-xl border p-3 text-center transition",
                    level === l.value
                      ? "border-indigo bg-indigo/10 text-indigo-light"
                      : "border-borderc hover:border-indigo-light"
                  )}
                >
                  <span className="text-xl">{l.icon}</span>
                  <span className="text-sm font-medium">{l.label}</span>
                  <span className="text-[11px] text-muted">{l.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {needsStream && (
            <div>
              <Label>Stream</Label>
              <div className="flex flex-wrap gap-2">
                {STREAMS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setStream(s)}
                    className={clsx(
                      "rounded-full border px-3 py-1 text-xs capitalize",
                      stream === s ? "border-indigo bg-indigo/10 text-indigo-light" : "border-borderc"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label>Subject (anything)</Label>
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Physics, History, Economics, Data Structures…"
              maxLength={100}
            />
          </div>

          <div>
            <Label>How do you like to learn?</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {LEARNING_STYLES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStyle(s.value)}
                  className={clsx(
                    "flex flex-col items-center gap-1 rounded-xl border p-3 text-center",
                    style === s.value ? "border-indigo bg-indigo/10 text-indigo-light" : "border-borderc"
                  )}
                >
                  <span className="text-lg">{s.icon}</span>
                  <span className="text-xs font-medium">{s.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label>What do you want to learn? (optional)</Label>
            <Textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} maxLength={500} placeholder="e.g. Understand Newton's laws for my exam" />
          </div>

          <div>
            <Label>Prior knowledge (optional)</Label>
            <Input value={prior} onChange={(e) => setPrior(e.target.value)} placeholder="e.g. I know basic algebra" maxLength={1000} />
          </div>

          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-borderc bg-surface p-3">
            <input type="checkbox" checked={learnAhead} onChange={(e) => setLearnAhead(e.target.checked)} className="h-4 w-4 accent-indigo" />
            <div>
              <div className="text-sm font-medium">Learn ahead of my class 🚀</div>
              <div className="text-xs text-muted">Teach me beyond my current syllabus.</div>
            </div>
          </label>

          <Button onClick={save} className="w-full">Save & continue</Button>
        </Card>
      </main>
    </>
  );
}

"use client";
import { ArrowDown, ArrowUp, CheckCircle2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { Quiz } from "@/lib/types";

const ADAPT_LABEL: Record<string, { icon: any; text: string; color: string }> = {
  deeper: { icon: ArrowUp, text: "Great! Going deeper.", color: "text-emerald" },
  reteach: { icon: RefreshCw, text: "Let's revisit this a simpler way.", color: "text-amber" },
  simpler: { icon: ArrowDown, text: "Easing off a little.", color: "text-amber" },
  hold: { icon: CheckCircle2, text: "Good — carrying on.", color: "text-indigo-light" },
};

export function CheckpointCard({
  quiz,
  onResolved,
}: {
  quiz: Quiz;
  onResolved: (r: any) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [result, setResult] = useState<any>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      const r = await api(`/checkpoints/${quiz.id}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setResult(r);
      onResolved(r);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="my-3 rounded-xl border border-amber/30 bg-amber/5 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber">
        ✅ Quick checkpoint
      </div>
      <div className="space-y-4">
        {quiz.questions.map((q, i) => (
          <div key={q.id}>
            <p className="mb-2 text-sm font-medium">
              {i + 1}. {q.question}
            </p>
            {q.type === "mcq" && q.options && (
              <div className="space-y-1.5">
                {Object.entries(q.options).map(([k, v]) => (
                  <label
                    key={k}
                    className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${
                      answers[q.id] === k ? "border-indigo bg-indigo/10" : "border-borderc"
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      checked={answers[q.id] === k}
                      onChange={() => setAnswers({ ...answers, [q.id]: k })}
                      disabled={!!result}
                      className="accent-indigo"
                    />
                    <b className="text-xs">{k}.</b> {v}
                  </label>
                ))}
              </div>
            )}
            {q.type === "true_false" && (
              <div className="flex gap-2">
                {["true", "false"].map((v) => (
                  <button
                    key={v}
                    disabled={!!result}
                    onClick={() => setAnswers({ ...answers, [q.id]: v })}
                    className={`flex-1 rounded-lg border px-3 py-1.5 text-sm capitalize ${
                      answers[q.id] === v ? "border-indigo bg-indigo/10" : "border-borderc"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            )}
            {q.type === "short_answer" && (
              <textarea
                disabled={!!result}
                value={answers[q.id] || ""}
                onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                rows={2}
                className="w-full rounded-lg border border-borderc bg-surface px-3 py-2 text-sm"
                placeholder="Your answer…"
              />
            )}
          </div>
        ))}
      </div>

      {result ? (
        <div className="mt-4 border-t border-borderc pt-3 text-sm">
          <div className="mb-1 font-medium">Score: {Math.round(result.score * 100)}%</div>
          {(() => {
            const a = ADAPT_LABEL[result.adapt] || ADAPT_LABEL.hold;
            const Icon = a.icon;
            return (
              <div className={`flex items-center gap-2 ${a.color}`}>
                <Icon className="h-4 w-4" /> {a.text}
              </div>
            );
          })()}
        </div>
      ) : (
        <Button
          className="mt-4"
          loading={submitting}
          onClick={submit}
          disabled={Object.keys(answers).length < quiz.questions.length}
        >
          Submit checkpoint
        </Button>
      )}
    </div>
  );
}

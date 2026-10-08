import Link from "next/link";
import { Button } from "@/components/ui";

const FEATURES = [
  ["🎥", "Any input, any size", "YouTube links, video, audio, PDFs, slides, docs, images — processed into a teachable knowledge base."],
  ["🎚️", "Your exact level", "Class 6-12, graduation, post-grad or professional — for any subject. Or learn ahead of your class."],
  ["🔊", "Text or audio", "Read the answer or listen to it, in the teacher's own voice."],
  ["✅", "Adaptive checkpoints", "Quick quizzes between the lecture make the teacher go simpler, deeper, or re-teach."],
  ["🌟", "Popular teachers", "No material of your own? Learn from the most-used teachers."],
  ["🔗", "Shareable teachers", "Share your customized teacher with friends via a link — it keeps its memory."],
];

export default function Landing() {
  return (
    <main>
      <section className="mx-auto max-w-4xl px-6 pt-24 pb-16 text-center">
        <div className="mx-auto mb-6 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-indigo to-cyan text-2xl">
          🧠
        </div>
        <h1 className="bg-gradient-to-r from-indigo-light to-cyan bg-clip-text text-4xl font-bold text-transparent sm:text-5xl">
          An AI teacher that adapts to you
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-muted">
          Upload any video, PDF, or link. It clones the teacher's style and teaches you
          any subject — at exactly your class level — in text or audio.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link href="/onboarding">
            <Button className="px-6 py-3 text-base">Start learning free</Button>
          </Link>
          <Link href="/discover">
            <Button variant="outline" className="px-6 py-3 text-base">
              Browse popular teachers
            </Button>
          </Link>
        </div>
      </section>

      <section className="mx-auto grid max-w-5xl gap-4 px-6 pb-24 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(([icon, title, desc]) => (
          <div key={title} className="rounded-xl border border-borderc bg-card p-5">
            <div className="mb-2 text-2xl">{icon}</div>
            <h3 className="mb-1 font-semibold">{title}</h3>
            <p className="text-sm text-muted">{desc}</p>
          </div>
        ))}
      </section>
    </main>
  );
}

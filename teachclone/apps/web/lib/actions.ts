import { api } from "./api";
import { loadStudentProfile } from "./constants";

/** Create a learning session for a teacher and return its id.
 * Falls back to onboarding if the student hasn't set a profile. */
export async function startSession(teacherId: string): Promise<string | null> {
  const profile = loadStudentProfile();
  if (!profile) {
    if (typeof window !== "undefined") {
      localStorage.setItem("tc_pending_teacher", teacherId);
      window.location.href = "/onboarding";
    }
    return null;
  }
  const session = await api<{ id: string }>("/sessions", {
    method: "POST",
    body: JSON.stringify({
      teacher_profile_id: teacherId,
      student_profile: {
        level: profile.level,
        stream: profile.stream,
        subject: profile.subject || "General",
        goal: profile.goal || "",
        learning_style: profile.learning_style || "examples",
        prior_knowledge: profile.prior_knowledge || "",
        learn_ahead: !!profile.learn_ahead,
        target_level: profile.target_level,
      },
    }),
  });
  return session.id;
}

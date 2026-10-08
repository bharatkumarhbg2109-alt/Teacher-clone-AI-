import type { StudentLevel } from "./types";

export const LEVELS: {
  value: StudentLevel;
  label: string;
  desc: string;
  icon: string;
}[] = [
  { value: "class_6_8", label: "Class 6-8", desc: "Middle school", icon: "🎒" },
  { value: "class_9_10", label: "Class 9-10", desc: "Secondary", icon: "📐" },
  { value: "class_11_12", label: "Class 11-12", desc: "Senior secondary", icon: "🎓" },
  { value: "undergrad", label: "Graduation", desc: "Any stream", icon: "📚" },
  { value: "postgrad", label: "Post-graduate", desc: "Masters / PhD", icon: "🔬" },
  { value: "professional", label: "Professional", desc: "Working / applied", icon: "💼" },
];

export const STREAMS = [
  "science",
  "commerce",
  "arts",
  "engineering",
  "medical",
  "law",
  "business",
  "other",
];

export const LEARNING_STYLES: { value: string; label: string; icon: string }[] = [
  { value: "examples", label: "Examples first", icon: "🧩" },
  { value: "theory", label: "Theory first", icon: "📖" },
  { value: "qa", label: "Q&A / Socratic", icon: "💬" },
  { value: "storytelling", label: "Storytelling", icon: "📕" },
];

export function levelLabel(v?: string): string {
  return LEVELS.find((l) => l.value === v)?.label ?? v ?? "";
}

const STUDENT_KEY = "tc_student_profile";

export function loadStudentProfile(): any | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(STUDENT_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveStudentProfile(p: any) {
  if (typeof window !== "undefined") localStorage.setItem(STUDENT_KEY, JSON.stringify(p));
}

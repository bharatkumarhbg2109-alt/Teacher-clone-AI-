export type StudentLevel =
  | "class_6_8"
  | "class_9_10"
  | "class_11_12"
  | "undergrad"
  | "postgrad"
  | "professional";

export interface StudentProfile {
  level: StudentLevel;
  stream?: string;
  subject: string;
  goal: string;
  learning_style: string;
  prior_knowledge: string;
  learn_ahead: boolean;
  target_level?: string;
}

export interface TeacherProfile {
  id: string;
  name: string;
  description?: string;
  subject?: string;
  tts_voice: string;
  style_profile?: any;
  total_sources: number;
  visibility: string;
  share_token?: string;
  share_enabled: boolean;
  share_mode: string;
  session_count: number;
  unique_learners: number;
  created_at: string;
}

export interface MediaSource {
  id: string;
  teacher_profile_id: string;
  source_type: string;
  file_name?: string;
  original_url?: string | null;
  status: string;
  transcript_chunks?: number;
  created_at: string;
}

export interface Citation {
  media_source_id: string;
  start_time?: number | null;
  end_time?: number | null;
  page?: number | null;
  chunk_text: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  audio_url?: string | null;
  created_at?: string;
}

export interface Session {
  id: string;
  teacher_profile_id: string;
  student_profile: StudentProfile;
  current_effective_level?: string;
  concept_mastery: any[];
  message_count: number;
  teacher_profile?: TeacherProfile;
  messages?: ChatMessage[];
}

export interface QuizQuestion {
  id: string;
  type: "mcq" | "true_false" | "short_answer";
  concept?: string;
  question: string;
  options?: Record<string, string>;
  key_concepts?: string[];
  source_page?: number;
}

export interface Quiz {
  id: string;
  session_id: string;
  kind: string;
  questions: QuizQuestion[];
  score?: number | null;
}

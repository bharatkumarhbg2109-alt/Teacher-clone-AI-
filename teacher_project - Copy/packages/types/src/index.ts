/**
 * @teachclone/types — shared type definitions used by the web app and any
 * TypeScript consumer (e.g. the embeddable widget / public SDK).
 *
 * These mirror the FastAPI Pydantic schemas. Keep them in sync.
 */

// ============================================================================
//  Enums (string-literal unions)
// ============================================================================

export type Plan = 'free' | 'pro' | 'creator' | 'institution';

/**
 * Grade ladder. Ascending difficulty. Calibrates vocabulary + depth so the
 * teacher feeds "not too much, not too little".
 */
export type StudentLevel =
  | 'class_6_8' // Middle school (grades 6-8)
  | 'class_9_10' // Secondary (grades 9-10)
  | 'class_11_12' // Senior secondary (grades 11-12)
  | 'undergrad' // Graduation, any stream
  | 'postgrad' // Post-graduate / Masters / PhD
  | 'professional'; // Working professional

/** Optional academic stream, relevant for class_11_12 and undergrad. */
export type Stream =
  | 'science'
  | 'commerce'
  | 'arts'
  | 'engineering'
  | 'medical'
  | 'law'
  | 'business'
  | 'other';

export type LearningStyle = 'examples' | 'theory' | 'qa' | 'storytelling';

export type MediaStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type MessageRole = 'user' | 'assistant';
export type OrgRole = 'admin' | 'teacher' | 'student';

export type SourceType =
  | 'youtube_url'
  | 'video_upload'
  | 'audio_upload'
  | 'pdf_upload'
  | 'doc_upload' // docx / pptx / txt / markdown
  | 'image_upload';

export type ToneType =
  | 'strict'
  | 'friendly'
  | 'socratic'
  | 'storytelling'
  | 'energetic'
  | 'calm';

export type ExplanationPattern =
  | 'analogy_first'
  | 'example_first'
  | 'theory_first'
  | 'problem_first'
  | 'narrative';

export type VocabLevel = 'elementary' | 'intermediate' | 'advanced' | 'technical';

/** Visibility of a teacher profile. */
export type Visibility = 'private' | 'unlisted' | 'public';

/** What opening a share link does. */
export type ShareMode = 'clone' | 'view';

/** Mastery state per concept, driven by inline checkpoints. */
export type MasteryState = 'mastered' | 'shaky' | 'review' | 'unseen';

export type QuizKind = 'full' | 'checkpoint';

// ============================================================================
//  Style profile (teacher-style analysis result)
// ============================================================================

export interface StyleProfile {
  vocabularyLevel: VocabLevel;
  vocabularyScore: number;
  toneType: ToneType;
  toneConfidence: number;
  explanationPattern: ExplanationPattern;
  analogyDensity: number;
  avgSentenceLength: number;
  useOfHumor: number;
  useOfQuestions: number;
  signaturePhrases: string[];
  vocabularySamples: string[];
  pacing: 'slow' | 'moderate' | 'fast';
  explanationDepth: 'surface' | 'moderate' | 'deep';
  subjects?: string[];
  rawAnalysis: string;
}

// ============================================================================
//  Student profile (per session)
// ============================================================================

export interface StudentProfile {
  level: StudentLevel;
  stream?: Stream;
  subject: string; // any subject, free-form or picked
  goal: string;
  learningStyle: LearningStyle;
  priorKnowledge: string;
  /** If true, teach above the stated level. */
  learnAhead: boolean;
  /** Target level when learnAhead is on (defaults to one step above level). */
  targetLevel?: StudentLevel;
}

// ============================================================================
//  Core entities
// ============================================================================

export interface User {
  id: string;
  clerkId: string;
  email: string;
  fullName: string;
  avatarUrl?: string;
  plan: Plan;
  stripeCustomerId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  ownerId: string;
  plan: Plan;
  seatLimit: number;
  logoUrl?: string;
  ssoEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface OrgMember {
  id: string;
  orgId: string;
  userId: string;
  role: OrgRole;
  user?: User;
  createdAt: string;
}

export interface TeacherProfile {
  id: string;
  userId?: string;
  orgId?: string;
  name: string;
  description?: string;
  subject?: string;
  ttsVoice: string;
  styleProfile?: StyleProfile;
  totalSources: number;

  // Discovery + sharing
  visibility: Visibility;
  shareToken?: string;
  shareEnabled: boolean;
  shareMode: ShareMode;
  forkedFromId?: string;
  sessionCount: number;
  uniqueLearners: number;

  createdAt: string;
  updatedAt: string;
}

export interface MediaSource {
  id: string;
  teacherProfileId: string;
  uploadedBy: string;
  sourceType: SourceType;
  originalUrl?: string;
  storageKey?: string;
  fileName?: string;
  fileSizeBytes?: number;
  durationSeconds?: number;
  pageCount?: number;
  status: MediaStatus;
  errorMessage?: string;
  transcriptChunks?: number;
  createdAt: string;
}

export interface Citation {
  mediaSourceId: string;
  startTime?: number; // seconds (audio/video)
  endTime?: number;
  page?: number; // documents
  chunkText: string;
}

export interface Message {
  id: string;
  sessionId: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  audioUrl?: string;
  tokensUsed?: number;
  modelUsed?: string;
  createdAt: string;
}

/** Per-concept mastery tracking, updated by checkpoints. */
export interface ConceptMastery {
  concept: string;
  state: MasteryState;
  attempts: number;
  correct: number;
  lastSeenAt?: string;
  nextReviewAt?: string; // spaced repetition
}

export interface StudentSession {
  id: string;
  studentId: string;
  teacherProfileId: string;
  studentProfile: StudentProfile;
  currentEffectiveLevel?: StudentLevel;
  messageCount: number;
  conceptMastery: ConceptMastery[];
  lastActivityAt: string;
  sessionNotes?: SessionSummary;
  createdAt: string;
  updatedAt: string;
  teacherProfile?: TeacherProfile;
  messages?: Message[];
}

// ============================================================================
//  Quizzes & checkpoints
// ============================================================================

export interface MCQQuestion {
  id: string;
  type: 'mcq';
  concept?: string;
  question: string;
  options: Record<'A' | 'B' | 'C' | 'D', string>;
  correctAnswer: 'A' | 'B' | 'C' | 'D';
  explanation: string;
  sourceTimestamp?: number;
  sourcePage?: number;
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface TrueFalseQuestion {
  id: string;
  type: 'true_false';
  concept?: string;
  question: string;
  correctAnswer: boolean;
  explanation: string;
  sourceTimestamp?: number;
  sourcePage?: number;
}

export interface ShortAnswerQuestion {
  id: string;
  type: 'short_answer';
  concept?: string;
  question: string;
  sampleAnswer: string;
  keyConcepts: string[];
  sourceTimestamp?: number;
  sourcePage?: number;
}

export type Question = MCQQuestion | TrueFalseQuestion | ShortAnswerQuestion;

export interface QuizData {
  title: string;
  questions: Question[];
}

export interface GradingResult {
  isCorrect: boolean;
  score: number;
  feedback: string;
  correctAnswer?: string | boolean;
}

export interface Quiz {
  id: string;
  sessionId: string;
  teacherProfileId: string;
  kind: QuizKind;
  questions: Question[];
  studentAnswers?: Record<string, string | boolean>;
  gradingResults?: Record<string, GradingResult>;
  score?: number;
  completedAt?: string;
  createdAt: string;
}

/** Result of submitting a checkpoint — drives adaptation. */
export interface CheckpointResult {
  quizId: string;
  score: number;
  results: Record<string, GradingResult>;
  /** Direction the teacher should adapt next. */
  adapt: 'simpler' | 'deeper' | 'reteach' | 'hold';
  updatedLevel: StudentLevel;
  masteredConcepts: string[];
  reviewConcepts: string[];
}

// ============================================================================
//  Session export
// ============================================================================

export interface SessionSummary {
  overview: string;
  keyConcepts: string[];
  definitions: Array<{ term: string; definition: string }>;
  takeaways: string[];
  questionsToExplore: string[];
  quizScore?: number;
  topicsToReview: string[];
}

// ============================================================================
//  Gamification
// ============================================================================

export interface UserStats {
  userId: string;
  xpTotal: number;
  level: number;
  streakDays: number;
  longestStreak: number;
  lastSessionDate?: string;
  sessionsCompleted: number;
  quizzesCompleted: number;
  perfectQuizzes: number;
  sourcesProcessed: number;
}

export interface BadgeDef {
  id: string;
  name: string;
  icon: string;
  xp: number;
  description: string;
}

export interface UserBadge {
  userId: string;
  badgeId: string;
  earnedAt: string;
}

export interface GamificationResult {
  xpEarned: number;
  newTotal: number;
  oldLevel: number;
  newLevel: number;
  levelUp: boolean;
  newBadges: BadgeDef[];
  streak: number;
}

// ============================================================================
//  Billing
// ============================================================================

export interface PlanLimits {
  sourcesPerMonth: number;
  messagesPerDay: number;
  sessions: number;
  exportsPerMonth: number;
  quizzesPerMonth: number;
}

export interface MonthlyUsage {
  sources: number;
  messages: number;
  exports: number;
  quizzes: number;
}

export interface BillingStatus {
  plan: Plan;
  limits: PlanLimits;
  usage: MonthlyUsage;
}

// ============================================================================
//  API helpers
// ============================================================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  perPage: number;
  hasMore: boolean;
}

export interface ApiError {
  message: string;
  code: string;
  status: number;
}

// ---- Upload flow (multipart / resumable, "any size") -----------------------

export interface UploadInitiateResponse {
  mediaSourceId: string;
  /** Single-shot presigned PUT (small files). */
  uploadUrl?: string;
  uploadKey: string;
  /** Multipart upload id (large files). */
  multipartUploadId?: string;
  /** Recommended part size in bytes. */
  partSize?: number;
  expiresAt: string;
}

export interface MultipartPartUrl {
  partNumber: number;
  url: string;
}

export interface ProcessingProgress {
  status: MediaStatus;
  transcriptChunks?: number;
  stage?: string;
  progress?: number;
}

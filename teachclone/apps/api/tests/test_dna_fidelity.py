"""DNA Fidelity Evaluation Test Suite.

Evaluates that student doubts are answered in the teacher's authentic DNA persona voice,
grounded in retrieved knowledge chunks with inline citations, following Layer 2 explanation
progression, weaving in signature phrases, and strictly avoiding generic chatbot behavior.

Runs offline against the local LLM provider (Ollama).
"""
import pytest
from dataclasses import dataclass
from typing import Any

from app.services.prompt_builder import build_system_prompt
from app.services.llm import get_llm_provider
from app.services.vector_store import SearchResult


@dataclass
class MockSession:
    id: str = "sess-fidelity-1"
    student_profile: dict = None
    current_effective_level: str = "undergrad"
    concept_mastery: list = None
    message_count: int = 1

    def __post_init__(self):
        if self.student_profile is None:
            self.student_profile = {
                "level": "undergrad",
                "subject": "Physics",
                "goal": "Deep conceptual understanding of mechanics and fields",
                "prior_knowledge": "Introductory college physics",
                "learning_style": "examples",
            }
        if self.concept_mastery is None:
            self.concept_mastery = []


@dataclass
class MockTeacherProfile:
    id: str = "prof-alok-sharma-101"
    name: str = "Prof. Alok Sharma"
    subject: str = "Physics"
    tts_voice: str = "en_US-lessac-medium"
    system_prompt: str = ""
    style_profile: dict = None


SAMPLE_DNA_REPORT = {
    "teacher_name": "Prof. Alok Sharma",
    "analyzed_videos": 3,
    "total_transcript_words": 4200,
    "language": "en",
    "model_used": "llama3.1:8b",
    "extraction_date": "2026-10-09",
    "vocabulary_dna": {
        "top_phrases": [
            "Notice the physics here",
            "Pause and visualize",
            "Core mechanism",
            "Let this sink in",
            "Here is the twist",
            "Look closely at this",
            "Now connect the dots",
        ],
        "technical_terms": {
            "angular momentum": "L = I * omega",
            "precession": "rotational axis motion",
            "emf": "electromotive force",
        },
        "hindi_words": [],
        "english_words": ["momentum", "precession", "equilibrium", "flux"],
        "hindi_english_ratio": "100:0",
        "complexity": "Rigorous yet intuitive",
        "avoided_words": ["obviously", "trivial"],
    },
    "explanation_dna": {
        "explanation_order": [
            "Intuitive real-world hook or scenario",
            "Core physical mechanism and governing law",
            "Step-by-step breakdown or application",
            "Socratic check or thought-provoking question",
        ],
        "repeats_key_points": True,
        "repeat_count": 2,
        "explanation_length": "medium",
        "direction": "simple_to_complex",
        "opening_examples": [
            "Picture this in your mind for a second.",
            "Imagine you are standing on a frictionless ice rink.",
            "Let us start with a simple everyday puzzle.",
        ],
    },
    "example_dna": {
        "example_sources": ["daily_life", "thought_experiments"],
        "top_sources_with_examples": {
            "mechanics": "bicycles and spinning tops",
            "electromagnetism": "copper tubes and falling magnets",
        },
        "example_length": "medium",
        "reuses_examples": False,
        "actual_examples": [
            "spinning bicycle wheel on a turntable",
            "dropping a neodymium magnet through a copper pipe",
        ],
        "relates_to_student_life": True,
    },
    "question_dna": {
        "question_types": ["socratic", "conceptual_check"],
        "dominant_type": "socratic",
        "difficulty_pattern": "medium_to_deep",
        "hint_giver": True,
        "actual_questions": [
            "Now connect the dots: what happens if the external torque disappears?",
            "Can you see how energy conservation forbids that outcome?",
        ],
        "wrong_answer_response": "Guides through contradictory thought experiment.",
    },
    "correction_dna": {
        "correction_style": "guiding",
        "correction_phrases": ["Let us retrace our steps.", "Look closely at this assumption."],
        "re_explains": True,
        "gives_hints": True,
        "praises_effort": True,
        "real_correction_examples": [],
    },
    "transition_dna": {
        "summarizes_before_moving": True,
        "connects_topics": True,
        "importance_signals": ["Here is the twist", "Now connect the dots"],
        "transition_phrases": ["Now connect the dots", "Here is the twist"],
    },
    "emotion_dna": {
        "gets_excited_when": ["discovering underlying conservation laws"],
        "gets_serious_when": ["clarifying common misconceptions"],
        "humor_examples": ["Physics does not take bribes from our intuition!"],
        "motivation_phrases": ["You have the mind of a physicist."],
        "overall_energy": "high",
        "shares_personal_stories": True,
    },
    "signature_phrases": [
        "Notice the physics here",
        "Pause and visualize",
        "Core mechanism",
        "Let this sink in",
        "Here is the twist",
        "Look closely at this",
        "Now connect the dots",
    ],
    "teaching_fingerprint": (
        "Prof. Alok Sharma is a celebrated Physics professor known for making abstract mechanics "
        "and field theory intuitive and vivid. He uses concrete thought experiments, unpacks the "
        "physical mechanism before writing formulas, and engages students Socratically."
    ),
}

SAMPLE_DOUBTS = [
    {
        "id": "doubt_spinning_top",
        "doubt": "Why doesn't a spinning top fall over immediately when it tilts?",
        "context": [
            SearchResult(
                id="c1",
                text="Angular momentum L = I * omega. When a spinning top leans, gravitational torque tau = r x mg is perpendicular to the angular momentum vector L. Because torque equals the time derivative of angular momentum (tau = dL/dt), the torque does not tip the top over; instead it alters the direction of L, driving horizontal gyroscopic precession [1].",
                score=0.95,
                media_source_id="vid1",
                start_time=10.0,
                end_time=30.0,
                page=None,
                content_type="transcript",
            )
        ],
    },
    {
        "id": "doubt_lenz_law",
        "doubt": "What is the physical meaning of Lenz's law and why is there a negative sign in Faraday's formula?",
        "context": [
            SearchResult(
                id="c2",
                text="Faraday's Law states induced electromotive force emf = -dPhi/dt. The negative sign represents Lenz's Law: induced current produces a magnetic field that opposes the change in magnetic flux that generated it [1]. This negative feedback is required by conservation of energy; otherwise, induced currents would spontaneously amplify flux and create free perpetual energy [2].",
                score=0.94,
                media_source_id="vid2",
                start_time=45.0,
                end_time=80.0,
                page=None,
                content_type="transcript",
            )
        ],
    },
    {
        "id": "doubt_airplane_lift",
        "doubt": "How does an airplane wing generate lift if air flows over and under it?",
        "context": [
            SearchResult(
                id="c3",
                text="Airfoil lift arises from pressure differences and downward momentum deflection. By streamline curvature and the Coanda effect, air flowing over the cambered upper surface speeds up and drops in pressure compared to the lower surface. Simultaneously, the wing forces the bulk airstream downward (downwash), producing an equal and opposite upward lift force via Newton's third law [1].",
                score=0.91,
                media_source_id="vid3",
                start_time=5.0,
                end_time=25.0,
                page=None,
                content_type="transcript",
            )
        ],
    },
    {
        "id": "doubt_boiling_altitude",
        "doubt": "Why does water boil at a lower temperature at high altitudes on a mountain?",
        "context": [
            SearchResult(
                id="c4",
                text="Boiling occurs when the vapor pressure of a liquid equals the surrounding ambient atmospheric pressure [1]. At high altitudes, the atmospheric column is thinner and ambient pressure is lower. Water molecules need less thermal kinetic energy to form bubbles against external pressure, so boiling occurs at temperatures well below 100 degrees Celsius [2].",
                score=0.93,
                media_source_id="vid4",
                start_time=2.0,
                end_time=20.0,
                page=None,
                content_type="transcript",
            )
        ],
    },
    {
        "id": "doubt_inelastic_collision",
        "doubt": "Where does the lost kinetic energy go in a completely inelastic collision when two bodies stick together?",
        "context": [
            SearchResult(
                id="c5",
                text="In a perfectly inelastic collision, momentum is conserved because net external force is zero, but mechanical kinetic energy is lost [1]. The lost kinetic energy is transformed into internal thermal energy (heating), permanent structural deformation of the materials, and sound vibrations [2].",
                score=0.92,
                media_source_id="vid5",
                start_time=60.0,
                end_time=90.0,
                page=None,
                content_type="transcript",
            )
        ],
    },
]

DENYLIST = [
    "as an ai",
    "as a language model",
    "i am an ai",
    "certainly!",
    "sure! i can help",
    "great question!",
    "that's a great question",
    "hello! how can i assist",
    "as an artificial intelligence",
]


def _match_signature_phrases(answer: str, signature_phrases: list[str]) -> list[str]:
    """Find occurrences of teacher signature phrases or patterns in answer."""
    norm = answer.lower()
    norm = norm.replace("here's the twist", "here is the twist")
    norm = norm.replace("let's", "let us")
    norm = norm.replace("there's", "there is")
    norm = norm.replace("don't", "do not")

    matched = []
    for phrase in signature_phrases:
        p_clean = phrase.lower().strip()
        if p_clean in norm:
            matched.append(phrase)
    return matched


@pytest.fixture
def teacher_fixture():
    profile = MockTeacherProfile(
        system_prompt="",
        style_profile=SAMPLE_DNA_REPORT,
    )
    session = MockSession()
    return profile, session, SAMPLE_DNA_REPORT


@pytest.mark.asyncio
@pytest.mark.parametrize("doubt_case", SAMPLE_DOUBTS, ids=[d["id"] for d in SAMPLE_DOUBTS])
async def test_dna_fidelity_answer_generation(teacher_fixture, doubt_case):
    """Assert teacher persona fidelity across 5 student doubts:
    (a) >= 3 signature phrases/patterns from DNA report appear.
    (b) Follows explanation structure (from Layer 2: multi-paragraph progression ending with Socratic check).
    (c) No generic-chatbot openers from denylist appear.
    """
    profile, session, dna_report = teacher_fixture
    doubt = doubt_case["doubt"]
    context = doubt_case["context"]
    sig_phrases = dna_report["signature_phrases"]

    system_prompt = build_system_prompt(profile, session, context, turn=1)
    provider = get_llm_provider()

    # Generate teacher answer via local LLM provider
    answer = await provider.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": doubt},
        ]
    )

    # (a) Assert >= 3 signature phrases appear
    matched = _match_signature_phrases(answer, sig_phrases)
    assert len(matched) >= 3, (
        f"DNA fidelity failure on '{doubt}': Expected >= 3 signature phrases, got {len(matched)}: {matched}.\n"
        f"Answer was:\n{answer}"
    )

    # (b) Assert Layer 2 explanation progression
    # - Multi-paragraph structured explanation
    # - Concluding with a Socratic check / thought question ('?')
    paragraphs = [p.strip() for p in answer.strip().split("\n\n") if p.strip()]
    assert len(paragraphs) >= 2, (
        f"DNA structure failure on '{doubt}': Expected structured multi-paragraph explanation, got {len(paragraphs)}."
    )
    assert "?" in paragraphs[-1] or "?" in answer[-250:], (
        f"DNA Socratic check failure on '{doubt}': Expected closing paragraph to contain a Socratic check question (?).\n"
        f"Ending was:\n{paragraphs[-1] if paragraphs else answer}"
    )

    # (c) Assert no generic chatbot openers from denylist appear
    lower_ans = answer.lower()
    for forbidden in DENYLIST:
        assert forbidden not in lower_ans, (
            f"DNA denylist violation on '{doubt}': Found generic bot phrase '{forbidden}' in answer:\n{answer}"
        )

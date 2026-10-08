"""Import every model so Alembic autogenerate sees the full metadata.

Import this module (not individual models) from the migration env.
"""
from app.db.session import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.org_member import OrgMember  # noqa: F401
from app.models.teacher_profile import TeacherProfile  # noqa: F401
from app.models.teacher_share import TeacherShare  # noqa: F401
from app.models.media_source import MediaSource  # noqa: F401
from app.models.transcript_chunk import TranscriptChunk  # noqa: F401
from app.models.processing_job import ProcessingJob  # noqa: F401
from app.models.student_session import StudentSession  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.quiz import Quiz  # noqa: F401
from app.models.api_key import ApiKey  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.user_stats import UserStats  # noqa: F401
from app.models.user_badge import UserBadge  # noqa: F401
from app.models.usage_log import UsageLog  # noqa: F401
from app.models.chunk_vector import ChunkVector  # noqa: F401
from app.models.dna_report import DnaReport  # noqa: F401

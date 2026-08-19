"""Database runtime and schema for durable fixture identities."""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool


SCHEMA_VERSION = '20260804_01'


def utc_now():
    return datetime.now(timezone.utc)


def normalize_database_url(url):
    value = str(url or '').strip()
    if value.startswith('postgres://'):
        return f'postgresql+psycopg://{value[len("postgres://"):]}'
    if value.startswith('postgresql://'):
        return f'postgresql+psycopg://{value[len("postgresql://"):]}'
    return value


class Base(DeclarativeBase):
    pass


class FixtureIdentity(Base):
    __tablename__ = 'fixture_identities'

    public_id: Mapped[str] = mapped_column(String(27), primary_key=True)
    canonical_competition_id: Mapped[str | None] = mapped_column(String(255))
    canonical_home_team_id: Mapped[str | None] = mapped_column(String(255))
    canonical_away_team_id: Mapped[str | None] = mapped_column(String(255))
    season_key: Mapped[str | None] = mapped_column(String(128))
    stage_key: Mapped[str | None] = mapped_column(String(128))
    kickoff_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class FixtureProviderAlias(Base):
    __tablename__ = 'fixture_provider_aliases'

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(27),
        ForeignKey('fixture_identities.public_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FixturePublicAlias(Base):
    __tablename__ = 'fixture_public_aliases'

    alias_public_id: Mapped[str] = mapped_column(String(27), primary_key=True)
    canonical_public_id: Mapped[str] = mapped_column(
        String(27),
        ForeignKey('fixture_identities.public_id', ondelete='CASCADE'),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IdentityResolutionIssue(Base):
    __tablename__ = 'identity_resolution_issues'
    __table_args__ = (
        UniqueConstraint(
            'kind',
            'provider',
            'provider_id',
            name='uq_identity_resolution_issue',
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SchemaMetadata(Base):
    __tablename__ = 'schema_metadata'

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class DatabaseRuntime:
    def __init__(self, engine):
        self.engine = engine
        self.session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            future=True,
        )

    @classmethod
    def from_config(cls, config):
        database_url = normalize_database_url(config.get('DATABASE_URL'))
        if not database_url:
            raise ValueError('DATABASE_URL is required for durable fixture identities.')
        options = {'pool_pre_ping': True, 'future': True}
        if database_url.startswith('sqlite:'):
            options['connect_args'] = {'check_same_thread': False}
            if database_url in {'sqlite://', 'sqlite:///:memory:'}:
                options['poolclass'] = StaticPool
        else:
            # Soccer Scanner is a low-traffic, single-worker service. Retaining a
            # Postgres QueuePool is unnecessary and can keep Railway Serverless
            # from observing a truly idle process. Request-scoped sessions close
            # their connection when finished instead.
            options['poolclass'] = NullPool
        return cls(create_engine(database_url, **options))

    @contextmanager
    def session_scope(self):
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self):
        self.engine.dispose()

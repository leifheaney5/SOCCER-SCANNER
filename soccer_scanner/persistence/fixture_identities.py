"""Transactional provider aliases and durable public fixture identities."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text, tuple_, update
from sqlalchemy.exc import IntegrityError

from soccer_scanner.domain.identity import (
    FixtureIdentityError,
    provider_fallback_public_id,
)
from .database import (
    SCHEMA_VERSION,
    FixtureIdentity,
    FixtureProviderAlias,
    FixturePublicAlias,
    IdentityResolutionIssue,
    SchemaMetadata,
    utc_now,
)


MATCH_TOLERANCE = timedelta(minutes=10)


def _instant(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _value(container, key):
    return container.get(key) if isinstance(container, dict) else None


def _canonical_evidence(match):
    return {
        'canonical_competition_id': _value(match.get('competition'), 'canonicalId'),
        'canonical_home_team_id': _value(match.get('homeTeam'), 'canonicalId'),
        'canonical_away_team_id': _value(match.get('awayTeam'), 'canonicalId'),
        'season_key': str(_value(match.get('season'), 'year') or '') or None,
        'stage_key': str(match.get('stage') or '') or None,
        'kickoff_utc': _instant(match.get('utcDate')),
    }


def _provider_identities(group):
    identities = set()
    for fixture in group:
        for provider, provider_id in (fixture.get('providerIds') or {}).items():
            provider_name = str(provider or '').strip().casefold()
            event_id = str(provider_id or '').strip()
            if provider_name and event_id:
                identities.add((provider_name, event_id))
    return tuple(sorted(identities))


def _aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class FixtureIdentityRepository:
    def __init__(self, database, *, durable=True):
        self.database = database
        self.durable = bool(durable)

    def resolve(self, group, match_evidence):
        last_error = None
        for _attempt in range(3):
            try:
                return self._resolve_once(group, match_evidence)
            except IntegrityError as error:
                last_error = error
        raise FixtureIdentityError(
            'Concurrent fixture identity resolution did not converge.'
        ) from last_error

    def _resolve_once(self, group, match_evidence):
        provider_identities = _provider_identities(group)
        if not provider_identities:
            raise FixtureIdentityError('Fixture is missing a provider event identity.')
        evidence = _canonical_evidence(match_evidence)
        now = utc_now()

        with self.database.session_scope() as session:
            existing_aliases = session.scalars(
                select(FixtureProviderAlias).where(
                    tuple_(
                        FixtureProviderAlias.provider,
                        FixtureProviderAlias.provider_event_id,
                    ).in_(provider_identities)
                )
            ).all()
            alias_map = {
                (alias.provider, alias.provider_event_id): alias
                for alias in existing_aliases
            }
            existing_public_ids = {
                alias_map[identity].public_id
                for identity in provider_identities
                if identity in alias_map
            }

            if existing_public_ids:
                public_id = self._reconcile(session, existing_public_ids, now)
            else:
                public_id = self._find_canonical_candidate(session, evidence)
                if public_id is None:
                    preferred = min(
                        (
                            fixture
                            for fixture in group
                            if fixture.get('providerIds')
                        ),
                        key=lambda fixture: tuple(sorted(
                            (str(provider), str(provider_id))
                            for provider, provider_id in (
                                fixture.get('providerIds') or {}
                            ).items()
                        )),
                    )
                    public_id = provider_fallback_public_id(preferred)
                    collision = session.get(FixtureIdentity, public_id)
                    if collision is not None:
                        raise FixtureIdentityError(
                            'Provider-qualified public fixture identity collision.'
                        )
                    session.add(FixtureIdentity(public_id=public_id, **evidence))

            identity = session.get(FixtureIdentity, public_id)
            if identity is None:
                raise FixtureIdentityError('Durable fixture identity could not be resolved.')
            for field, value in evidence.items():
                if value is not None:
                    setattr(identity, field, value)
            identity.updated_at = now

            for provider, event_id in provider_identities:
                alias = alias_map.get((provider, event_id))
                if alias is None:
                    session.add(FixtureProviderAlias(
                        provider=provider,
                        provider_event_id=event_id,
                        public_id=public_id,
                    ))
                elif alias.public_id != public_id:
                    alias.public_id = public_id

            self._record_unresolved_entities(session, match_evidence, now)
            return public_id

    def resolve_public_alias(self, public_id):
        with self.database.session_scope() as session:
            if session.get(FixtureIdentity, public_id) is not None:
                return public_id
            alias = session.get(FixturePublicAlias, public_id)
            return alias.canonical_public_id if alias is not None else None

    def get(self, public_id):
        resolved = self.resolve_public_alias(public_id)
        if resolved is None:
            return None
        with self.database.session_scope() as session:
            identity = session.get(FixtureIdentity, resolved)
            if identity is None:
                return None
            kickoff = _aware(identity.kickoff_utc)
            provider_aliases = session.scalars(
                select(FixtureProviderAlias).where(
                    FixtureProviderAlias.public_id == resolved
                )
            ).all()
            return {
                'publicId': resolved,
                'requestedPublicId': public_id,
                'kickoffUtc': kickoff.isoformat() if kickoff else None,
                'providerIds': {
                    alias.provider: alias.provider_event_id
                    for alias in provider_aliases
                },
            }

    def unresolved_report(self, *, limit=100):
        bounded_limit = min(500, max(1, int(limit)))
        with self.database.session_scope() as session:
            total = session.scalar(
                select(func.count()).select_from(IdentityResolutionIssue).where(
                    IdentityResolutionIssue.resolved.is_(False)
                )
            )
            issues = session.scalars(
                select(IdentityResolutionIssue)
                .where(IdentityResolutionIssue.resolved.is_(False))
                .order_by(
                    IdentityResolutionIssue.occurrences.desc(),
                    IdentityResolutionIssue.last_seen_at.desc(),
                    IdentityResolutionIssue.id.asc(),
                )
                .limit(bounded_limit)
            ).all()
            return {
                'total': int(total or 0),
                'items': [
                    {
                        'kind': issue.kind,
                        'provider': issue.provider,
                        'providerId': issue.provider_id,
                        'displayName': issue.display_name,
                        'occurrences': issue.occurrences,
                        'firstSeenAt': _aware(issue.first_seen_at).isoformat(),
                        'lastSeenAt': _aware(issue.last_seen_at).isoformat(),
                    }
                    for issue in issues
                ],
            }

    def health(self):
        try:
            with self.database.session_scope() as session:
                session.execute(text('SELECT 1'))
                schema_version = session.scalar(
                    select(SchemaMetadata.value).where(
                        SchemaMetadata.key == 'schema_version'
                    )
                )
        except Exception:
            return {
                'backend': 'database',
                'reachable': False,
                'schemaVersion': None,
                'status': 'degraded',
            }
        return {
            'backend': 'database',
            'reachable': True,
            'schemaVersion': schema_version,
            'status': 'ready' if schema_version == SCHEMA_VERSION else 'schema_mismatch',
        }

    @staticmethod
    def _find_canonical_candidate(session, evidence):
        required = (
            'canonical_competition_id',
            'canonical_home_team_id',
            'canonical_away_team_id',
            'kickoff_utc',
        )
        if any(evidence[field] is None for field in required):
            return None
        kickoff = evidence['kickoff_utc']
        candidates = session.scalars(
            select(FixtureIdentity).where(
                FixtureIdentity.canonical_competition_id
                == evidence['canonical_competition_id'],
                FixtureIdentity.canonical_home_team_id
                == evidence['canonical_home_team_id'],
                FixtureIdentity.canonical_away_team_id
                == evidence['canonical_away_team_id'],
                FixtureIdentity.season_key == evidence['season_key'],
                FixtureIdentity.stage_key == evidence['stage_key'],
                FixtureIdentity.kickoff_utc >= kickoff - MATCH_TOLERANCE,
                FixtureIdentity.kickoff_utc <= kickoff + MATCH_TOLERANCE,
            )
        ).all()
        return candidates[0].public_id if len(candidates) == 1 else None

    @staticmethod
    def _reconcile(session, public_ids, now):
        identities = session.scalars(
            select(FixtureIdentity)
            .where(FixtureIdentity.public_id.in_(public_ids))
            .order_by(FixtureIdentity.created_at.asc(), FixtureIdentity.public_id.asc())
        ).all()
        if not identities:
            raise FixtureIdentityError('Provider alias points to a missing fixture identity.')
        survivor = identities[0]
        for superseded in identities[1:]:
            session.execute(
                update(FixtureProviderAlias)
                .where(FixtureProviderAlias.public_id == superseded.public_id)
                .values(public_id=survivor.public_id)
            )
            session.execute(
                update(FixturePublicAlias)
                .where(FixturePublicAlias.canonical_public_id == superseded.public_id)
                .values(canonical_public_id=survivor.public_id)
            )
            existing_alias = session.get(FixturePublicAlias, superseded.public_id)
            if existing_alias is None:
                session.add(FixturePublicAlias(
                    alias_public_id=superseded.public_id,
                    canonical_public_id=survivor.public_id,
                    created_at=now,
                ))
            else:
                existing_alias.canonical_public_id = survivor.public_id
            session.delete(superseded)
        return survivor.public_id

    @staticmethod
    def _record_unresolved_entities(session, match, now):
        entities = (
            ('competition', match.get('competition')),
            ('team', match.get('homeTeam')),
            ('team', match.get('awayTeam')),
        )
        for kind, entity in entities:
            if not isinstance(entity, dict) or entity.get('canonicalId'):
                continue
            provider = str(entity.get('provider') or '').strip().casefold()
            provider_id = str(entity.get('providerId') or '').strip()
            if not provider or not provider_id:
                continue
            issue = session.scalar(
                select(IdentityResolutionIssue).where(
                    IdentityResolutionIssue.kind == kind,
                    IdentityResolutionIssue.provider == provider,
                    IdentityResolutionIssue.provider_id == provider_id,
                )
            )
            if issue is None:
                session.add(IdentityResolutionIssue(
                    kind=kind,
                    provider=provider,
                    provider_id=provider_id,
                    display_name=str(entity.get('name') or '').strip() or None,
                    occurrences=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    resolved=False,
                ))
            else:
                issue.occurrences += 1
                issue.last_seen_at = now

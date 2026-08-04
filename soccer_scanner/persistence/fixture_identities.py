"""Transactional provider aliases and durable public fixture identities."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, text, tuple_, update
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
        return self.resolve_many([(group, match_evidence)])[0]

    def resolve_many(self, entries):
        pending = list(entries)
        if not pending:
            return []
        last_error = None
        for _attempt in range(3):
            try:
                return self._resolve_many_once(pending)
            except IntegrityError as error:
                last_error = error
        raise FixtureIdentityError(
            'Concurrent fixture identity resolution did not converge.'
        ) from last_error

    def _resolve_many_once(self, entries):
        now = utc_now()
        records = []
        provider_identities = set()
        fallback_public_ids = set()
        kickoffs = []
        for group, match_evidence in entries:
            aliases = _provider_identities(group)
            if not aliases:
                raise FixtureIdentityError(
                    'Fixture is missing a provider event identity.'
                )
            providers = {}
            for provider, event_id in aliases:
                providers.setdefault(provider, set()).add(event_id)
            if any(len(event_ids) > 1 for event_ids in providers.values()):
                raise FixtureIdentityError(
                    'Fixture contains conflicting identities for one provider.'
                )
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
            evidence = _canonical_evidence(match_evidence)
            fallback_public_id = provider_fallback_public_id(preferred)
            records.append({
                'match': match_evidence,
                'provider_identities': aliases,
                'provider_map': providers,
                'evidence': evidence,
                'fallback_public_id': fallback_public_id,
            })
            provider_identities.update(aliases)
            fallback_public_ids.add(fallback_public_id)
            if evidence['kickoff_utc'] is not None:
                kickoffs.append(evidence['kickoff_utc'])

        with self.database.session_scope() as session:
            current_aliases = session.scalars(
                select(FixtureProviderAlias).where(
                    tuple_(
                        FixtureProviderAlias.provider,
                        FixtureProviderAlias.provider_event_id,
                    ).in_(provider_identities)
                )
            ).all()
            aliased_public_ids = {
                alias.public_id
                for alias in current_aliases
            }
            identity_conditions = [
                FixtureIdentity.public_id.in_(fallback_public_ids)
            ]
            if aliased_public_ids:
                identity_conditions.append(
                    FixtureIdentity.public_id.in_(aliased_public_ids)
                )
            if kickoffs:
                identity_conditions.append(
                    FixtureIdentity.kickoff_utc.between(
                        min(kickoffs) - MATCH_TOLERANCE,
                        max(kickoffs) + MATCH_TOLERANCE,
                    )
                )
            identities = session.scalars(
                select(FixtureIdentity).where(or_(*identity_conditions))
            ).all()
            identity_map = {
                identity.public_id: identity
                for identity in identities
            }

            if identity_map:
                existing_aliases = session.scalars(
                    select(FixtureProviderAlias).where(
                        FixtureProviderAlias.public_id.in_(identity_map)
                    )
                ).all()
            else:
                existing_aliases = current_aliases
            alias_map = {
                (alias.provider, alias.provider_event_id): alias
                for alias in existing_aliases
            }
            aliases_by_public_id = {}
            for alias in existing_aliases:
                aliases_by_public_id.setdefault(alias.public_id, []).append(alias)

            public_ids = []
            for record in records:
                aliases = record['provider_identities']
                evidence = record['evidence']
                existing_public_ids = {
                    alias_map[provider_identity].public_id
                    for provider_identity in aliases
                    if provider_identity in alias_map
                }
                if existing_public_ids:
                    if len(existing_public_ids) == 1:
                        public_id = next(iter(existing_public_ids))
                    else:
                        public_id = self._reconcile(
                            session,
                            existing_public_ids,
                            now,
                        )
                    identity = identity_map.get(public_id)
                    if identity is None:
                        raise FixtureIdentityError(
                            'Provider alias points to a missing fixture identity.'
                        )
                else:
                    identity = self._find_preloaded_candidate(
                        identity_map.values(),
                        aliases_by_public_id,
                        record['provider_map'],
                        evidence,
                    )
                    if identity is None:
                        public_id = record['fallback_public_id']
                        if public_id in identity_map:
                            raise FixtureIdentityError(
                                'Provider-qualified public fixture identity collision.'
                            )
                        identity = FixtureIdentity(public_id=public_id, **evidence)
                        session.add(identity)
                        identity_map[public_id] = identity
                    else:
                        public_id = identity.public_id

                for field, value in evidence.items():
                    if value is not None:
                        setattr(identity, field, value)
                identity.updated_at = now

                for provider, event_id in aliases:
                    alias = alias_map.get((provider, event_id))
                    if alias is None:
                        alias = FixtureProviderAlias(
                            provider=provider,
                            provider_event_id=event_id,
                            public_id=public_id,
                        )
                        session.add(alias)
                        alias_map[(provider, event_id)] = alias
                        aliases_by_public_id.setdefault(public_id, []).append(alias)
                    elif alias.public_id != public_id:
                        previous_public_id = alias.public_id
                        alias.public_id = public_id
                        aliases_by_public_id[previous_public_id].remove(alias)
                        aliases_by_public_id.setdefault(public_id, []).append(alias)
                public_ids.append(public_id)

            self._record_unresolved_batch(
                session,
                (record['match'] for record in records),
                now,
            )
            return public_ids

    @staticmethod
    def _find_preloaded_candidate(
        identities,
        aliases_by_public_id,
        provider_map,
        evidence,
    ):
        required = (
            'canonical_competition_id',
            'canonical_home_team_id',
            'canonical_away_team_id',
            'kickoff_utc',
        )
        if any(evidence[field] is None for field in required):
            return None
        candidates = []
        for identity in identities:
            kickoff = _aware(identity.kickoff_utc)
            if (
                identity.canonical_competition_id
                != evidence['canonical_competition_id']
                or identity.canonical_home_team_id
                != evidence['canonical_home_team_id']
                or identity.canonical_away_team_id
                != evidence['canonical_away_team_id']
                or identity.season_key != evidence['season_key']
                or identity.stage_key != evidence['stage_key']
                or kickoff is None
                or abs((kickoff - evidence['kickoff_utc']).total_seconds())
                > MATCH_TOLERANCE.total_seconds()
            ):
                continue
            candidate_provider_ids = {}
            for alias in aliases_by_public_id.get(identity.public_id, ()):
                candidate_provider_ids.setdefault(alias.provider, set()).add(
                    alias.provider_event_id
                )
            if any(
                candidate_provider_ids[provider] != event_ids
                for provider, event_ids in provider_map.items()
                if provider in candidate_provider_ids
            ):
                continue
            candidates.append(identity)
        return candidates[0] if len(candidates) == 1 else None

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
    def _record_unresolved_batch(session, matches, now):
        observations = {}
        for match in matches:
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
                key = (kind, provider, provider_id)
                observation = observations.setdefault(key, {
                    'display_name': str(entity.get('name') or '').strip() or None,
                    'occurrences': 0,
                })
                observation['occurrences'] += 1

        if not observations:
            return
        issues = session.scalars(
            select(IdentityResolutionIssue).where(
                tuple_(
                    IdentityResolutionIssue.kind,
                    IdentityResolutionIssue.provider,
                    IdentityResolutionIssue.provider_id,
                ).in_(observations)
            )
        ).all()
        issue_map = {
            (issue.kind, issue.provider, issue.provider_id): issue
            for issue in issues
        }
        for key, observation in observations.items():
            issue = issue_map.get(key)
            if issue is None:
                kind, provider, provider_id = key
                session.add(IdentityResolutionIssue(
                    kind=kind,
                    provider=provider,
                    provider_id=provider_id,
                    display_name=observation['display_name'],
                    occurrences=observation['occurrences'],
                    first_seen_at=now,
                    last_seen_at=now,
                    resolved=False,
                ))
            else:
                issue.occurrences += observation['occurrences']
                issue.last_seen_at = now

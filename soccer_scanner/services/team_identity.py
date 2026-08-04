"""Maintained, provider-qualified soccer team identity resolution."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


def normalize_alias(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(character for character in text if not unicodedata.combining(character))
    return ''.join(character for character in text.casefold() if character.isalnum())


@dataclass(frozen=True)
class TeamIdentity:
    canonicalId: str | None
    canonicalName: str | None
    provider: str | None
    providerId: str | None
    providerIds: dict

    def as_dict(self):
        return {
            'canonicalId': self.canonicalId,
            'provider': self.provider,
            'providerId': self.providerId,
            'providerIds': dict(self.providerIds),
        }


class TeamIdentityResolver:
    def __init__(self, entries):
        self._canonical = {}
        self._provider = {}
        self._aliases = {}
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            canonical_id = str(raw_entry.get('canonicalId') or '').strip()
            name = str(raw_entry.get('name') or '').strip()
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', canonical_id) or not name:
                continue
            provider_ids = {
                str(provider).strip(): str(provider_id).strip()
                for provider, provider_id in (raw_entry.get('providerIds') or {}).items()
                if str(provider).strip() and str(provider_id).strip()
            }
            entry = {
                'canonicalId': canonical_id,
                'name': name,
                'providerIds': provider_ids,
            }
            if canonical_id in self._canonical:
                raise ValueError(f'Duplicate canonical team identity: {canonical_id}')
            self._canonical[canonical_id] = entry
            for provider, provider_id in provider_ids.items():
                key = (provider, provider_id)
                if key in self._provider:
                    raise ValueError(f'Duplicate provider team identity: {provider}')
                self._provider[key] = entry
            aliases = [name, *(raw_entry.get('aliases') or [])]
            for alias in aliases:
                normalized = normalize_alias(alias)
                if normalized:
                    self._aliases.setdefault(normalized, []).append(entry)

    @classmethod
    def from_file(cls, path):
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(payload.get('teams', []))

    def resolve(self, provider, provider_id, name=None):
        provider = str(provider or '').strip() or None
        provider_id = str(provider_id or '').strip() or None
        entry = self._provider.get((provider, provider_id)) if provider and provider_id else None
        if entry is None:
            candidates = self._aliases.get(normalize_alias(name), [])
            unique = {candidate['canonicalId']: candidate for candidate in candidates}
            if len(unique) == 1:
                entry = next(iter(unique.values()))
        if entry is None:
            observed = {provider: provider_id} if provider and provider_id else {}
            return TeamIdentity(None, None, provider, provider_id, observed)
        return TeamIdentity(
            entry['canonicalId'],
            entry['name'],
            provider,
            provider_id,
            dict(entry['providerIds']),
        )

    def provider_id(self, canonical_id, provider):
        entry = self._canonical.get(str(canonical_id or ''))
        if entry is None:
            return None
        return entry['providerIds'].get(provider)

    def canonical(self, canonical_id):
        entry = self._canonical.get(str(canonical_id or ''))
        return dict(entry) if entry is not None else None

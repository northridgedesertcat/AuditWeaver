"""YAML-backed repositories for rule profiles and regex libraries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class RuleConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedRules:
    profiles: tuple[dict[str, Any], ...]
    libraries: dict[str, dict[str, Any]]


class RuleLoader:
    """Loads and validates the two independently managed YAML repositories."""

    def __init__(self, profile_path: str | Path, regex_path: str | Path) -> None:
        self.profile_path = Path(profile_path)
        self.regex_path = Path(regex_path)

    def load(self) -> LoadedRules:
        libraries = self.load_regex_libraries()
        profiles = self.load_profiles(libraries)
        return LoadedRules(tuple(profiles), libraries)

    def load_regex_libraries(self) -> dict[str, dict[str, Any]]:
        libraries: dict[str, dict[str, Any]] = {}
        for file_path in self._yaml_files(self.regex_path):
            library = self._read_yaml(file_path)
            library_id = library.get("id")
            patterns = library.get("patterns")
            if not isinstance(library_id, str) or not library_id:
                raise RuleConfigurationError(f"{file_path}: regex library requires a non-empty id")
            if library_id in libraries:
                raise RuleConfigurationError(f"Duplicate regex library id: {library_id}")
            if not isinstance(patterns, list):
                raise RuleConfigurationError(f"{file_path}: patterns must be a list")
            pattern_ids: set[str] = set()
            for pattern in patterns:
                if not isinstance(pattern, Mapping) or not isinstance(pattern.get("id"), str) or not isinstance(pattern.get("regex"), str):
                    raise RuleConfigurationError(f"{file_path}: each pattern needs string id and regex")
                if pattern["id"] in pattern_ids:
                    raise RuleConfigurationError(f"{file_path}: duplicate pattern id {pattern['id']}")
                pattern_ids.add(pattern["id"])
            libraries[library_id] = library
        return libraries

    def load_profiles(self, libraries: Mapping[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        libraries = libraries if libraries is not None else self.load_regex_libraries()
        profiles: list[dict[str, Any]] = []
        profile_ids: set[str] = set()
        for file_path in self._yaml_files(self.profile_path):
            profile = self._read_yaml(file_path)
            profile_id = profile.get("id")
            target_fields = profile.get("target_fields")
            matchers = profile.get("matchers")
            if not isinstance(profile_id, str) or not profile_id:
                raise RuleConfigurationError(f"{file_path}: profile requires a non-empty id")
            if profile_id in profile_ids:
                raise RuleConfigurationError(f"Duplicate rule profile id: {profile_id}")
            if not isinstance(target_fields, list) or not all(isinstance(field, str) for field in target_fields):
                raise RuleConfigurationError(f"{file_path}: target_fields must be a string list")
            if not isinstance(matchers, list) or not matchers:
                raise RuleConfigurationError(f"{file_path}: matchers must be a non-empty list")
            for matcher in matchers:
                if not isinstance(matcher, Mapping) or matcher.get("type") != "regex":
                    raise RuleConfigurationError(f"{file_path}: only regex matchers are supported")
                if matcher.get("library") not in libraries:
                    raise RuleConfigurationError(f"{file_path}: unknown regex library {matcher.get('library')!r}")
            profile_ids.add(profile_id)
            profiles.append(profile)
        return profiles

    @staticmethod
    def _yaml_files(directory: Path) -> list[Path]:
        if not directory.is_dir():
            raise RuleConfigurationError(f"Rule repository does not exist: {directory}")
        files = sorted((*directory.glob("*.yaml"), *directory.glob("*.yml")))
        if not files:
            raise RuleConfigurationError(f"Rule repository is empty: {directory}")
        return files

    @staticmethod
    def _read_yaml(file_path: Path) -> dict[str, Any]:
        try:
            with file_path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except yaml.YAMLError as error:
            raise RuleConfigurationError(f"Invalid YAML in {file_path}: {error}") from error
        if not isinstance(data, dict):
            raise RuleConfigurationError(f"{file_path}: YAML root must be a mapping")
        return data

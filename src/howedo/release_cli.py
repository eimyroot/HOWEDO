from __future__ import annotations

import argparse
import json
from pathlib import Path

from howedo.release_bundle import build_release_bundle, verify_release_bundle


def build_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--git-tree", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--sdist", required=True)
    parser.add_argument("--sbom", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = build_release_bundle(
        root=args.root,
        package_version=args.version,
        tag=args.tag,
        git_commit=args.git_commit,
        git_tree=args.git_tree,
        wheel=args.wheel,
        sdist=args.sdist,
        sbom=args.sbom,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest.record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-tag")
    parser.add_argument("--expected-commit")
    parser.add_argument("--expected-tree")
    args = parser.parse_args()

    raw = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("release bundle manifest must be a JSON object")
    verify_release_bundle(
        raw,
        root=args.root,
        expected_tag=args.expected_tag,
        expected_commit=args.expected_commit,
        expected_tree=args.expected_tree,
    )


if __name__ == "__main__":
    verify_main()

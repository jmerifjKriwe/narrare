#!/usr/bin/env python3
"""Query the SonarCloud API for the narrare project."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ORG = "jmerifjkriwe"
DEFAULT_PROJECT = "jmerifjKriwe_narrare"
BASE = "https://sonarcloud.io/api"
EXCLUDE_PARTS = ("docs/", ".agents/", "node_modules", ".venv", "tests/")


def load_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    token = os.environ.get("SONAR_TOKEN")
    if token:
        return token
    cfg = Path.home() / ".config" / "openchamber" / "environment.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            token = data.get("user", {}).get("variables", {}).get("SONAR_TOKEN")
            if token:
                return str(token)
        except OSError, ValueError, AttributeError:
            pass
    sys.exit("SONAR_TOKEN missing: set the env var or pass --token")


def api(path: str, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-https URL: {url!r}")
    req = urllib.request.Request(url)  # noqa: S310 - scheme pinned above
    creds = base64.b64encode((token + ":").encode("ascii")).decode("ascii")
    req.add_header("Authorization", f"Basic {creds}")
    with urllib.request.urlopen(req) as resp:  # noqa: S310 - scheme pinned above
        return json.load(resp)


def cmd_qg(args: argparse.Namespace, token: str) -> int:
    data = api("/qualitygates/project_status", token, {"projectKey": args.project})
    status = data["projectStatus"]
    print(f"Quality gate: {status['status']}")
    for c in status.get("conditions", []):
        print(
            f"  {c['status']:2}  {c['metricKey']:40} "
            f"actual={c.get('actualValue')}  threshold={c.get('errorThreshold')}"
        )
    return 0


def _is_app_code(component: str) -> bool:
    return not any(part in component for part in EXCLUDE_PARTS)


def cmd_issues(args: argparse.Namespace, token: str) -> int:
    params: dict[str, Any] = {
        "componentKeys": args.project,
        "statuses": "OPEN,CONFIRMED,REOPENED",
        "ps": 100,
    }
    if args.type:
        params["types"] = args.type
    if args.severity:
        params["severities"] = args.severity

    collected: list[dict[str, Any]] = []
    page = 1
    while True:
        params["p"] = page
        data = api("/issues/search", token, params)
        issues = data.get("issues", [])
        collected.extend(issues)
        total = data.get("total", 0)
        if len(collected) >= total or not issues:
            break
        page += 1
        if args.limit and len(collected) >= args.limit * 4:
            break

    if not args.all:
        collected = [i for i in collected if _is_app_code(i.get("component", ""))]

    if args.component:
        needle = args.component
        collected = [i for i in collected if needle in i.get("component", "")]

    if args.limit:
        collected = collected[: args.limit]

    for i in collected:
        comp = i.get("component", "").split(":", 1)[-1]
        line = i.get("line")
        where = f"{comp}:{line}" if line else comp
        print(
            f"{i.get('key')} | {i.get('type'):10} | {i.get('severity'):8} | "
            f"{where} | {i.get('message')}"
        )
    print(f"\nshown: {len(collected)}")
    return 0


def cmd_measures(args: argparse.Namespace, token: str) -> int:
    metrics = args.metrics or ",".join(
        [
            "coverage",
            "duplicated_lines_density",
            "complexity",
            "cognitive_complexity",
            "code_smells",
            "bugs",
            "vulnerabilities",
            "security_hotspots",
            "ncloc",
        ]
    )
    data = api(
        "/measures/component",
        token,
        {"component": args.project, "metricKeys": metrics},
    )
    comp = data.get("component", {})
    for m in comp.get("measures", []):
        print(f"{m['metric']:32} {m.get('value')}")
    return 0


def cmd_hotspots(args: argparse.Namespace, token: str) -> int:
    params: dict[str, Any] = {"projectKey": args.project, "ps": 100}
    if args.status:
        params["status"] = args.status
    data = api("/hotspots/search", token, params)
    hotspots = data.get("hotspots", [])
    for h in hotspots:
        comp = h.get("component", "").split(":", 1)[-1]
        line = h.get("line")
        where = f"{comp}:{line}" if line else comp
        print(
            f"{h.get('key')} | {h.get('status'):12} | "
            f"{h.get('vulnerabilityProbability'):8} | {where} | {h.get('message')}"
        )
    print(f"\nshown: {len(hotspots)} (total: {data.get('paging', {}).get('total', len(hotspots))})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sonar", description="Query the SonarCloud API for narrare.")
    p.add_argument("--org", default=os.environ.get("SONAR_ORG", DEFAULT_ORG))
    p.add_argument("--project", default=os.environ.get("SONAR_PROJECT", DEFAULT_PROJECT))
    p.add_argument("--token", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("qg", help="quality gate project status")

    iss = sub.add_parser("issues", help="list open issues")
    iss.add_argument("--all", action="store_true", help="include docs/.agents/tests")
    iss.add_argument("--type", help="BUG,VULNERABILITY,CODE_SMELL (comma list)")
    iss.add_argument("--severity", help="BLOCKER,CRITICAL,MAJOR,MINOR,INFO (comma list)")
    iss.add_argument("--component", help="filter component path contains this")
    iss.add_argument("--limit", type=int, default=0, help="cap output rows")

    mea = sub.add_parser("measures", help="component measures")
    mea.add_argument("--metrics", help="comma list of metric keys")

    hot = sub.add_parser("hotspots", help="security hotspots")
    hot.add_argument("--status", default="TO_REVIEW", help="TO_REVIEW,REVIEWED (or omit for all)")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    token = load_token(args.token)
    if args.cmd == "qg":
        return cmd_qg(args, token)
    if args.cmd == "issues":
        return cmd_issues(args, token)
    if args.cmd == "measures":
        return cmd_measures(args, token)
    if args.cmd == "hotspots":
        return cmd_hotspots(args, token)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

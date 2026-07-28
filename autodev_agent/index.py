"""CLI entry point. `autodev run --ticket tickets/T-001.json --repo ./target-app`"""

import argparse
import json
from pathlib import Path

from .agent import agent_process

def run(ticket: Path, repo: Path):
  # Parsed rather than echoed, so a malformed ticket fails here and not later.
  # print(json.dumps(json.loads(ticket.read_text()), indent=2))
  agent_process(ticket, repo)

def main(argv=None):
  parser = argparse.ArgumentParser(prog='autodev')
  # Required subcommand, so bare `autodev` prints usage instead of doing something.
  commands = parser.add_subparsers(dest='command', required=True)

  run_cmd = commands.add_parser('run', help='Resolve one ticket against a target repo')
  run_cmd.add_argument('--ticket', required=True, type=Path, help='Path to a ticket JSON file')
  run_cmd.add_argument('--repo', type=Path, default=Path('./target-app'), help='Repo to work in')

  args = parser.parse_args(argv)
  try:
    run(args.ticket, args.repo)
  except (OSError, json.JSONDecodeError) as err:
    raise SystemExit(f'autodev: cannot read ticket {args.ticket}: {err}')

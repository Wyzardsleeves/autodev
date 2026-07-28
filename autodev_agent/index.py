"""CLI entry point. `autodev run --ticket tickets/T-001.json --repo ./target-app`"""

import argparse
import json
from pathlib import Path

BANNER = """
  -------------------------------------------
  Ticketeer
  -------------------------------------------
  Welcome to Ticketeer! 🎟️
"""


def run(ticket: Path, repo: Path):
  print(BANNER)
  # Parsed rather than echoed, so a malformed ticket fails here and not later.
  data = json.loads(ticket.read_text())
  print(f'  ticket: {ticket}  ->  {data.get("id")} ({data.get("type")}) {data.get("title")}')
  print(f'  repo:   {repo}\n')

  # Imported here, not at module scope: `autodev --help` should not pay for
  # langgraph's import time or need a model key.
  from .agent import agent_process

  report = agent_process(data, repo)
  # Non-zero exit for anything but a clean resolve, so CI can gate on it.
  raise SystemExit(0 if report['status'] == 'resolved' else 1)


def main(argv=None):
  parser = argparse.ArgumentParser(prog='autodev')
  # Required subcommand, so bare `autodev` prints usage instead of doing something.
  commands = parser.add_subparsers(dest='command', required=True)

  run_cmd = commands.add_parser('run', help='Resolve one ticket against a target repo')
  run_cmd.add_argument('--ticket', required=True, type=Path, help='Path to a ticket JSON file')
  run_cmd.add_argument('--repo', type=Path, default=Path('./target-app'), help='Repo to work in')

  args = parser.parse_args(argv)
  if not args.repo.is_dir():
    raise SystemExit(f'autodev: no such repo directory: {args.repo}')
  try:
    run(args.ticket, args.repo)
  except (OSError, json.JSONDecodeError) as err:
    raise SystemExit(f'autodev: cannot read ticket {args.ticket}: {err}')

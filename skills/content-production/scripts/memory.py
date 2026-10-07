#!/usr/bin/env python3
"""Discover project-owned ViewPrinter memory and append immutable event records.

Python standard library only. No operation writes inside the installed skill.
Memory lives at <project>/.viewprinter/content-memory, so the project is the
directory holding .viewprinter and config stores no path. VIEWPRINTER_CONTENT_MEMORY
overrides the location for init and locate.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile


SCHEMA_VERSION = 1
SKILL_ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ("feedback", "changes", "findings")
DIRECTORIES = ("formats", "batches", "state", "history", *("history/" + c for c in COLLECTIONS))
MEMORY_RELATIVE = Path(".viewprinter") / "content-memory"
# Written by content-publishing's learn.py, which can run before init.
POSTING_LOGS = (Path("history") / "publications", Path("history") / "posting")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class MemoryError(ValueError):
    """An unsafe path, incomplete memory, or conflicting immutable record."""


def absolute_path(value):
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def refuse_link(path):
    if path.is_symlink():
        raise MemoryError("Symlinks are not allowed in memory: {}".format(path))


def memory_path(value):
    """Resolve symlinks above the memory (macOS /tmp is one); allow none from .viewprinter down."""
    path = absolute_path(value)
    if path.parts[-2:] == MEMORY_RELATIVE.parts:
        root = path.parents[1].resolve()
        refuse_link(root / MEMORY_RELATIVE.parts[0])
        path = root / MEMORY_RELATIVE
    else:
        path = path.parent.resolve() / path.name
    refuse_link(path)
    if within(path, SKILL_ROOT):
        raise MemoryError("Memory must live outside the installed skill: {}".format(path))
    return path


def inside(memory, relative):
    """A path in memory, refusing a symlink at any component so writes cannot be redirected."""
    path = memory
    for part in Path(relative).parts:
        path = path / part
        refuse_link(path)
    return path


def read_object(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream, parse_constant=lambda token: invalid_constant(token))
    except (OSError, ValueError) as error:
        raise MemoryError("Cannot read JSON object {}: {}".format(path, error)) from error
    if not isinstance(value, dict):
        raise MemoryError("Expected JSON object: {}".format(path))
    return value


def invalid_constant(token):
    raise ValueError("Nonstandard JSON constant: {}".format(token))


def validate_memory(value):
    path = memory_path(value)
    if not path.is_dir():
        raise MemoryError("Memory directory does not exist: {}".format(path))
    config = read_object(inside(path, "config.json"))
    # An older config's absolute projectRoot is ignored, so a moved, renamed,
    # cloned or worktree copy of the project keeps working.
    if (type(config.get("schemaVersion")) is not int
            or config["schemaVersion"] != SCHEMA_VERSION
            or not isinstance(config.get("projectName"), str)
            or not config["projectName"].strip()):
        raise MemoryError("Invalid memory config: {}".format(path / "config.json"))
    for relative in DIRECTORIES:
        if not inside(path, relative).is_dir():
            raise MemoryError("Incomplete memory; missing directory: {}".format(path / relative))
    if not inside(path, "project.md").is_file():
        raise MemoryError("Incomplete memory; missing project.md")
    state = read_object(inside(path, "state/carry-forward.json"))
    if (type(state.get("schemaVersion")) is not int
            or state["schemaVersion"] != SCHEMA_VERSION
            or not isinstance(state.get("openItems"), list)):
        raise MemoryError("Invalid carry-forward state")
    return path


def json_bytes(value):
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError) as error:
        raise MemoryError("Record is not valid JSON: {}".format(error)) from error


def write_exclusive(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def environment_memory():
    override = os.environ.get("VIEWPRINTER_CONTENT_MEMORY")
    if override is None:
        return None
    if not override.strip():
        raise MemoryError("VIEWPRINTER_CONTENT_MEMORY is set but empty")
    return memory_path(override)


def started_by_posting(memory):
    """A memory content-publishing's learn.py started before init ran: no config, and
    nothing but its publication and posting logs."""
    if memory.is_symlink() or not memory.is_dir() or (memory / "config.json").exists():
        return False
    for path in memory.rglob("*"):
        relative = path.relative_to(memory)
        if path.name == ".DS_Store" and path.is_file() and not path.is_symlink():
            continue  # Finder's folder settings
        if path.is_symlink():
            return False
        if path.is_dir() and relative not in (Path("history"), *POSTING_LOGS):
            return False
        if not path.is_dir() and relative.parent not in POSTING_LOGS:
            return False
    return True


def initialize(project, name=None):
    project = absolute_path(project).resolve()
    if not project.is_dir():
        raise MemoryError("Project must be an existing directory: {}".format(project))
    name = (name if name is not None else project.name).strip()
    if not name:
        raise MemoryError("Project name must not be empty")
    override = environment_memory()
    memory = override if override is not None else memory_path(project / MEMORY_RELATIVE)
    if memory.exists() and not started_by_posting(memory):
        return validate_memory(memory)
    memory.parent.mkdir(parents=True, exist_ok=True)
    refuse_link(memory.parent)
    try:
        memory.mkdir()
    except FileExistsError:
        if not started_by_posting(memory):
            return validate_memory(memory)
    # A failure leaves an explicitly incomplete directory for human review. Never
    # overwrite or delete an existing directory to repair initialization; the one
    # exception is completing a memory the posting helper started, keeping its logs.
    for relative in DIRECTORIES:
        (memory / relative).mkdir(exist_ok=True)
    write_exclusive(memory / "config.json", json_bytes({
        "schemaVersion": SCHEMA_VERSION, "projectName": name,
    }))
    write_exclusive(memory / "state" / "carry-forward.json", json_bytes({
        "schemaVersion": SCHEMA_VERSION, "openItems": [],
    }))
    write_exclusive(memory / "project.md", (
        "# {}\n\nProject preferences and durable content context.\n".format(name)
    ).encode("utf-8"))
    return validate_memory(memory)


def locate(start=None):
    override = environment_memory()
    if override is not None:
        return validate_memory(override)
    start = absolute_path(Path.cwd() if start is None else start).resolve()
    if within(start, SKILL_ROOT):
        raise MemoryError("Discovery must start outside the installed skill: {}".format(start))
    if not start.exists():
        raise MemoryError("Discovery start does not exist: {}".format(start))
    if start.is_file():
        start = start.parent
    for project in (start, *start.parents):
        candidate = project / MEMORY_RELATIVE
        if candidate.exists() or candidate.is_symlink():
            return validate_memory(candidate)
    raise MemoryError("No project memory found; run init --project with an explicit project path")


def append(memory, collection, record):
    if collection not in COLLECTIONS:
        raise MemoryError("Unknown collection: {}".format(collection))
    memory = validate_memory(memory)
    if not isinstance(record, dict):
        raise MemoryError("Record must be a JSON object")
    identifier = record.get("id")
    if not isinstance(identifier, str) or not SAFE_ID.fullmatch(identifier):
        raise MemoryError("id must be 1-128 filename-safe characters, beginning with a letter or digit")
    if not isinstance(record.get("createdAt"), str) or not record["createdAt"].strip():
        raise MemoryError("Record requires a nonempty createdAt string")
    data = json_bytes(record)
    destination = inside(memory, Path("history", collection, identifier + ".json"))
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            try:
                # Linking a fully written file publishes it atomically and exclusively.
                # Concurrent events never read/modify/write a shared collection file.
                os.link(temporary, destination)
            except FileExistsError:
                raise
            except OSError:
                # No hard links on this drive (FAT, exFAT, some network shares). An exclusive
                # create still never overwrites a record; a reader may briefly see it half written.
                with open(destination, "xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
        except FileExistsError:
            refuse_link(destination)
            if json_bytes(read_object(destination)) != data:
                raise MemoryError("Conflicting immutable record id: {}".format(identifier))
        return destination
    finally:
        os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init", help="Initialize memory in an explicit project")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--name")
    locate_parser = commands.add_parser("locate", help="Find existing project memory without creating it")
    locate_parser.add_argument("--start")
    append_parser = commands.add_parser("append", help="Append one immutable JSON event")
    append_parser.add_argument("--memory", required=True)
    append_parser.add_argument("--collection", required=True, choices=COLLECTIONS)
    append_parser.add_argument("--file", required=True, help="the event's JSON file, from any location")
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            result = initialize(arguments.project, arguments.name)
        elif arguments.command == "locate":
            result = locate(arguments.start)
        else:
            result = append(arguments.memory, arguments.collection, read_object(absolute_path(arguments.file)))
        print(result)
        return 0
    except (MemoryError, OSError) as error:
        print("memory: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())

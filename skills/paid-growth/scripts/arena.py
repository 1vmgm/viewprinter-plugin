#!/usr/bin/env python3
"""Project memory and the rule evaluator for the paid-growth skill.

Python standard library only. No operation writes inside the installed skill.
VIEWPRINTER_PAID_GROWTH overrides the default memory location.

  arena.py init --project <root> --name <name>
  arena.py locate [--start <directory>]
  arena.py evaluate [--memory <dir>] --ads <pull.csv|pull.json> [--window TEXT] [--account-window] [--json]
  arena.py append --memory <dir> --collection decisions --file <event.json>

The evaluator applies references/decision-rules.md in the order written there,
reading the input described in references/evaluator.md. Its verdicts are
proposals for a person to approve, not instructions to act.
"""

import argparse
import csv
from datetime import date, timedelta
import json
import math
import os
from pathlib import Path
import re
import sys


SCHEMA_VERSION = 1
SKILL_ROOT = Path(__file__).resolve().parents[1]
MEMORY_RELATIVE = Path(".viewprinter") / "paid-growth"
ENVIRONMENT = "VIEWPRINTER_PAID_GROWTH"
COLLECTIONS = ("rounds", "decisions", "findings")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
Z90 = 1.6448536269514722
BLANKS = ("", "-", "--", "null", "none", "n/a", "na")

# Spend thresholds are multiples of break-even cost per paying customer, so
# the same rules hold at any price point. See references/decision-rules.md.
DEFAULT_RULES = {
    "engagementCheckMultiple": 1.5,
    "noPayerMultiple": 3.0,
    "ctrFloor": 0.006,
    "holdFloor": 0.35,
    "floorsBasis": "provisional",
    "starvedGroupMultiple": 4.0,
    "starvedShare": 0.15,
    "valueCutMinPayers": 5,
    "valueCutRoas": 0.8,
    "fewPayerRoas": 1.0,
    "graduatePayers": 4,
    "graduateRoas": 1.0,
    "scalePayers": 15,
    "scaleRoas": 1.2,
    "scaleStep": 0.2,
    "pullBackRoas": 0.8,
    "fatigueDrop": 0.3,
    "fatigueMinEvents": 100,
    "governorRoas": 1.0,
}
TEXT_RULES = ("floorsBasis",)

# Canonical column -> accepted headers, compared after normalize_header().
# Covers the evaluator's own names, Marketing API metric names and the usual
# English Ads Manager export labels.
ALIASES = {
    "ad_id": ("ad_id", "ad id", "adid"),
    "name": ("name", "ad_name", "ad name"),
    "group": ("group", "ad_group", "ad group", "adgroup", "ad group name", "adgroup_name",
              "ad group id", "adgroup_id"),
    "role": ("role",),
    "round": ("round", "round_id", "launch_date", "launch date"),
    "date": ("date", "day", "by day", "stat_time_day"),
    "spend": ("spend", "cost", "amount spent"),
    "impressions": ("impressions",),
    "clicks": ("clicks", "clicks (destination)"),
    "ctr": ("ctr", "ctr (destination)"),
    "plays": ("plays", "video_play_actions", "video views"),
    "views_2s": ("views_2s", "video_watched_2s", "2-second video views", "2s views"),
    "hold": ("hold", "hold_2s", "2s hold"),
    "trials": ("trials", "trial starts", "trial_starts"),
    "purchases": ("purchases", "direct purchases", "direct_purchases"),
    "peak_ctr": ("peak_ctr", "peak ctr"),
    "peak_hold": ("peak_hold", "peak hold"),
}
COUNT_COLUMNS = ("spend", "impressions", "clicks", "plays", "views_2s", "trials", "purchases")
RATE_COLUMNS = ("ctr", "hold", "peak_ctr", "peak_hold")
# Rate -> (numerator, denominator). The rate column is read only when these are missing.
RATE_SOURCES = {"ctr": ("clicks", "impressions"), "hold": ("views_2s", "plays")}


class ArenaError(ValueError):
    """Unsafe memory, missing configuration, unreadable input or a conflicting record."""


# --- paths and memory ----------------------------------------------------------------

def absolute_path(value):
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def within(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def outside_skill(value):
    """Resolve symlinks first (macOS /tmp and /var are symlinks), then refuse the installed skill."""
    given = absolute_path(value)
    path = given.resolve()
    if within(given, SKILL_ROOT) or within(path, SKILL_ROOT):
        raise ArenaError("Memory must live outside the installed skill: {}".format(given))
    return path


def in_memory(memory, *parts):
    """A path below the memory root. A symlink inside memory is refused."""
    path = memory
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ArenaError("Symlinks are not allowed inside memory: {}".format(path))
    return path


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as error:
        raise ArenaError("Cannot read JSON {}: {}".format(path, error)) from error


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_new(path, data):
    """Create a file only if it does not exist; never overwrite."""
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    return True


def config_template(project, name):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "projectName": name,
        "projectRoot": str(project),
        "platform": "tiktok",
        "currency": "USD",
        "timezones": {"ads": None, "attribution": None, "revenue": None},
        "accounts": {"advertiserId": None, "campaignIds": []},
        "value": {
            "horizon": "first-year",
            "perTrial": None,
            "perPurchase": None,
            "trialShare": None,
            "breakEvenPerPayer": None,
            "basis": "provisional",
            "assumptions": {},
            "asOf": None,
            "recheckWhen": None,
        },
        "rules": dict(DEFAULT_RULES),
    }


PROJECT_MD = """# Paid growth

## Winning format
Not established yet. Write the hook, product reveal time, length, proof and tone the winners share.

## Hypotheses tested

## Standing preferences
"""


def validate_memory(value):
    path = outside_skill(value)
    if not path.is_dir():
        raise ArenaError("Memory directory does not exist: {}".format(path))
    config = read_json(in_memory(path, "config.json"))
    if not isinstance(config, dict) or config.get("schemaVersion") != SCHEMA_VERSION:
        raise ArenaError("Invalid memory config: {}".format(path / "config.json"))
    return path, config


def initialize(project, name=None):
    project = outside_skill(project)
    if not project.is_dir():
        raise ArenaError("Project directory does not exist: {}".format(project))
    override = os.environ.get(ENVIRONMENT)
    memory = outside_skill(override if override else project / MEMORY_RELATIVE)
    for parts in (("state",), ("snapshots",), *(("history", c) for c in COLLECTIONS)):
        in_memory(memory, *parts).mkdir(parents=True, exist_ok=True)
    if not write_new(in_memory(memory, "config.json"),
                     json_bytes(config_template(project, name or project.name))):
        validate_memory(memory)
    write_new(in_memory(memory, "project.md"), PROJECT_MD.encode("utf-8"))
    write_new(in_memory(memory, "state", "carry-forward.json"),
              json_bytes({"schemaVersion": SCHEMA_VERSION, "openItems": []}))
    return memory


def locate(start=None):
    override = os.environ.get(ENVIRONMENT)
    if override:
        return validate_memory(override)[0]
    directory = absolute_path(start or os.getcwd()).resolve()
    for candidate in (directory, *directory.parents):
        memory = candidate / MEMORY_RELATIVE
        if (memory / "config.json").is_file():
            return validate_memory(memory)[0]
    raise ArenaError("No {} found above {}; run init first.".format(MEMORY_RELATIVE, directory))


def append(memory, collection, record):
    if collection not in COLLECTIONS:
        raise ArenaError("Unknown collection: {}".format(collection))
    memory, _ = validate_memory(memory)
    if not isinstance(record, dict):
        raise ArenaError("An event must be a JSON object")
    identifier = record.get("id")
    if not isinstance(identifier, str) or not SAFE_ID.match(identifier):
        raise ArenaError("An event needs a safe string id (letters, digits, . _ -)")
    if not isinstance(record.get("createdAt"), str):
        raise ArenaError("An event needs a createdAt timestamp")
    in_memory(memory, "history", collection).mkdir(parents=True, exist_ok=True)
    path = in_memory(memory, "history", collection, "{}.json".format(identifier))
    data = json_bytes(record)
    if write_new(path, data):
        return path
    if path.read_bytes() == data:
        return path
    raise ArenaError("Event {} already exists with different content; use a new id".format(identifier))


# --- reading a pull --------------------------------------------------------------------

def normalize_header(value):
    return re.sub(r"[\s_]+", " ", str(value).strip().lower())


HEADER_MAP = {normalize_header(alias): canonical
              for canonical, aliases in ALIASES.items() for alias in aliases}


def blank(value):
    return value is None or str(value).strip().lower() in BLANKS


def parse_number(value):
    """None for blank. A '%' suffix is a percentage. NaN and infinity are refused."""
    if blank(value) or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace(",", "").replace("$", "")
        try:
            number = float(text.rstrip("%").strip())
        except ValueError as error:
            raise ArenaError("Not a number: {!r}".format(value)) from error
        if text.endswith("%"):
            number /= 100
    if not math.isfinite(number):
        raise ArenaError("Not a finite number: {!r}".format(value))
    return number


def parse_date(value, index):
    if blank(value):
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10].replace("/", "-"))
    except ValueError as error:
        raise ArenaError("Row {}: date must start YYYY-MM-DD, not {!r}".format(index, value)) from error


def load_rows(path):
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = read_json(path)
        rows = data.get("ads") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ArenaError("JSON pull must be a list of ads or {\"ads\": [...]}")
    else:
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        except OSError as error:
            raise ArenaError("Cannot read {}: {}".format(path, error)) from error
    return [normalize_row(row, index) for index, row in enumerate(rows, start=1)]


def normalize_row(raw, index):
    """One input row. A missing role or round stays None; evaluate() warns about it."""
    if not isinstance(raw, dict):
        raise ArenaError("Row {} is not an object".format(index))
    row = {}
    for key, value in raw.items():
        canonical = HEADER_MAP.get(normalize_header(key))
        if canonical and canonical not in row:
            row[canonical] = value
    for required in ("ad_id", "group", "spend"):
        if blank(row.get(required)):
            raise ArenaError("Row {} is missing {}".format(index, required))
    role = None if blank(row.get("role")) else str(row["role"]).strip().lower()
    if role not in (None, "test", "winner"):
        raise ArenaError("Row {}: role must be test or winner, not {!r}".format(index, role))
    ad = {
        "ad_id": str(row["ad_id"]).strip(),
        "name": None if blank(row.get("name")) else str(row["name"]).strip(),
        "group": str(row["group"]).strip(),
        "role": role,
        "round": None if blank(row.get("round")) else str(row["round"]).strip(),
        "date": parse_date(row.get("date"), index),
    }
    for column in COUNT_COLUMNS:
        ad[column] = parse_number(row.get(column))
        if ad[column] is not None and ad[column] < 0:
            raise ArenaError("Row {}: {} must not be negative".format(index, column))
    if ad["spend"] is None:
        raise ArenaError("Row {}: spend must be a number".format(index))
    for column in RATE_COLUMNS:
        value = row.get(column)
        sources = RATE_SOURCES.get(column)
        if sources and ad[sources[0]] is not None and ad[sources[1]] is not None:
            ad[column] = None  # computed from the counts instead
        elif blank(value):
            ad[column] = None
        elif not str(value).strip().endswith("%"):
            raise ArenaError(
                "Row {}: {} {!r} has no % sign. Write rates as percentages with the sign (0.45%), "
                "or give the counts (clicks and impressions; plays and 2-second views). TikTok's "
                "API reports ctr in percent without the sign, so a bare number is ambiguous.".format(
                    index, column, value))
        else:
            ad[column] = parse_number(value)
    return ad


# --- one entry per ad -------------------------------------------------------------------

def one_value(rows, field, ad_id):
    values = sorted({row[field] for row in rows if row[field] is not None})
    if len(values) > 1:
        raise ArenaError("Ad {} has conflicting {} values: {}".format(ad_id, field, ", ".join(values)))
    return values[0] if values else None


def total(rows, column):
    """Sum over days; a blank day counts as zero when another day has the column."""
    values = [row[column] for row in rows if row[column] is not None]
    return sum(values) if values else None


def three_day_rates(rows, numerator, denominator, minimum):
    """(latest, best) rate over 3-calendar-day windows with at least `minimum` numerator events."""
    by_date = {row["date"]: row for row in rows}
    first, last = min(by_date), max(by_date)
    rates = []
    end = first + timedelta(days=2)
    while end <= last:
        days = [by_date.get(end - timedelta(days=offset)) for offset in range(3)]
        top = sum(day[numerator] or 0 for day in days if day)
        bottom = sum(day[denominator] or 0 for day in days if day)
        rates.append(top / bottom if bottom and top >= minimum else None)
        end += timedelta(days=1)
    known = [rate for rate in rates if rate is not None]
    return (rates[-1] if rates else None), (max(known) if known else None)


def combine(rows, rules):
    """One entry per ad: daily rows are summed, and their series gives the fatigue inputs."""
    by_ad = {}
    for row in rows:
        by_ad.setdefault(row["ad_id"], []).append(row)
    ads, warnings = [], []
    for ad_id, days in by_ad.items():
        dates = [row["date"] for row in days]
        daily = len(days) > 1
        if daily and None in dates:
            raise ArenaError("Ad {} appears {} times without a date. Give one row per ad, or one "
                             "row per ad per day with a date column.".format(ad_id, len(days)))
        if daily and len(set(dates)) < len(dates):
            raise ArenaError("Ad {} has two rows for the same date".format(ad_id))
        role = one_value(days, "role", ad_id)
        ad = {
            "ad_id": ad_id,
            "name": next((row["name"] for row in days if row["name"]), ad_id),
            "group": one_value(days, "group", ad_id),
            "role": role or "test",
            "roleAssumed": role is None,
            "round": one_value(days, "round", ad_id),
            "days": len(days) if daily else None,
            "firstDate": min(dates).isoformat() if daily else None,
            "lastDate": max(dates).isoformat() if daily else None,
        }
        for column in COUNT_COLUMNS:
            ad[column] = total(days, column)
        for column in RATE_COLUMNS:
            values = [row[column] for row in days if row[column] is not None]
            if column.startswith("peak_"):
                ad[column] = max(values) if values else None
            elif not daily:
                ad[column] = values[0] if values else None
            else:
                ad[column] = None
                if values:
                    warnings.append("Ad {}: daily rows give {} without its counts, so it cannot be "
                                    "combined across days; include the counts.".format(ad_id, column))
        for metric, (numerator, denominator) in RATE_SOURCES.items():
            ad[metric + "Recent"], ad[metric + "Best"] = (
                three_day_rates(days, numerator, denominator, rules["fatigueMinEvents"])
                if daily else (None, None))
        ads.append(ad)
    return ads, warnings


# --- the rules ------------------------------------------------------------------------

def poisson_interval(count, z=Z90):
    """Two-sided 90% interval on a Poisson mean (Wilson-Hilferty approximation)."""
    lower = 0.0
    if count > 0:
        lower = max(0.0, count * (1 - 1 / (9 * count) - z / (3 * math.sqrt(count))) ** 3)
    upper_count = count + 1
    upper = upper_count * (1 - 1 / (9 * upper_count) + z / (3 * math.sqrt(upper_count))) ** 3
    return lower, upper


def config_number(section, key, value, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ArenaError("{}.{} in config.json must be a number, not {!r}".format(section, key, value))
    if value < 0 or (high is not None and value > high):
        raise ArenaError("{}.{} in config.json is out of range: {!r}".format(section, key, value))
    return float(value)


def config_section(config, name):
    section = config.get(name) or {}
    if not isinstance(section, dict):
        raise ArenaError("{} in config.json must be an object".format(name))
    return section


def read_rules(config):
    rules = dict(DEFAULT_RULES, **config_section(config, "rules"))
    for key in DEFAULT_RULES:
        if key not in TEXT_RULES:
            rules[key] = config_number("rules", key, rules[key])
    return rules


def value_model(config):
    """Break-even comes from config, never from the rows being judged."""
    value = config_section(config, "value")
    numbers = {key: config_number("value", key, value[key], high=1 if key == "trialShare" else None)
               for key in ("perTrial", "perPurchase", "trialShare", "breakEvenPerPayer")
               if value.get(key) is not None}
    mix = None
    if all(key in numbers for key in ("perTrial", "perPurchase", "trialShare")):
        share = numbers["trialShare"]
        mix = share * numbers["perTrial"] + (1 - share) * numbers["perPurchase"]
    break_even = numbers.get("breakEvenPerPayer", mix)
    if not break_even:
        raise ArenaError("No break-even. Set value.breakEvenPerPayer, or perTrial, perPurchase and "
                         "trialShare, in config.json; see references/economics.md. It is never "
                         "derived from the pull, whose trial/purchase mix moves with every window.")
    warnings = []
    if mix and abs(mix - break_even) > 0.05 * break_even:
        warnings.append("breakEvenPerPayer {} differs from the trialShare mix {} by more than 5%; "
                        "update the value model.".format(money(break_even), money(mix)))
    model = {
        "perTrial": numbers.get("perTrial", break_even),
        "perPurchase": numbers.get("perPurchase", break_even),
        "breakEven": break_even,
        "basis": value.get("basis") or "provisional",
        "horizon": value.get("horizon") or "unstated",
    }
    return model, warnings


def measure(ad, model):
    impressions, clicks = ad["impressions"], ad["clicks"]
    plays, views = ad["plays"], ad["views_2s"]
    ctr = clicks / impressions if impressions and clicks is not None else ad["ctr"]
    hold = views / plays if plays and views is not None else ad["hold"]
    known = ad["trials"] is not None or ad["purchases"] is not None
    trials, purchases = (ad["trials"] or 0), (ad["purchases"] or 0)
    payers = trials + purchases if known else None
    spend = ad["spend"]
    result = dict(ad, ctr=ctr, hold=hold, payers=payers, costPerPayer=None,
                  costRange=None, projectedRoas=None)
    if payers is not None:
        worth = trials * model["perTrial"] + purchases * model["perPurchase"]
        result["projectedRoas"] = worth / spend if spend > 0 else None
        if payers > 0:
            lower, upper = poisson_interval(payers)
            result["costPerPayer"] = spend / payers
            result["costRange"] = [spend / upper, spend / lower if lower > 0 else None]
    return result


def below(value, floor):
    return value is not None and value < floor


def losing(ad, rules, be, line):
    """Why the ad is losing money on the revenue rules, or None."""
    spend, payers, roas = ad["spend"], ad["payers"], ad["projectedRoas"]
    if payers is None:
        return None
    if payers == 0:
        if spend >= rules["noPayerMultiple"] * be:
            return "no paying customer at {} (≥ {:g}× break-even)".format(
                money(spend), rules["noPayerMultiple"])
        return None
    if roas is None:
        return None
    if payers >= rules["valueCutMinPayers"]:
        if roas < line:
            return "projected ROAS {:.2f} < {:g} on {:g} payers".format(roas, line, payers)
        return None
    # Few payers: judge on the optimistic end of their 90% range, as the no-payer rule does.
    best_case = roas * poisson_interval(payers)[1] / payers
    if best_case < rules["fewPayerRoas"]:
        return ("{:g} payer{} at projected ROAS {:.2f}; even the top of the 90% range ({:.2f}) "
                "is below {:g}".format(payers, "" if payers == 1 else "s", roas, best_case,
                                       rules["fewPayerRoas"]))
    return None


def judge_test(ad, round_spend, rules, be):
    spend, payers, roas = ad["spend"], ad["payers"], ad["projectedRoas"]
    if round_spend >= rules["starvedGroupMultiple"] * be and spend < rules["starvedShare"] * round_spend:
        share = spend / round_spend if round_spend else 0
        return "no read", "starved: {:.0%} of its {}'s spend; ends with the round".format(
            share, "round" if ad["round"] else "group")
    check = rules["engagementCheckMultiple"] * be
    if spend < check:
        return "wait", "below the first check ({} of {})".format(money(spend), money(check))
    if payers is None or payers < rules["scalePayers"]:
        weak = []
        if below(ad["ctr"], rules["ctrFloor"]):
            weak.append("CTR {} < {}".format(pct(ad["ctr"]), pct(rules["ctrFloor"])))
        if below(ad["hold"], rules["holdFloor"]):
            weak.append("2s hold {} < {}".format(pct(ad["hold"]), pct(rules["holdFloor"])))
        if weak:
            return "cut", "weak engagement: " + ", ".join(weak)
    if payers is None:
        return "hold", "payers unknown; engagement only, no revenue verdict"
    reason = losing(ad, rules, be, rules["valueCutRoas"])
    if reason:
        return "cut", reason
    if payers >= rules["graduatePayers"] and roas is not None and roas >= rules["graduateRoas"]:
        return "graduate", "{:g} payers at projected ROAS {:.2f}; propose moving it at round end".format(
            payers, roas)
    return "hold", "learning"


def judge_winner(ad, rules, be):
    payers, roas = ad["payers"], ad["projectedRoas"]
    tired = []
    for metric, label in (("ctr", "CTR"), ("hold", "2s hold")):
        if ad["days"]:
            now, span = ad[metric + "Recent"], "last 3 days"
        else:
            now, span = ad[metric], "window"
        bests = [value for value in (ad[metric + "Best"], ad["peak_" + metric]) if value]
        best = max(bests) if bests else None
        if now is not None and best and now <= (1 - rules["fatigueDrop"]) * best:
            tired.append("{} {} ({}) vs best 3 days {}".format(label, pct(now), span, pct(best)))
    reason = losing(ad, rules, be, rules["pullBackRoas"])
    if reason:
        return "pull back", "{}; step down {:.0%}".format(reason, rules["scaleStep"])
    if tired:
        return "fatigue", "; ".join(tired) + "; propose its backup for a test round"
    if payers is None:
        return "hold", "payers unknown; no scale verdict"
    if payers >= rules["scalePayers"] and roas is not None and roas >= rules["scaleRoas"]:
        return "scale", "{:g} payers at projected ROAS {:.2f}; step up {:.0%}".format(
            payers, roas, rules["scaleStep"])
    return "hold", "steady"


def evaluate(config, rows, account_window=False):
    rules = read_rules(config)
    model, warnings = value_model(config)
    be = model["breakEven"]
    ads, combine_warnings = combine(rows, rules)
    warnings += combine_warnings
    measured = [measure(ad, model) for ad in ads]

    assumed = [ad for ad in measured if ad["roleAssumed"]]
    if assumed:
        warnings.insert(0, "Ads with no role: {} of {}. They were judged as test ads, and a winner "
                           "judged that way can only graduate: it never gets scale, fatigue or "
                           "pull-back. Give every row role=test or role=winner.".format(
                               len(assumed), len(measured)))
    tests = [ad for ad in measured if ad["role"] == "test"]
    group_sizes = {}
    for ad in tests:
        group_sizes[ad["group"]] = group_sizes.get(ad["group"], 0) + 1
    unrounded = [ad for ad in tests if ad["round"] is None]
    if unrounded and (account_window or any(group_sizes[ad["group"]] > 4 for ad in unrounded)):
        warnings.append("Test ads with no round: {}. Starvation and the one-graduate limit apply "
                        "per group instead. A group that still holds a previous round's ads, as a 7-day pull "
                        "usually does, is misjudged; add a round column.".format(len(unrounded)))

    # A round is a group plus its round value; without one, the whole group.
    round_spend = {}
    for ad in tests:
        key = (ad["group"], ad["round"])
        round_spend[key] = round_spend.get(key, 0.0) + ad["spend"]
    for ad in measured:
        if ad["role"] == "test":
            ad["verdict"], ad["reason"] = judge_test(ad, round_spend[(ad["group"], ad["round"])], rules, be)
        else:
            ad["verdict"], ad["reason"] = judge_winner(ad, rules, be)

    # A round graduates at most one video: the best projected ROAS in it.
    leaders = {}
    for ad in measured:
        if ad["verdict"] == "graduate":
            key = (ad["group"], ad["round"])
            if key not in leaders or ad["projectedRoas"] > leaders[key]["projectedRoas"]:
                leaders[key] = ad
    for ad in measured:
        leader = leaders.get((ad["group"], ad["round"]))
        if ad["verdict"] == "graduate" and leader is not ad:
            ad["verdict"], ad["reason"] = "hold", "qualifies, but {} leads its round".format(leader["name"])

    summary = summarize(measured, model, rules, account_window)
    if summary.get("governor") == "fired":
        for ad in measured:
            if ad["verdict"] == "scale":
                ad["verdict"] = "hold"
                ad["reason"] = "governor: blended projected ROAS {:.2f} < {:g}".format(
                    summary["projectedRoas"], rules["governorRoas"])
    return {"breakEven": be, "value": model, "rules": rules, "ads": measured,
            "summary": summary, "warnings": warnings}


def summarize(ads, model, rules, account_window):
    spend = sum(ad["spend"] for ad in ads)
    known = [ad for ad in ads if ad["payers"] is not None]
    summary = {"ads": len(ads), "spend": spend, "adsWithPayers": len(known)}
    if known:
        trials = sum(ad["trials"] or 0 for ad in known)
        purchases = sum(ad["purchases"] or 0 for ad in known)
        known_spend = sum(ad["spend"] for ad in known)
        worth = trials * model["perTrial"] + purchases * model["perPurchase"]
        summary.update(trials=trials, purchases=purchases, payers=trials + purchases,
                       costPerPayer=known_spend / (trials + purchases) if trials + purchases else None,
                       projectedRoas=worth / known_spend if known_spend else None)
    if not account_window:
        summary["governor"] = ("not applied (needs every ad over one trailing 7-day window, "
                               "run with --account-window)")
    elif summary.get("projectedRoas") is None or len(known) < len(ads):
        summary["governor"] = "not applied (payers missing for some ads)"
    else:
        summary["governor"] = "fired" if summary["projectedRoas"] < rules["governorRoas"] else "ok"
    return summary


# --- output ---------------------------------------------------------------------------

def money(value):
    return "—" if value is None else "${:,.2f}".format(value)


def pct(value):
    return "—" if value is None else "{:.2%}".format(value)


def count(value):
    return "—" if value is None else "{:g}".format(value)


def render(result, window):
    value, summary = result["value"], result["summary"]
    lines = ["WARNING: " + warning for warning in result["warnings"]]
    if lines:
        lines.append("")
    lines += [
        "Window: {}".format(window or "unstated — name the dates and each source's time zone"),
        "Break-even {} per payer ({} value, {}); spend thresholds are multiples of it.".format(
            money(result["breakEven"]), value["basis"], value["horizon"]),
        "",
        "| Ad | Group (round) | Role | Spend | CTR | 2s hold | Payers (T+P) | $/payer (90% range) | Proj. ROAS | Verdict | Why |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for ad in result["ads"]:
        payers = "—" if ad["payers"] is None else "{} ({}+{})".format(
            count(ad["payers"]), count(ad["trials"] or 0), count(ad["purchases"] or 0))
        cost = money(ad["costPerPayer"])
        if ad["costRange"]:
            low, high = ad["costRange"]
            cost += " ({}–{})".format(money(low), money(high) if high else "∞")
        roas = "—" if ad["projectedRoas"] is None else "{:.2f}".format(ad["projectedRoas"])
        group = ad["group"] + (" ({})".format(ad["round"]) if ad["round"] else "")
        role = ad["role"] + (" (assumed)" if ad["roleAssumed"] else "")
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | **{}** | {} |".format(
            ad["name"], group, role, money(ad["spend"]), pct(ad["ctr"]), pct(ad["hold"]),
            payers, cost, roas, ad["verdict"], ad["reason"]))
    lines.append("")
    blended = ("{} spend, {} payers ({} trials + {} purchases), {} per payer, projected ROAS {}".format(
        money(summary["spend"]), count(summary["payers"]), count(summary["trials"]),
        count(summary["purchases"]), money(summary["costPerPayer"]),
        "—" if summary["projectedRoas"] is None else "{:.2f}".format(summary["projectedRoas"]))
        if "payers" in summary else "{} spend; payers unknown".format(money(summary["spend"])))
    lines.append("All ads in these rows: " + blended)
    lines.append("Governor: " + summary["governor"])
    lines.append("Verdicts are proposals. Nothing changes without the user's explicit yes.")
    return "\n".join(lines)


# --- command line ---------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--name")
    locate_parser = commands.add_parser("locate")
    locate_parser.add_argument("--start")
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--memory")
    evaluate_parser.add_argument("--ads", required=True)
    evaluate_parser.add_argument("--window")
    evaluate_parser.add_argument("--account-window", action="store_true",
                                 help="the rows are every ad in the account over one trailing 7-day window")
    evaluate_parser.add_argument("--json", action="store_true")
    append_parser = commands.add_parser("append")
    append_parser.add_argument("--memory", required=True)
    append_parser.add_argument("--collection", required=True, choices=COLLECTIONS)
    append_parser.add_argument("--file", required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            print(initialize(arguments.project, arguments.name))
        elif arguments.command == "locate":
            print(locate(arguments.start))
        elif arguments.command == "evaluate":
            memory = arguments.memory or locate()
            _, config = validate_memory(memory)
            result = evaluate(config, load_rows(arguments.ads), arguments.account_window)
            if arguments.json:
                print(json.dumps(dict(result, window=arguments.window), indent=2, ensure_ascii=False))
            else:
                print(render(result, arguments.window))
        else:
            print(append(arguments.memory, arguments.collection, read_json(absolute_path(arguments.file))))
    except ArenaError as error:
        print("arena: {}".format(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    # Agents read this through a pipe, which on Windows defaults to the system code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
    sys.exit(main())

from __future__ import annotations

import ast
import difflib
import json
import operator
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "command_log.txt"
NOTES_FILE = BASE_DIR / "notes.txt"
PROFILE_FILE = BASE_DIR / "assistant_profile.json"
ALIASES_FILE = BASE_DIR / "aliases.json"

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I told my computer I needed a break, and it said: no problem, I will go to sleep.",
    "Why did the Python developer wear glasses? Because they could not C.",
]

CHALLENGES = {
    "easy": [
        "Build a function that returns the second largest number from a list.",
        "Write a function to count vowels and consonants in a sentence.",
    ],
    "medium": [
        "Create a mini task scheduler that stores tasks by priority and due date.",
        "Design a text-based expense tracker with category-wise summary.",
    ],
    "hard": [
        "Implement your own tiny autocomplete engine using token frequency.",
        "Build a command replay system that can rerun a selected command history slice.",
    ],
}

MODE_STYLES = {
    "pro": "[Pro Mode]",
    "mentor": "[Mentor Mode]",
    "fun": "[Fun Mode]",
}

INTENT_PATTERNS = {
    "time": ["time", "what time", "current time", "time now"],
    "date": ["date", "what date", "today date", "current date", "what is todays date", "what is today s date"],
    "help": ["help", "commands", "what can you do"],
    "exit": ["exit", "quit", "close", "goodbye", "bye"],
    "joke": ["joke", "funny", "make me laugh"],
    "notes": ["show notes", "list notes", "my notes"],
    "history": ["show history", "command history", "my history"],
    "insights": ["insights", "analytics", "usage stats", "command stats"],
}


class SafeEval(ast.NodeVisitor):
    """Evaluate simple arithmetic expressions safely."""

    ALLOWED_BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    ALLOWED_UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp) -> float:
        op_type = type(node.op)
        if op_type not in self.ALLOWED_BIN_OPS:
            raise ValueError("Unsupported operator.")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self.ALLOWED_BIN_OPS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        op_type = type(node.op)
        if op_type not in self.ALLOWED_UNARY_OPS:
            raise ValueError("Unsupported unary operator.")
        value = self.visit(node.operand)
        return self.ALLOWED_UNARY_OPS[op_type](value)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numbers are allowed.")

    def generic_visit(self, node: ast.AST):
        raise ValueError("Invalid expression.")


@dataclass
class IntentResult:
    command: str
    args: str


def safe_calculate(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    evaluator = SafeEval()
    return evaluator.visit(tree)


def normalize(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())


def read_json_or_default(path: Path, default_value: dict) -> dict:
    if not path.exists():
        return default_value
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_value


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class MiniCLIAssistant:
    def __init__(self) -> None:
        self.history: list[str] = []
        self.aliases: dict[str, str] = read_json_or_default(ALIASES_FILE, {})
        self.profile: dict[str, str] = read_json_or_default(
            PROFILE_FILE, {"developer": "Narendra", "mode": "pro"}
        )

        self.handlers: dict[str, Callable[[str], bool]] = {
            "time": self.handle_time,
            "date": self.handle_date,
            "help": self.handle_help,
            "exit": self.handle_exit,
            "calc": self.handle_calc,
            "joke": self.handle_joke,
            "note": self.handle_note,
            "notes": self.handle_notes,
            "history": self.handle_history,
            "insights": self.handle_insights,
            "mode": self.handle_mode,
            "challenge": self.handle_challenge,
            "alias": self.handle_alias,
            "aliases": self.handle_aliases,
            "profile": self.handle_profile,
            "unknown": self.handle_unknown,
        }

    @property
    def mode_tag(self) -> str:
        return MODE_STYLES.get(self.profile.get("mode", "pro"), "[Pro Mode]")

    def say(self, message: str) -> None:
        print(f"{self.mode_tag} {message}")

    def log_user_command(self, raw_input: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {raw_input}\n")

    def expand_alias(self, user_input: str) -> str:
        parts = user_input.split(maxsplit=1)
        if not parts:
            return user_input

        head = parts[0].lower()
        tail = parts[1] if len(parts) > 1 else ""
        if head not in self.aliases:
            return user_input

        alias_target = self.aliases[head]
        return f"{alias_target} {tail}".strip()

    def detect_intent(self, raw_input: str) -> IntentResult:
        stripped = raw_input.strip()
        if not stripped:
            return IntentResult("unknown", "")

        expanded = self.expand_alias(stripped)
        lowered = expanded.lower()
        parts = expanded.split(maxsplit=1)
        first_word = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        direct_aliases = {
            "time": "time",
            "date": "date",
            "help": "help",
            "exit": "exit",
            "quit": "exit",
            "bye": "exit",
            "calc": "calc",
            "calculate": "calc",
            "joke": "joke",
            "notes": "notes",
            "note": "note",
            "history": "history",
            "insights": "insights",
            "analytics": "insights",
            "mode": "mode",
            "challenge": "challenge",
            "alias": "alias",
            "aliases": "aliases",
            "profile": "profile",
        }
        if first_word in direct_aliases:
            return IntentResult(direct_aliases[first_word], rest)

        if lowered.startswith("calculate "):
            return IntentResult("calc", expanded[10:].strip())

        for prefix in ("add note ", "save note ", "note "):
            if lowered.startswith(prefix):
                return IntentResult("note", expanded[len(prefix) :].strip())

        normalized = normalize(lowered)

        best_command = "unknown"
        best_score = 0.0
        for command, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    return IntentResult(command, "")
                score = difflib.SequenceMatcher(None, normalized, pattern).ratio()
                if score > best_score:
                    best_score = score
                    best_command = command

        if best_score >= 0.72:
            return IntentResult(best_command, "")

        return IntentResult("unknown", expanded)

    def suggest_command(self, bad_input: str) -> str | None:
        known = list(self.handlers.keys())
        guess = difflib.get_close_matches(normalize(bad_input), known, n=1, cutoff=0.6)
        return guess[0] if guess else None

    def handle_time(self, _: str) -> bool:
        self.say(f"Current time: {datetime.now().strftime('%H:%M:%S')}")
        return True

    def handle_date(self, _: str) -> bool:
        self.say(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
        return True

    def handle_help(self, _: str) -> bool:
        print("Available commands:")
        print("  time                   -> show current time")
        print("  date                   -> show current date")
        print("  help                   -> list all commands")
        print("  calc <expression>      -> calculator, e.g. calc 10 / 2 + 3")
        print("  joke                   -> show a random joke")
        print("  note <text>            -> save a note")
        print("  notes                  -> show saved notes")
        print("  history                -> show command history")
        print("  insights               -> show usage analytics")
        print("  mode <pro|mentor|fun>  -> switch assistant personality")
        print("  challenge <level>      -> coding prompt (easy/medium/hard)")
        print("  alias add x=<command>  -> create shortcut")
        print("  alias del x            -> remove shortcut")
        print("  aliases                -> show all shortcuts")
        print("  profile                -> show saved profile")
        print("  exit                   -> close program")
        return True

    def handle_exit(self, _: str) -> bool:
        self.say("Assistant closed. Bye!")
        return False

    def handle_calc(self, args: str) -> bool:
        expression = args.strip() or input("Enter expression: ").strip()
        try:
            result = safe_calculate(expression)
            self.say(f"Result: {result}")
        except Exception as error:
            self.say(f"Could not calculate: {error}")
        return True

    def handle_joke(self, _: str) -> bool:
        self.say(random.choice(JOKES))
        return True

    def handle_note(self, args: str) -> bool:
        note_text = args.strip() or input("Type your note: ").strip()
        if not note_text:
            self.say("Note cannot be empty.")
            return True

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with NOTES_FILE.open("a", encoding="utf-8") as notes_file:
            notes_file.write(f"[{timestamp}] {note_text}\n")
        self.say("Note saved.")
        return True

    def handle_notes(self, _: str) -> bool:
        if not NOTES_FILE.exists() or NOTES_FILE.stat().st_size == 0:
            self.say("No notes saved yet.")
            return True

        print("Saved notes:")
        for line in NOTES_FILE.read_text(encoding="utf-8").splitlines():
            print(f"  {line}")
        return True

    def handle_history(self, _: str) -> bool:
        if not self.history:
            self.say("No commands used yet.")
            return True

        print("Command history:")
        for index, command in enumerate(self.history, start=1):
            print(f"  {index}. {command}")
        return True

    def handle_insights(self, _: str) -> bool:
        if not LOG_FILE.exists() or LOG_FILE.stat().st_size == 0:
            self.say("No logs found yet. Try running a few commands first.")
            return True

        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        commands: list[str] = []
        hours: list[str] = []

        for line in lines:
            if "] " not in line:
                continue
            try:
                stamp_part, command_text = line.split("] ", maxsplit=1)
                stamp_text = stamp_part.replace("[", "", 1)
                stamp = datetime.strptime(stamp_text, "%Y-%m-%d %H:%M:%S")
                hours.append(stamp.strftime("%H"))

                intent = self.detect_intent(command_text)
                commands.append(intent.command)
            except ValueError:
                continue

        if not commands:
            self.say("Could not parse enough data from logs.")
            return True

        cmd_counts = Counter(commands)
        hour_counts = Counter(hours)

        top_command, top_count = cmd_counts.most_common(1)[0]
        peak_hour, peak_hits = hour_counts.most_common(1)[0]

        print("Usage insights:")
        print(f"  Total commands logged : {len(commands)}")
        print(f"  Most used command     : {top_command} ({top_count} times)")
        print(f"  Peak activity hour    : {peak_hour}:00 ({peak_hits} commands)")
        print("  Command distribution  :")
        for command_name, count in cmd_counts.most_common(6):
            print(f"    - {command_name}: {count}")

        return True

    def handle_mode(self, args: str) -> bool:
        selected = args.strip().lower()
        if selected not in MODE_STYLES:
            self.say("Choose one: pro, mentor, fun")
            return True

        self.profile["mode"] = selected
        write_json(PROFILE_FILE, self.profile)
        self.say(f"Mode switched to {selected}.")
        return True

    def handle_challenge(self, args: str) -> bool:
        level = args.strip().lower() or "medium"
        if level not in CHALLENGES:
            self.say("Use challenge easy | medium | hard")
            return True

        prompt = random.choice(CHALLENGES[level])
        self.say(f"{level.title()} challenge: {prompt}")
        return True

    def handle_alias(self, args: str) -> bool:
        action = args.strip()
        if action.startswith("add "):
            payload = action[4:].strip()
            if "=" not in payload:
                self.say("Format: alias add short=<full command>")
                return True

            key, value = payload.split("=", maxsplit=1)
            short = normalize(key)
            target = value.strip()
            if not short or not target:
                self.say("Alias key and value must not be empty.")
                return True

            self.aliases[short] = target
            write_json(ALIASES_FILE, self.aliases)
            self.say(f"Alias saved: {short} -> {target}")
            return True

        if action.startswith("del "):
            short = normalize(action[4:].strip())
            if short not in self.aliases:
                self.say("Alias not found.")
                return True

            del self.aliases[short]
            write_json(ALIASES_FILE, self.aliases)
            self.say(f"Alias deleted: {short}")
            return True

        self.say("Use: alias add x=<command> OR alias del x")
        return True

    def handle_aliases(self, _: str) -> bool:
        if not self.aliases:
            self.say("No aliases saved yet.")
            return True

        print("Saved aliases:")
        for key, value in sorted(self.aliases.items()):
            print(f"  {key} -> {value}")
        return True

    def handle_profile(self, _: str) -> bool:
        print("Profile:")
        print(f"  Developer: {self.profile.get('developer', 'Narendra')}")
        print(f"  Mode     : {self.profile.get('mode', 'pro')}")
        return True

    def handle_unknown(self, args: str) -> bool:
        suggestion = self.suggest_command(args)
        self.say(f"Unknown command: {args}")
        if suggestion:
            self.say(f"Did you mean '{suggestion}'?")
        self.say("Type 'help' to see available commands.")
        return True

    def run(self) -> None:
        print("Mini CLI Assistant - Unique Edition")
        print(f"Developer profile: {self.profile.get('developer', 'Narendra')}")
        print("Type 'help' to see available commands.")

        while True:
            user_input = input("\nYou> ").strip()
            if not user_input:
                continue

            self.history.append(user_input)
            self.log_user_command(user_input)

            intent = self.detect_intent(user_input)
            handler = self.handlers.get(intent.command, self.handle_unknown)
            keep_running = handler(intent.args)
            if not keep_running:
                break


if __name__ == "__main__":
    MiniCLIAssistant().run()

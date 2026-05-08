from __future__ import annotations

import ast
import operator
import random
from datetime import datetime
from pathlib import Path
from typing import Callable

LOG_FILE = Path("command_log.txt")
NOTES_FILE = Path("notes.txt")

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I told my computer I needed a break, and it said: no problem, I will go to sleep.",
    "Why did the Python developer wear glasses? Because they could not C.",
]


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


def safe_calculate(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    evaluator = SafeEval()
    return evaluator.visit(tree)


def log_user_command(raw_input: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] {raw_input}\\n")


def normalize(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(cleaned.split())


def command_from_text(raw_input: str) -> tuple[str, str]:
    stripped = raw_input.strip()
    if not stripped:
        return "", ""

    lowered = stripped.lower()
    parts = stripped.split(maxsplit=1)
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
    }
    if first_word in direct_aliases:
        return direct_aliases[first_word], rest

    normalized = normalize(lowered)

    if any(phrase in normalized for phrase in ("what time", "current time", "time now")):
        return "time", ""
    if any(
        phrase in normalized
        for phrase in (
            "what date",
            "today date",
            "current date",
            "what is todays date",
            "what is today s date",
        )
    ):
        return "date", ""
    if any(phrase in normalized for phrase in ("help", "what can you do", "commands")):
        return "help", ""
    if any(phrase in normalized for phrase in ("exit", "close", "quit", "goodbye")):
        return "exit", ""
    if any(phrase in normalized for phrase in ("joke", "funny", "make me laugh")):
        return "joke", ""
    if any(phrase in normalized for phrase in ("show notes", "list notes", "my notes")):
        return "notes", ""
    if any(phrase in normalized for phrase in ("show history", "command history", "my history")):
        return "history", ""

    for prefix in ("add note ", "save note ", "note "):
        if lowered.startswith(prefix):
            return "note", stripped[len(prefix) :].strip()

    if lowered.startswith("calculate "):
        return "calc", stripped[10:].strip()

    return "unknown", stripped


def handle_time(_: str, __: dict) -> bool:
    print(f"Current time: {datetime.now().strftime('%H:%M:%S')}")
    return True


def handle_date(_: str, __: dict) -> bool:
    print(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
    return True


def handle_help(_: str, __: dict) -> bool:
    print("Available commands:")
    print("  time                -> show current time")
    print("  date                -> show current date")
    print("  help                -> list all commands")
    print("  calc <expression>   -> calculator, e.g. calc 10 / 2 + 3")
    print("  joke                -> show a random joke")
    print("  note <text>         -> save a note")
    print("  notes               -> show saved notes")
    print("  history             -> show command history")
    print("  exit                -> close program")
    return True


def handle_exit(_: str, __: dict) -> bool:
    print("Assistant closed. Bye!")
    return False


def handle_calc(args: str, __: dict) -> bool:
    expression = args.strip()
    if not expression:
        expression = input("Enter expression: ").strip()

    try:
        result = safe_calculate(expression)
        print(f"Result: {result}")
    except Exception as error:
        print(f"Could not calculate: {error}")
    return True


def handle_joke(_: str, __: dict) -> bool:
    print(random.choice(JOKES))
    return True


def handle_note(args: str, __: dict) -> bool:
    note_text = args.strip()
    if not note_text:
        note_text = input("Type your note: ").strip()

    if not note_text:
        print("Note cannot be empty.")
        return True

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with NOTES_FILE.open("a", encoding="utf-8") as notes_file:
        notes_file.write(f"[{timestamp}] {note_text}\\n")
    print("Note saved.")
    return True


def handle_notes(_: str, __: dict) -> bool:
    if not NOTES_FILE.exists() or NOTES_FILE.stat().st_size == 0:
        print("No notes saved yet.")
        return True

    print("Saved notes:")
    for line in NOTES_FILE.read_text(encoding="utf-8").splitlines():
        print(f"  {line}")
    return True


def handle_history(_: str, context: dict) -> bool:
    history = context["history"]
    if not history:
        print("No commands used yet.")
        return True

    print("Command history:")
    for index, cmd in enumerate(history, start=1):
        print(f"  {index}. {cmd}")
    return True


def handle_unknown(args: str, __: dict) -> bool:
    print(f"Unknown command: {args}")
    print("Type 'help' to see available commands.")
    return True


def run_assistant() -> None:
    handlers: dict[str, Callable[[str, dict], bool]] = {
        "time": handle_time,
        "date": handle_date,
        "help": handle_help,
        "exit": handle_exit,
        "calc": handle_calc,
        "joke": handle_joke,
        "note": handle_note,
        "notes": handle_notes,
        "history": handle_history,
        "unknown": handle_unknown,
    }

    context = {"history": []}

    print("Mini CLI Assistant")
    print("Type 'help' to see available commands.")

    while True:
        user_input = input("\\nYou> ").strip()
        if not user_input:
            continue

        context["history"].append(user_input)
        log_user_command(user_input)

        command, args = command_from_text(user_input)
        handler = handlers.get(command, handle_unknown)

        should_continue = handler(args, context)
        if not should_continue:
            break


if __name__ == "__main__":
    run_assistant()

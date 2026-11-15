#!/usr/bin/env python3
"""
Bcrypt Password Auditing Tool
Author: Security Auditor
Purpose: Ethical auditing of bcrypt password hashes (Dictionary & Brute-Force modes)
Platform: Windows / Linux / macOS
"""

import argparse
import itertools
import multiprocessing as mp
import os
import string
import sys
import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class AuditConfig:
    hash_value: bytes
    mode: str  # "dictionary" or "bruteforce"
    wordlist: Optional[str] = None
    charset: str = string.ascii_lowercase + string.digits
    min_len: int = 1
    max_len: int = 4
    workers: Optional[int] = None
    verbose: bool = False


@dataclass
class AuditResult:
    found: bool
    password: Optional[str] = None
    attempts: int = 0
    elapsed: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Hash Utilities
# ---------------------------------------------------------------------------

def parse_bcrypt_hash(hash_str: str) -> bytes:
    """Validate and return bcrypt hash as bytes."""
    hash_str = hash_str.strip()
    if not hash_str.startswith(("$2a$", "$2b$", "$2y$")):
        raise ValueError(
            "Invalid bcrypt hash format. Expected prefix: $2a$, $2b$, or $2y$"
        )
    return hash_str.encode("utf-8")


def extract_cost_factor(hash_bytes: bytes) -> int:
    """Extract the cost factor (rounds) from a bcrypt hash."""
    try:
        parts = hash_bytes.decode("utf-8").split("$")
        return int(parts[2])
    except (IndexError, ValueError):
        return -1


def format_duration(seconds: float) -> str:
    """Human-readable duration."""
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


# ---------------------------------------------------------------------------
# Worker Functions (Multiprocessing)
# ---------------------------------------------------------------------------

def _check_single(args):
    """Worker: test one password candidate."""
    candidate_bytes, hash_bytes = args
    try:
        if bcrypt.checkpw(candidate_bytes, hash_bytes):
            return candidate_bytes
    except ValueError:
        pass
    return None


def _check_chunk(args):
    """Worker: test a chunk of candidates and return the first match."""
    candidates, hash_bytes = args
    for cand in candidates:
        try:
            if bcrypt.checkpw(cand.encode("utf-8"), hash_bytes):
                return cand
        except (ValueError, UnicodeEncodeError):
            continue
    return None


# ---------------------------------------------------------------------------
# Attack Engines
# ---------------------------------------------------------------------------

def run_dictionary_attack(config: AuditConfig) -> AuditResult:
    """Dictionary attack using a wordlist."""
    if not config.wordlist or not os.path.isfile(config.wordlist):
        return AuditResult(found=False, error=f"Wordlist not found: {config.wordlist}")

    try:
        with open(config.wordlist, "r", encoding="utf-8", errors="ignore") as f:
            words = [line.strip() for line in f if line.strip()]
    except OSError as e:
        return AuditResult(found=False, error=f"Cannot read wordlist: {e}")

    total = len(words)
    attempts = 0
    start = time.perf_counter()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TextColumn("• {task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Dictionary Attack", total=total)
        for word in words:
            attempts += 1
            try:
                if bcrypt.checkpw(word.encode("utf-8"), config.hash_value):
                    elapsed = time.perf_counter() - start
                    progress.update(task, advance=1)
                    return AuditResult(
                        found=True,
                        password=word,
                        attempts=attempts,
                        elapsed=elapsed,
                    )
            except (ValueError, UnicodeEncodeError):
                pass
            progress.update(task, advance=1)

    elapsed = time.perf_counter() - start
    return AuditResult(found=False, attempts=attempts, elapsed=elapsed)


def run_bruteforce_attack(config: AuditConfig) -> AuditResult:
    """Brute-force attack using itertools.product with optional multiprocessing."""
    charset = config.charset
    min_len = config.min_len
    max_len = config.max_len
    hash_bytes = config.hash_value

    total_combinations = sum(len(charset) ** l for l in range(min_len, max_len + 1))
    attempts = 0
    start = time.perf_counter()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold magenta]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TextColumn("• {task.completed:,}/{task.total:,}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Brute-Force Attack", total=total_combinations)

        # If multiprocessing is requested and enough work exists
        if config.workers and config.workers > 1 and total_combinations > 1000:
            chunk_size = max(1, total_combinations // (config.workers * 4))
            # Generate all candidates lazily in chunks
            def candidate_chunks():
                chunk = []
                for length in range(min_len, max_len + 1):
                    for tup in itertools.product(charset, repeat=length):
                        chunk.append("".join(tup))
                        if len(chunk) >= chunk_size:
                            yield chunk
                            chunk = []
                if chunk:
                    yield chunk

            with mp.Pool(processes=config.workers) as pool:
                for result in pool.imap_unordered(
                    _check_chunk,
                    ((chunk, hash_bytes) for chunk in candidate_chunks()),
                ):
                    # Update progress roughly (chunk size)
                    progress.update(task, advance=chunk_size)
                    attempts += chunk_size
                    if result is not None:
                        elapsed = time.perf_counter() - start
                        pool.terminate()
                        return AuditResult(
                            found=True,
                            password=result,
                            attempts=attempts,
                            elapsed=elapsed,
                        )
        else:
            # Single-process fallback
            for length in range(min_len, max_len + 1):
                for tup in itertools.product(charset, repeat=length):
                    candidate = "".join(tup)
                    attempts += 1
                    try:
                        if bcrypt.checkpw(candidate.encode("utf-8"), hash_bytes):
                            elapsed = time.perf_counter() - start
                            progress.update(task, advance=1)
                            return AuditResult(
                                found=True,
                                password=candidate,
                                attempts=attempts,
                                elapsed=elapsed,
                            )
                    except (ValueError, UnicodeEncodeError):
                        pass
                    progress.update(task, advance=1)

    elapsed = time.perf_counter() - start
    return AuditResult(found=False, attempts=attempts, elapsed=elapsed)


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def print_banner():
    banner = Text()
    banner.append("╔══════════════════════════════════════════════╗\n", style="bold cyan")
    banner.append("║      BCRYPT PASSWORD AUDITING TOOL           ║\n", style="bold white")
    banner.append("║      Dictionary & Brute-Force Mode           ║\n", style="dim cyan")
    banner.append("╚══════════════════════════════════════════════╝", style="bold cyan")
    console.print(Panel(banner, border_style="bright_blue", expand=False))


def print_summary(config: AuditConfig):
    table = Table(title="Audit Configuration", show_header=False, border_style="dim")
    table.add_column("Property", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Hash", config.hash_value.decode("utf-8")[:60] + "...")
    table.add_row("Mode", config.mode.capitalize())
    cost = extract_cost_factor(config.hash_value)
    table.add_row("Cost Factor", str(cost) if cost > 0 else "N/A")

    if config.mode == "dictionary":
        table.add_row("Wordlist", config.wordlist or "N/A")
    else:
        table.add_row("Charset", config.charset)
        table.add_row("Length Range", f"{config.min_len} – {config.max_len}")
        table.add_row("Workers", str(config.workers or 1))

    console.print(table)


def print_result(result: AuditResult, config: AuditConfig):
    console.print()
    if result.found:
        console.print(
            Panel(
                f"[bold green]✔ PASSWORD FOUND[/bold green]\n\n"
                f"[bold]Password:[/bold] [bold yellow]{result.password}[/bold yellow]\n"
                f"[bold]Attempts:[/bold] {result.attempts:,}\n"
                f"[bold]Time:[/bold] {format_duration(result.elapsed)}",
                title="Audit Result",
                border_style="green",
            )
        )
    elif result.error:
        console.print(
            Panel(
                f"[bold red]✘ ERROR[/bold red]\n\n{result.error}",
                title="Audit Result",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]✘ PASSWORD NOT FOUND[/bold red]\n\n"
                f"[bold]Attempts:[/bold] {result.attempts:,}\n"
                f"[bold]Time:[/bold] {format_duration(result.elapsed)}\n\n"
                f"[dim]Try a larger wordlist or increase length/charset.[/dim]",
                title="Audit Result",
                border_style="yellow",
            )
        )


# ---------------------------------------------------------------------------
# CLI Parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bcrypt Password Auditing Tool – Dictionary & Brute-Force",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dictionary attack
  python auditor.py -H '$2b$12$...' -m dictionary -w words.txt

  # Brute-force attack (lowercase + digits, length 1-4)
  python auditor.py -H '$2b$12$...' -m bruteforce -c 'abcdefghijklmnopqrstuvwxyz0123456789' -l 1 -L 4

  # Brute-force with multiprocessing (4 workers)
  python auditor.py -H '$2b$12$...' -m bruteforce -l 1 -L 5 --workers 4
        """,
    )
    parser.add_argument(
        "-H", "--hash", required=True, help="Bcrypt hash to audit (e.g., $2b$12$...)"
    )
    parser.add_argument(
        "-m", "--mode", choices=["dictionary", "bruteforce"], default="dictionary",
        help="Attack mode (default: dictionary)"
    )
    parser.add_argument(
        "-w", "--wordlist", help="Path to wordlist file (required for dictionary mode)"
    )
    parser.add_argument(
        "-c", "--charset", default=string.ascii_lowercase + string.digits,
        help="Character set for brute-force (default: lowercase + digits)"
    )
    parser.add_argument(
        "-l", "--min-len", type=int, default=1,
        help="Minimum password length for brute-force (default: 1)"
    )
    parser.add_argument(
        "-L", "--max-len", type=int, default=4,
        help="Maximum password length for brute-force (default: 4)"
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Number of worker processes for brute-force (default: CPU count)"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    print_banner()

    # Validate hash
    try:
        hash_bytes = parse_bcrypt_hash(args.hash)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    # Validate mode-specific options
    if args.mode == "dictionary" and not args.wordlist:
        console.print("[bold red]Error:[/bold red] --wordlist is required for dictionary mode.")
        sys.exit(1)

    if args.mode == "bruteforce":
        if args.min_len < 1 or args.max_len < args.min_len:
            console.print("[bold red]Error:[/bold red] Invalid length range.")
            sys.exit(1)

    workers = args.workers
    if args.mode == "bruteforce" and workers is None:
        workers = os.cpu_count() or 1

    config = AuditConfig(
        hash_value=hash_bytes,
        mode=args.mode,
        wordlist=args.wordlist,
        charset=args.charset,
        min_len=args.min_len,
        max_len=args.max_len,
        workers=workers,
        verbose=args.verbose,
    )

    print_summary(config)
    console.print()

    # Run attack
    try:
        if config.mode == "dictionary":
            result = run_dictionary_attack(config)
        else:
            result = run_bruteforce_attack(config)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]⚠ Interrupted by user.[/bold yellow]")
        sys.exit(130)

    print_result(result, config)


if __name__ == "__main__":
    main()

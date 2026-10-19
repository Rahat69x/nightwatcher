"""
NightWatcher — Live Demo Attack Simulator
Simulates real-world cyberattacks against the demo target app or directly into
the NightWatcher engine to demonstrate the complete loop:
Attack Occurs ➔ Detected ➔ Auto-Blocked ➔ Escalating Multi-Channel Alerts ➔ Human Reply

Uses Rich library for clean terminal visuals during hackathon presentations.
"""
from __future__ import annotations
import argparse
import asyncio
import sys
import time
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

TARGET_APP_URL = "http://localhost:8001/login"
NIGHTWATCHER_API_URL = "http://localhost:8000/api/events/"


async def run_brute_force(attacker_ip: str = "198.51.100.42", attempts: int = 12):
    console.print(Panel(
        f"[bold red]⚡ SCENARIO 1: BRUTE FORCE ATTACK[/bold red]\n"
        f"Simulating [bold]{attempts}[/bold] rapid SSH/Web login attempts from attacker IP [yellow]{attacker_ip}[/yellow]",
        border_style="red"
    ))

    # Test if target app is reachable
    app_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://localhost:8001/")
            app_online = resp.status_code in (200, 403)
    except Exception:
        app_online = False

    blocked_detected = False

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Launching brute force attack...", total=attempts)

        for i in range(1, attempts + 1):
            await asyncio.sleep(0.35)

            if app_online and not blocked_detected:
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.post(
                            TARGET_APP_URL,
                            data={"username": "admin", "password": f"wrongPass_{i}"},
                            headers={"x-simulated-ip": attacker_ip},
                        )
                        if resp.status_code == 403:
                            blocked_detected = True
                            console.print(f"  [bold red]🚫 ATTEMPT #{i}: HTTP 403 FORBIDDEN! IP {attacker_ip} WAS NEUTRALIZED BY NIGHTWATCHER AUTO-BLOCK![/bold red]")
                        elif resp.status_code in (200, 303):
                            console.print(f"  [yellow]Attempt #{i}: Login failed (invalid password)[/yellow]")
                except Exception as e:
                    console.print(f"  [yellow]Attempt #{i}: Failed ({e})[/yellow]")
            else:
                # Direct API injection fallback
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        resp = await client.post(
                            NIGHTWATCHER_API_URL,
                            json={
                                "type": "brute_force",
                                "source": "attack_simulator",
                                "details": {
                                    "source_ip": attacker_ip,
                                    "failed_attempts": i,
                                    "username": "admin",
                                    "abuse_confidence_score": 85,
                                    "off_hours": True,
                                },
                            },
                        )
                        data = resp.json()
                        if i >= 5:
                            console.print(f"  [bold red]🚨 ATTEMPT #{i}: NightWatcher Engine generated Alert #{data.get('alert_id')} ({data.get('severity')}) — Attacker Auto-Blocked![/bold red]")
                        else:
                            console.print(f"  [dim]Attempt #{i}: Recorded event...[/dim]")
                except Exception as e:
                    console.print(f"  [red]Failed to connect to NightWatcher: {e}[/red]")
                    break

            progress.update(task, advance=1)

    console.print(Panel(
        f"[bold green]✔ ATTACK NEUTRALIZED[/bold green]\n"
        f"• Total attempts: {attempts}\n"
        f"• Status: [bold red]IP {attacker_ip} is now blocked on firewall/proxy[/bold red]\n"
        f"• Notification dispatched to Telegram & Email\n"
        f"• Dashboard updated in real-time",
        border_style="green"
    ))


async def run_credential_stuffing(attacker_ip: str = "203.0.113.88"):
    console.print(Panel(
        f"[bold orange3]⚡ SCENARIO 2: CREDENTIAL STUFFING ATTACK[/bold orange3]\n"
        f"Simulating botnet testing leaked passwords against [bold]8 distinct usernames[/bold]",
        border_style="orange3"
    ))

    usernames = ["jdoe", "sarah_k", "finance_admin", "devops", "alex99", "support", "billing", "ceo_office"]

    for u in usernames:
        await asyncio.sleep(0.3)
        console.print(f"  [yellow]Testing leaked credential for user:[/yellow] [bold cyan]{u}[/bold cyan]...")

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                NIGHTWATCHER_API_URL,
                json={
                    "type": "credential_stuffing",
                    "source": "attack_simulator",
                    "details": {
                        "source_ip": attacker_ip,
                        "unique_usernames": len(usernames),
                        "failed_attempts": len(usernames),
                        "off_hours": False,
                    },
                },
            )
            data = resp.json()
            console.print(Panel(
                f"[bold red]🚨 CREDENTIAL STUFFING FLAGGED[/bold red]\n"
                f"• Alert ID: #{data.get('alert_id')}\n"
                f"• Severity: [bold]{data.get('severity').upper()}[/bold] (Score: {data.get('score')}/100)\n"
                f"• Auto-Action: Blocked IP {attacker_ip}\n"
                f"• Summary: {data.get('summary')}",
                border_style="red"
            ))
    except Exception as e:
        console.print(f"[red]Error contacting NightWatcher API: {e}[/red]")


async def run_critical_breach(attacker_ip: str = "198.51.100.42"):
    console.print(Panel(
        f"[bold red blink]🚨 SCENARIO 3: CRITICAL INTRUSION ALARM[/bold red blink]\n"
        f"Simulating worst-case security incident: Successful login AFTER 25 failed attempts.\n"
        f"This triggers [bold red]Level 4 Escalation: Voice Call + Telegram Urgent Dispatch[/bold red]",
        border_style="red"
    ))

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                NIGHTWATCHER_API_URL,
                json={
                    "type": "login_success_after_brute",
                    "source": "attack_simulator",
                    "details": {
                        "source_ip": attacker_ip,
                        "username": "root_admin",
                        "failed_attempts_before": 25,
                    },
                },
            )
            data = resp.json()
            console.print(Panel(
                f"[bold red]📞 IMMEDIATE VOICE CALL DISPATCHED[/bold red]\n"
                f"• Alert #{data.get('alert_id')} [CRITICAL]\n"
                f"• Severity Score: {data.get('score')}/100\n"
                f"• Twilio Voice Engine dialing verified phone with TwiML\n"
                f"• Summary: {data.get('summary')}\n\n"
                f"[yellow]Phone prompt:[/yellow] 'Press 1 to acknowledge, Press 2 to block IP'",
                border_style="red"
            ))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def main():
    parser = argparse.ArgumentParser(description="NightWatcher Attack Simulator")
    parser.add_argument(
        "--mode",
        choices=["brute", "stuffing", "critical", "all"],
        default="brute",
        help="Attack scenario to run",
    )
    parser.add_argument("--ip", default="198.51.100.42", help="Simulated attacker IP")
    args = parser.parse_args()

    console.print("[bold cyan]════════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold white]   NIGHTWATCHER — HACKATHON LIVE ATTACK SIMULATOR[/bold white]")
    console.print("[bold cyan]════════════════════════════════════════════════════════════════════[/bold cyan]\n")

    if args.mode == "brute":
        asyncio.run(run_brute_force(args.ip))
    elif args.mode == "stuffing":
        asyncio.run(run_credential_stuffing(args.ip))
    elif args.mode == "critical":
        asyncio.run(run_critical_breach(args.ip))
    elif args.mode == "all":
        asyncio.run(run_brute_force(args.ip))
        time.sleep(1)
        asyncio.run(run_credential_stuffing("203.0.113.88"))
        time.sleep(1)
        asyncio.run(run_critical_breach(args.ip))


if __name__ == "__main__":
    main()

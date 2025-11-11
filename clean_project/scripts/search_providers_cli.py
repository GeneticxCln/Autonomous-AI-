#!/usr/bin/env python3
from __future__ import annotations

"""
Admin CLI for managing web search provider configuration.

Examples:
  # Show current config and status
  python clean_project/scripts/search_providers_cli.py --show

  # Set provider order
  python clean_project/scripts/search_providers_cli.py --set-order serpapi,bing,google

  # Disable providers
  python clean_project/scripts/search_providers_cli.py --disable google

  # Interactive mode
  python clean_project/scripts/search_providers_cli.py --interactive
"""

import argparse
import os
import sys
from typing import List


def ensure_sys_path() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, ".."))
    src_dir = os.path.join(project_root, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def _print_status() -> None:
    from agent_system.unified_config import unified_config
    from agent_system.config_simple import get_api_key

    order = unified_config.api.search_provider_order or ["serpapi", "bing", "google"]
    disabled = unified_config.api.disabled_search_providers or []
    configured = unified_config.get_configured_providers()
    enabled = [p for p in configured if p not in disabled and p in ("serpapi", "bing", "google")]
    keys_present = {p: bool(get_api_key(p)) for p in ("serpapi", "bing", "google")}
    google_cse_configured = bool(
        (os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_SEARCH_CX") or "").strip()
    )

    print("Current provider configuration:")
    print(f"  Order:      {', '.join(order)}")
    print(f"  Disabled:   {', '.join(disabled) if disabled else '(none)'}")
    print(f"  Configured: {', '.join(configured) if configured else '(none)'}")
    print(f"  Enabled:    {', '.join(enabled) if enabled else '(none)'}")
    print(f"  Keys:       {keys_present}")
    print(f"  Google CSE: {'configured' if google_cse_configured else 'missing'}")


def _persist(order: List[str], disabled: List[str]) -> None:
    from agent_system.unified_config import unified_config

    unified_config.api.search_provider_order = order
    unified_config.api.disabled_search_providers = disabled
    unified_config.save_to_file()


def main() -> int:
    ensure_sys_path()

    parser = argparse.ArgumentParser(description="Manage search provider configuration")
    parser.add_argument("--show", action="store_true", help="Show current configuration")
    parser.add_argument("--set-order", help="Comma-separated provider order (serpapi,bing,google)")
    parser.add_argument("--disable", help="Comma-separated providers to disable")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    if args.show and not (args.set_order or args.disable or args.interactive):
        _print_status()
        return 0

    if args.interactive:
        _print_status()
        print("")
        new_order = input(
            "Enter provider order (comma-separated; default serpapi,bing,google): "
        ).strip() or "serpapi,bing,google"
        new_disabled = input("Disable providers (comma-separated or blank): ").strip() or ""
        order = [p.strip().lower() for p in new_order.split(",") if p.strip()]
        disabled = [p.strip().lower() for p in new_disabled.split(",") if p.strip()]
        _persist(order, disabled)
        print("\n✅ Updated provider configuration")
        _print_status()
        return 0

    order = None
    disabled = None
    if args.set_order:
        order = [p.strip().lower() for p in args.set_order.split(",") if p.strip()]
    if args.disable:
        disabled = [p.strip().lower() for p in args.disable.split(",") if p.strip()]

    if order is None and disabled is None:
        parser.print_help()
        return 1

    from agent_system.unified_config import unified_config

    effective_order = order or list(
        unified_config.api.search_provider_order or ["serpapi", "bing", "google"]
    )
    effective_disabled = disabled or list(unified_config.api.disabled_search_providers or [])
    _persist(effective_order, effective_disabled)
    print("✅ Updated provider configuration")
    _print_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


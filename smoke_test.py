"""Execute exactly one skill through an already running IRSEN bridge."""

import json
import sys

from irsen_client import IrsenClient, IrsenError, IrsenProtocolError


def show(label, value):
    print(f"\n{label}:", flush=True)
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def main():
    client = IrsenClient()
    try:
        client.connect()
        show("Ping", client.ping())
        before = client.get_combat_state()
        show("Before", before)
        if not isinstance(before, dict):
            raise IrsenProtocolError("Combat state must be a JSON object.")
        if before.get("error"):
            raise IrsenProtocolError(f"Combat unavailable: {before['error']}")
        if not isinstance(before.get("player"), dict) or not before["player"]:
            raise IrsenProtocolError("No active combat/player in combat state.")
        if before.get("combat_finished") is True:
            raise IrsenProtocolError("Combat has already finished.")
        if before.get("ready") is not True:
            raise IrsenProtocolError(
                "Combat is not ready. Enter combat and wait for the player turn.")

        actions = client.get_available_actions()
        show("Available actions", actions)
        if not isinstance(actions, list) or any(
                not isinstance(action, dict) for action in actions):
            raise IrsenProtocolError("Available actions must be a list of objects.")
        selected = next((action for action in actions
                         if action.get("type") == "skill"), None)
        if selected is None:
            raise IrsenProtocolError("No available skill action.")
        action_id = selected.get("action_id")
        if not isinstance(action_id, str) or not action_id:
            raise IrsenProtocolError("Selected skill lacks a valid action_id.")
        show("Selected action", selected)
        print("\nWaiting for action completion (up to 120s)...", flush=True)
        result = client.perform_action(action_id)
        show("Result", result)
        show("After", client.get_combat_state())
        return 0
    except IrsenError as exc:
        print(f"\nSmoke test failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

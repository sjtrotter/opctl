import argparse
from .manager import OpManager

def main():
    parser = argparse.ArgumentParser(prog="opctl")
    subparsers = parser.add_subparsers(dest="command")

    # Status / Show
    subparsers.add_parser("status")
    subparsers.add_parser("show-final")

    # Configuration Verbs
    set_host = subparsers.add_parser("set-hostname")
    set_host.add_argument("name")

    add_target = subparsers.add_parser("add-target")
    add_target.add_argument("range")

    # The Action
    subparsers.add_parser("commit")

    args = parser.parse_args()
    mgr = OpManager()

    if args.command == "set-hostname":
        mgr.state["hostname"] = args.name
        mgr.save_state()
    elif args.command == "add-target":
        mgr.state["targets"].append(args.range)
        mgr.save_state()
    elif args.command == "commit":
        mgr.commit()
    # ... more commands ...

if __name__ == "__main__":
    main()
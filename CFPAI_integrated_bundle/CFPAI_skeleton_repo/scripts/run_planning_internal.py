"""运行 CFPAI 规划。"""
import argparse
from cfpai.service.planning_service import run_planning_service


def main():
    parser = argparse.ArgumentParser(description="CFPAI Planning")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    result = run_planning_service(
        symbols=args.symbols, start=args.start, end=args.end, out_folder=args.out,
    )
    print(f"Status: {result['status']}")
    print(f"Run dir: {result['run_dir']}")
    if "planning" in result:
        print(f"Market label: {result['planning'].get('market_label')}")
        print(f"Actions: {result['planning'].get('actions')}")


if __name__ == "__main__":
    main()

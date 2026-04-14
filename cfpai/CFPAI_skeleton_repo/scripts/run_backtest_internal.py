"""运行 CFPAI 回测。"""
import argparse
from cfpai.service.backtest_service import run_backtest_service


def main():
    parser = argparse.ArgumentParser(description="CFPAI Backtest")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--utm", action="store_true", help="use UTM auto-tuning")
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    result = run_backtest_service(
        symbols=args.symbols, start=args.start, end=args.end,
        use_utm=args.utm, out_folder=args.out,
    )
    print(f"Status: {result['status']}")
    print(f"Run dir: {result['run_dir']}")
    if "stats" in result:
        for k, v in result["stats"].items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

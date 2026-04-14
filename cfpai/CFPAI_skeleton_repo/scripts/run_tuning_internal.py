"""运行 CFPAI UTM 调参。"""
import argparse
from cfpai.service.tuning_service import run_tuning_service


def main():
    parser = argparse.ArgumentParser(description="CFPAI UTM Tuning")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--generations", type=int, default=6)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    result = run_tuning_service(
        symbols=args.symbols, start=args.start, end=args.end,
        generations=args.generations, population=args.population, out_folder=args.out,
    )
    print(f"Status: {result['status']}")
    print(f"Run dir: {result['run_dir']}")
    if "best_params" in result:
        print(f"Best params: {result['best_params']}")


if __name__ == "__main__":
    main()

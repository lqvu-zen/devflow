import sys

from tally import core


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    numbers = [float(a) for a in args]
    print(f"total={core.total(numbers)} average={core.average(numbers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

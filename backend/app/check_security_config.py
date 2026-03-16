import argparse
import sys

from app.core.config import GOVERNED_SECRET_FIELDS, Settings, collect_secret_issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate governed secrets and default-key policy",
    )
    parser.add_argument(
        "--mode",
        choices=("warn", "strict"),
        default="warn",
        help="warn prints findings but exits 0, strict exits non-zero on findings",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = Settings()
    issues = collect_secret_issues(settings, strict=args.mode == "strict")

    print(f"[security-gate] environment={settings.ENVIRONMENT}")
    print("[security-gate] governed fields=" + ", ".join(GOVERNED_SECRET_FIELDS))

    if not issues:
        print("[security-gate] no insecure governed secrets detected")
        return 0

    for issue in issues:
        print(f"[security-gate] issue: {issue}")

    if args.mode == "warn":
        print("[security-gate] warn mode: continue with findings")
        return 0

    print("[security-gate] strict mode: failing due to governed secret findings")
    return 1


if __name__ == "__main__":
    sys.exit(main())

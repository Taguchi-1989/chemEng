"""Check pip-audit output against known/accepted advisories."""

import sys

# Known/accepted vulnerabilities — add GHSA IDs here after review
KNOWN_ADVISORIES = {
    "GHSA-67mh-4wv8-2f99",  # accepted: low-risk, no fix available
    "GHSA-4w7w-66w2-5vf9",  # vite path traversal — not applicable (Python project)
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_known.py <audit-output-file>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        output = f.read()

    unknown = []
    known = []

    for line in output.splitlines():
        is_known = False
        for ghsa in KNOWN_ADVISORIES:
            if ghsa in line:
                known.append(line.strip())
                is_known = True
                break
        # Lines containing GHSA that are not known
        if not is_known and "GHSA-" in line:
            unknown.append(line.strip())

    if known:
        print(f"Known (accepted): {len(known)}")
        for k in known:
            print(f"  \u26a0\ufe0f  {k}")
        print()

    if unknown:
        print(f"\u274c {len(unknown)} unknown vulnerabilities found:")
        for u in unknown:
            print(f"  {u}")
        print()
        print("Please review and either:")
        print("  1. Fix the vulnerability (upgrade the package)")
        print("  2. Add to known list in scripts/audit/check_known.py")
        sys.exit(1)
    else:
        print("\u2705 All vulnerabilities are known/accepted.")


if __name__ == "__main__":
    main()

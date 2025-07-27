import sys

REQUIRED_SECTIONS = [
    "<One line description>",
    "Description of problem:",
    "Description of solution:",
    "Testing done:",
    "Closes:",
]

def main():
    if len(sys.argv) < 2:
        print("Usage: check_pr_description.py <pr_body_file>")
        sys.exit(1)
    with open(sys.argv[1], "r") as f:
        body = f.read()
    missing = [section for section in REQUIRED_SECTIONS if section not in body]
    if missing:
        print(f"PR description is missing required sections: {missing}")
        sys.exit(1)
    print("PR description format check passed.")

if __name__ == "__main__":
    main()

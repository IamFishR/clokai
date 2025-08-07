def patch_file(path, edits):
    with open(path, "r") as f:
        lines = f.readlines()
    for edit in edits:
        start = edit["start_line"]
        end = edit["end_line"]
        replacement = edit["replacement"]
        lines[start:end] = [line + "\n" for line in replacement]
    with open(path, "w") as f:
        f.writelines(lines)
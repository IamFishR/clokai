def chunk_file_by_lines(file_path, chunk_size=100):
    with open(file_path, "r") as f:
        lines = f.readlines()
    return [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
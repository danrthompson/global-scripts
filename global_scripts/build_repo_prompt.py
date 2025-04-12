import os
import tiktoken
from pathlib import Path
from xml.sax.saxutils import escape

# --- Configuration: Ignore rules ---
IGNORE_DIRS = {".git", "__pycache__", ".vscode"}
IGNORE_FILES_SUFFIX = {".pyc"}
IGNORE_FILES_NAMES = {"repo-contents.xml", ".DS_Store"}  # Also ignore output file
BINARY_FILE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".tar", ".gz"}

# --- Utility Functions ---


def get_token_count(text: str) -> int:
    """
    Return the token count for a given text based on target model encoding.
    """
    try:
        # Use encoding suitable for your target model.
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    except Exception:
        encoding = tiktoken.get_encoding("gpt2")
    return len(encoding.encode(text))


def format_size(num_bytes: int) -> str:
    """
    Format a byte count as a human-readable string.
    """
    if num_bytes < 1024:
        return f"{num_bytes} B"
    return f"{num_bytes / 1024:.1f} KB"


def prompt_choice(prompt: str, valid_choices: set[str]) -> str:
    """
    Prompt until the user inputs one of the valid choices (lowercase letters).
    Acceptable choices: e.g., {'y', 'n', 'o'}.
    """
    while True:
        choice = input(prompt).strip().lower()
        if choice in valid_choices:
            return choice
        print(f"Invalid choice. Please enter one of {', '.join(valid_choices)}.")


def is_probably_binary(file_path: Path) -> bool:
    """
    Check if a file is likely binary based on extension or content.
    """
    # Check file extension
    ext = file_path.suffix.lower()
    if ext in BINARY_FILE_EXTENSIONS:
        return True

    # Try to read a small chunk to detect binary content
    try:
        with file_path.open("rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk  # Null bytes usually indicate binary
    except Exception:
        return True  # If we can't read it, treat as binary to be safe

    return False


# --- Core Interactive Function ---


def process_directory(
    directory: Path, relative_path: Path = Path(""), included_files: list[dict] | None = None
) -> list[dict]:
    """
    Recursively process a directory:
      - List files (with details) and prompt: Yes (y), No (n), or One-by-one (o).
      - Then lists subdirectories and prompts similarly.

    Returns: List of included file information
    """
    if included_files is None:
        included_files = []

    try:
        entries = sorted(
            p for p in directory.iterdir() if not (p.is_dir() and p.name in IGNORE_DIRS or p.name.startswith("."))
        )
    except Exception as e:
        print(f"Error reading directory {directory}: {e}")
        return included_files

    files = []
    dirs = []
    for entry in entries:
        if entry.is_dir():
            if entry.name in IGNORE_DIRS or entry.name.startswith("."):
                continue
            dirs.append(entry)
        elif entry.is_file():
            if (
                entry.name in IGNORE_FILES_NAMES
                or any(entry.name.endswith(suffix) for suffix in IGNORE_FILES_SUFFIX)
                or entry.name.startswith(".")
            ):
                continue
            files.append(entry)

    # --- Process Files ---
    if files:
        rel_path_str = str(relative_path) or "."
        print(f"\nFiles in '{rel_path_str}':")
        file_info_list = []
        for file_path in files:
            size_str = ""  # Initialize to handle potential missing assignment
            try:
                size_bytes = file_path.stat().st_size
                size_str = format_size(size_bytes)

                # Check if file is binary
                if is_probably_binary(file_path):
                    print(f"  - {file_path.name}: {size_str} (binary file, will be skipped)")
                    continue

                with file_path.open("r", encoding="utf-8") as f:
                    content = f.read()
                char_count = len(content)
                token_count = get_token_count(content)
            except UnicodeDecodeError:
                print(f"  - {file_path.name}: {size_str} (binary or non-UTF-8 file, will be skipped)")
                continue
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                continue
            print(f"  - {file_path.name}: {size_str}, {char_count} chars, ~{token_count} tokens")
            file_info_list.append((file_path, content, char_count, token_count, size_str))

        file_choice = prompt_choice(
            f"Include files in '{rel_path_str}'? (Y=all, N=none, O=one-by-one): ", {"y", "n", "o"}
        )
        if file_choice == "y":
            for file_path, content, char_count, token_count, _ in file_info_list:
                if char_count == 0:  # Skip empty files
                    continue
                file_rel_path = relative_path / file_path.name if relative_path else Path(file_path.name)
                included_files.append(
                    {
                        "path": str(file_rel_path).replace(os.sep, "/"),
                        "content": content,
                        "char_count": char_count,
                        "token_count": token_count,
                    }
                )
        elif file_choice == "o":
            for file_path, content, char_count, token_count, size_str in file_info_list:
                prompt_file = (
                    f"Include '{file_path.name}' ({size_str}, {char_count} chars, ~{token_count} tokens)? (y/n): "
                )
                sub_choice = prompt_choice(prompt_file, {"y", "n"})
                if sub_choice == "y":
                    if char_count == 0:
                        continue
                    file_rel_path = relative_path / file_path.name if relative_path else Path(file_path.name)
                    included_files.append(
                        {
                            "path": str(file_rel_path).replace(os.sep, "/"),
                            "content": content,
                            "char_count": char_count,
                            "token_count": token_count,
                        }
                    )
        # 'n' leads to skipping files

    # --- Process Directories ---
    if dirs:
        rel_path_str = str(relative_path) or "."
        print(f"\nDirectories in '{rel_path_str}':")
        for dir_path in dirs:
            print(f"  - {dir_path.name}")
        dir_choice = prompt_choice(
            f"Include directories in '{rel_path_str}'? (Y=all, N=none, O=one-by-one): ", {"y", "n", "o"}
        )
        if dir_choice == "y":
            for dir_path in dirs:
                new_rel_path = relative_path / dir_path.name if relative_path else Path(dir_path.name)
                process_directory(dir_path, new_rel_path, included_files)
        elif dir_choice == "o":
            for dir_path in dirs:
                sub_choice = prompt_choice(f"Include directory '{dir_path.name}'? (y/n): ", {"y", "n"})
                if sub_choice == "y":
                    new_rel_path = relative_path / dir_path.name if relative_path else Path(dir_path.name)
                    process_directory(dir_path, new_rel_path, included_files)
        # 'n' leads to skipping directories

    return included_files


# --- XML Generation ---


def generate_xml(included_files: list[dict], repo_name: str | None = None) -> str:
    """
    Generate an XML representation of the selected files.
    """
    # Use the current directory's name as the repository name if not provided
    if repo_name is None:
        repo_name = Path.cwd().name

    # Escape XML special characters in the repo name
    repo_name = escape(repo_name)

    xml_lines = []
    xml_lines.append(f'<repo name="{repo_name}">')

    # Index: directory structure with included file paths.
    xml_lines.append("  <directory structure>")
    for file_info in included_files:
        xml_lines.append(f"    /{file_info['path']}")
    xml_lines.append("  </directory>\n")

    # File entries with XML-escaped content.
    for file_info in included_files:
        escaped_path = escape(file_info["path"])
        escaped_content = escape(file_info["content"])
        xml_lines.append(f'  <file path="{escaped_path}">')
        xml_lines.append(f"    {escaped_content}")
        xml_lines.append("  </file>\n")
    xml_lines.append("</repo>")

    return "\n".join(xml_lines)


# --- CLI Entry Point ---


def main(output_file: str = "repo-contents.xml", start_dir: str | None = None) -> None:
    """
    Entry point for the 'build-repo-prompt' CLI tool.

    Args:
        output_file: Name of the output XML file
        start_dir: Directory to start processing from (defaults to current directory)
    """
    print("Interactive Repository XML Builder")
    print("====================================")

    # Begin processing at the specified directory or current working directory
    start_directory = Path(start_dir) if start_dir else Path.cwd()
    included_files = process_directory(start_directory)

    # Show summary totals.
    total_chars = sum(f["char_count"] for f in included_files)
    total_tokens = sum(f["token_count"] for f in included_files)
    print("\nSummary:")
    print(f"  Total included files: {len(included_files)}")
    print(f"  Total characters: {total_chars}")
    print(f"  Total tokens: {total_tokens}")

    # Generate and write XML output.
    xml_content = generate_xml(included_files)
    try:
        # Create output path
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = start_directory / output_path

        with output_path.open("w", encoding="utf-8") as f:
            f.write(xml_content)
        print(f"\nXML output written to '{output_path}'.")
    except Exception as e:
        print(f"Error writing XML file: {e}")


if __name__ == "__main__":
    main()

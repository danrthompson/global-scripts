import os
import tiktoken
from xml.sax.saxutils import escape

# --- Configuration: Ignore rules ---
IGNORE_DIRS = {".git", "__pycache__", ".vscode"}
IGNORE_FILES_SUFFIX = {".pyc"}
IGNORE_FILES_NAMES = {"repo-contents.xml", ".DS_Store"}  # Also ignore output file

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


def prompt_choice(prompt: str, valid_choices: set) -> str:
    """
    Prompt until the user inputs one of the valid choices (lowercase letters).
    Acceptable choices: e.g., {'y', 'n', 'o'}.
    """
    while True:
        choice = input(prompt).strip().lower()
        if choice in valid_choices:
            return choice
        print(f"Invalid choice. Please enter one of {', '.join(valid_choices)}.")


# --- Global list to accumulate selected files ---
# Each entry is a dict with keys: 'path', 'content', 'char_count', 'token_count'
included_files = []

# --- Core Interactive Function ---


def process_directory(directory: str, relative_path: str = "") -> None:
    """
    Recursively process a directory:
      - List files (with details) and prompt: Yes (y), No (n), or One-by-one (o).
      - Then lists subdirectories and prompts similarly.
    """
    try:
        entries = os.listdir(directory)
    except Exception as e:
        print(f"Error reading directory {directory}: {e}")
        return

    files = []
    dirs = []
    for entry in sorted(entries):
        full_path = os.path.join(directory, entry)
        if os.path.isdir(full_path):
            if entry in IGNORE_DIRS or entry.startswith("."):
                continue
            dirs.append(entry)
        elif os.path.isfile(full_path):
            if (
                entry in IGNORE_FILES_NAMES
                or any(entry.endswith(suffix) for suffix in IGNORE_FILES_SUFFIX)
                or entry.startswith(".")
            ):
                continue
            files.append(entry)

    # --- Process Files ---
    if files:
        print(f"\nFiles in '{relative_path or '.'}':")
        file_info_list = []
        for file in files:
            full_path = os.path.join(directory, file)
            try:
                size_bytes = os.path.getsize(full_path)
                size_str = format_size(size_bytes)
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                char_count = len(content)
                token_count = get_token_count(content)
            except Exception as e:
                print(f"Error reading file {full_path}: {e}")
                continue
            print(f"  - {file}: {size_str}, {char_count} chars, ~{token_count} tokens")
            file_info_list.append((file, content, char_count, token_count, size_str))

        file_choice = prompt_choice(
            f"Include files in '{relative_path or '.'}'? (Y=all, N=none, O=one-by-one): ", {"y", "n", "o"}
        )
        if file_choice == "y":
            for file, content, char_count, token_count, _ in file_info_list:
                if char_count == 0:  # Skip empty files
                    continue
                file_rel_path = os.path.join(relative_path, file) if relative_path else file
                included_files.append(
                    {
                        "path": file_rel_path.replace(os.sep, "/"),
                        "content": content,
                        "char_count": char_count,
                        "token_count": token_count,
                    }
                )
        elif file_choice == "o":
            for file, content, char_count, token_count, size_str in file_info_list:
                prompt_file = f"Include '{file}' ({size_str}, {char_count} chars, ~{token_count} tokens)? (y/n): "
                sub_choice = prompt_choice(prompt_file, {"y", "n"})
                if sub_choice == "y":
                    if char_count == 0:
                        continue
                    file_rel_path = os.path.join(relative_path, file) if relative_path else file
                    included_files.append(
                        {
                            "path": file_rel_path.replace(os.sep, "/"),
                            "content": content,
                            "char_count": char_count,
                            "token_count": token_count,
                        }
                    )
        # 'n' leads to skipping files

    # --- Process Directories ---
    if dirs:
        print(f"\nDirectories in '{relative_path or '.'}':")
        for dir_name in dirs:
            print(f"  - {dir_name}")
        dir_choice = prompt_choice(
            f"Include directories in '{relative_path or '.'}'? (Y=all, N=none, O=one-by-one): ", {"y", "n", "o"}
        )
        if dir_choice == "y":
            for dir_name in dirs:
                new_rel_path = os.path.join(relative_path, dir_name) if relative_path else dir_name
                process_directory(os.path.join(directory, dir_name), new_rel_path)
        elif dir_choice == "o":
            for dir_name in dirs:
                sub_choice = prompt_choice(f"Include directory '{dir_name}'? (y/n): ", {"y", "n"})
                if sub_choice == "y":
                    new_rel_path = os.path.join(relative_path, dir_name) if relative_path else dir_name
                    process_directory(os.path.join(directory, dir_name), new_rel_path)
        # 'n' leads to skipping directories


# --- XML Generation ---


def generate_xml() -> str:
    """
    Generate an XML representation of the selected files.
    """
    # Use the current directory's name as the repository name.
    repo_name = os.path.basename(os.getcwd())
    xml_lines = []
    xml_lines.append(f'<repo name="{repo_name}">')

    # Index: directory structure with included file paths.
    xml_lines.append("  <directory structure>")
    for file_info in included_files:
        xml_lines.append(f"    /{file_info['path']}")
    xml_lines.append("  </directory>\n")

    # File entries with XML-escaped content.
    for file_info in included_files:
        escaped_content = escape(file_info["content"])
        xml_lines.append(f'  <file path="{file_info["path"]}">')
        xml_lines.append(f"    {escaped_content}")
        xml_lines.append("  </file>\n")
    xml_lines.append("</repo>")

    return "\n".join(xml_lines)


# --- CLI Entry Point ---


def main() -> None:
    """
    Entry point for the 'build-repo-prompt' CLI tool.
    """
    print("Interactive Repository XML Builder")
    print("====================================")

    # Begin processing at the current working directory.
    process_directory(os.getcwd(), "")

    # Show summary totals.
    total_chars = sum(f["char_count"] for f in included_files)
    total_tokens = sum(f["token_count"] for f in included_files)
    print("\nSummary:")
    print(f"  Total included files: {len(included_files)}")
    print(f"  Total characters: {total_chars}")
    print(f"  Total tokens: {total_tokens}")

    # Generate and write XML output.
    xml_content = generate_xml()
    output_file = "repo-contents.xml"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(xml_content)
        print(f"\nXML output written to '{output_file}'.")
    except Exception as e:
        print(f"Error writing XML file: {e}")


if __name__ == "__main__":
    main()

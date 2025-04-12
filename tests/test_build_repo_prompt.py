from pathlib import Path

import pytest

# Import the main function and reset any global state for testing
from global_scripts.build_repo_prompt import main

@pytest.fixture
def complex_temp_repo(tmp_path, monkeypatch):
    """
    Sets up a temporary repository with the following structure:

    - Top-level files:
        include1.txt -> "Content of include1"
        exclude1.txt -> "Content of exclude1"
        ignored1.pyc -> "Should be ignored by suffix"
        .nit.py     -> "Should be ignored by dot prefix"

    - Top-level directories:
        dir_included/
            Files: a.txt, b.txt, c.txt
            Directory: subdir_exclude/ (contains file x.txt, to be excluded)
        dir_excluded/ (contents arbitrary)
        .git/ (should be ignored)
    """
    # Create top-level files.
    file_include = tmp_path / "include1.txt"
    file_include.write_text("Content of include1")
    file_exclude = tmp_path / "exclude1.txt"
    file_exclude.write_text("Content of exclude1")
    ignored_file_pyc = tmp_path / "ignored1.pyc"
    ignored_file_pyc.write_text("Ignored content")
    ignored_dot_file = tmp_path / ".nit.py"
    ignored_dot_file.write_text("Ignored dot file")

    # Create top-level directories.
    dir_included = tmp_path / "dir_included"
    dir_included.mkdir()
    # Files in dir_included.
    (dir_included / "a.txt").write_text("File A content")
    (dir_included / "b.txt").write_text("File B content")
    (dir_included / "c.txt").write_text("File C content")
    # A subdirectory in dir_included that should be excluded.
    subdir_exclude = dir_included / "subdir_exclude"
    subdir_exclude.mkdir()
    (subdir_exclude / "x.txt").write_text("X in excluded subdir")

    # Create another directory to be entirely excluded.
    dir_excluded = tmp_path / "dir_excluded"
    dir_excluded.mkdir()
    (dir_excluded / "file.txt").write_text("Content not to be included")

    # Create a .git directory (should be ignored).
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("Git config content")

    # Change current directory to our temp repo.
    monkeypatch.chdir(tmp_path)
    return tmp_path

def test_complex_repo_selection(monkeypatch, complex_temp_repo):
    """
    Simulate interactive responses to select files/directories as follows:

    Top-Level Files:
      Prompt: "Include files in '.'? (Y=all, N=none, O=one-by-one):" -> answer "o"
         • For "exclude1.txt": respond "n"
         • For "include1.txt": respond "y"
         (ignored files are not prompted)

    Top-Level Directories:
      Prompt: "Include directories in '.'? (Y=all, N=none, O=one-by-one):" -> answer "o"
         • For "dir_excluded": respond "n"
         • For "dir_included": respond "y"

    Inside "dir_included":
      Files in "dir_included": Prompt: "Include files in 'dir_included'? ..." -> answer "y"
         (thus, include a.txt, b.txt, c.txt)
      Directories in "dir_included": Prompt: "Include directories in 'dir_included'? ..." -> answer "o"
         • For "subdir_exclude": respond "n"
    """
    # Define the sequence of responses in order:
    responses = iter([
        # For top-level files
        "o",    # choose one-by-one for top-level files
        "n",    # for "exclude1.txt" -> exclude
        "y",    # for "include1.txt" -> include

        # For top-level directories
        "o",    # choose one-by-one for top-level directories
        "n",    # for "dir_excluded" -> exclude
        "y",    # for "dir_included" -> include

        # For "dir_included": files
        "y",    # for files in "dir_included": choose all (y)

        # For "dir_included": directories
        "o",    # choose one-by-one for directories in "dir_included"
        "n",    # for "subdir_exclude" -> exclude
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))

    # Run the main function; this should process the temporary repo.
    # Use specific output file in the current directory for testing
    output_file = Path.cwd() / "repo-contents.xml"
    main(output_file=str(output_file))

    # Check that the output XML file was created.
    assert output_file.exists(), "Output XML file was not created"

    # Read the XML file.
    xml_content = output_file.read_text()
    repo_name = Path.cwd().name
    # Check the repository name is included.
    assert f'<repo name="{repo_name}">' in xml_content, "Repo name not found in XML output"
    # Check the directory structure index exists.
    assert "<directory structure>" in xml_content, "Missing directory structure section"

    # Verify expected files are included.
    # Should include only "include1.txt" at top-level.
    assert "include1.txt" in xml_content, "include1.txt should be included"
    assert "exclude1.txt" not in xml_content, "exclude1.txt should be excluded"

    # In "dir_included", should include a.txt, b.txt, c.txt.
    assert "dir_included/a.txt" in xml_content, "a.txt should be included from dir_included"
    assert "dir_included/b.txt" in xml_content, "b.txt should be included from dir_included"
    assert "dir_included/c.txt" in xml_content, "c.txt should be included from dir_included"

    # "subdir_exclude" should not be included.
    assert "dir_included/subdir_exclude" not in xml_content, "subdir_exclude should be excluded"

    # Check that .git and ignored files are indeed not present.
    assert ".git" not in xml_content, ".git directory should be ignored"
    assert "ignored1.pyc" not in xml_content, "Files ending with .pyc should be ignored"
    # Files starting with '.' (like .nit.py) are ignored.
    assert ".nit.py" not in xml_content, "Dotfiles should be ignored"

    # Clean up test file
    if output_file.exists():
        output_file.unlink()
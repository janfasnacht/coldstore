# test_archive_project.py
import os
import tempfile
import shutil
from pathlib import Path
import tarfile
import sys

# Import the script to test
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import archive_project


def test_basic_archive_functionality(preserve_output=False):
    """
    Simple test to verify the basic archiving functionality works.
    Creates a test project structure, archives it, and verifies the results.

    Args:
        preserve_output (bool): If True, copies the test output to a persistent
                               location for manual inspection
    """
    # Determine output paths for preservation if needed
    preserved_project_path = None
    preserved_archive_path = None

    if preserve_output:
        # Create persistent paths in the current directory
        test_output_dir = Path("test_output")
        test_output_dir.mkdir(exist_ok=True)

        preserved_project_path = test_output_dir / "test_project"
        if preserved_project_path.exists():
            shutil.rmtree(preserved_project_path)

        preserved_archive_path = test_output_dir / "archives"
        if preserved_archive_path.exists():
            shutil.rmtree(preserved_archive_path)
        preserved_archive_path.mkdir(exist_ok=True)

    # Use temporary directories for the test
    with tempfile.TemporaryDirectory() as temp_project_dir, \
         tempfile.TemporaryDirectory() as temp_archive_dir:

        project_dir = Path(temp_project_dir) / "test_project"
        project_dir.mkdir()
        archive_dir = Path(temp_archive_dir)

        # Create a simple file structure
        (project_dir / "README.md").write_text("# Test Project\nThis is a test.")
        (project_dir / "src").mkdir()
        (project_dir / "src" / "main.py").write_text("print('Hello world')")
        (project_dir / "data").mkdir()
        (project_dir / "data" / "sample.json").write_text('{"test": "data"}')

        # Run the archive function
        print(f"Creating archive from {project_dir} to {archive_dir}")
        archive_path, sha256_path, readme_path = archive_project.archive_project(
            project_dir,
            archive_dir,
            note="Test archive",
            do_archive=True,
            do_upload=False
        )

        # Verify results
        assert archive_path is not None, "Archive was not created"
        assert archive_path.exists(), "Archive file does not exist"
        assert sha256_path.exists(), "SHA256 file does not exist"
        assert readme_path.exists(), "README file does not exist"

        # Check archive contents
        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getnames()
            print(f"Archive members: {members}")

            # Verify key files are in the archive
            assert "test_project/README.md" in members
            assert "test_project/src/main.py" in members
            assert "test_project/data/sample.json" in members

        # Check README content
        readme_content = readme_path.read_text()
        print(f"README preview: {readme_content[:200]}...")

        # Updated assertions to match the new README format
        assert "Test archive" in readme_content
        assert "test_project" in readme_content
        assert "Project:" in readme_content  # Changed from "**Project**"
        assert "Files:" in readme_content or "Total size:" in readme_content  # Changed from "**Files**" or "**Total size**"

        # Preserve output if requested
        if preserve_output and preserved_project_path and preserved_archive_path:
            print(f"\nPreserving test output for manual inspection:")

            # Copy the test project
            shutil.copytree(project_dir, preserved_project_path)
            print(f"- Test project copied to: {preserved_project_path}")

            # Copy the archive files
            for src_file in [archive_path, sha256_path, readme_path]:
                dst_file = preserved_archive_path / src_file.name
                shutil.copy2(src_file, dst_file)
                print(f"- {src_file.name} copied to: {dst_file}")

        print("Test completed successfully!")


if __name__ == "__main__":
    # When run directly (not through pytest), preserve the output
    # (for development/manual inspection)
    preserve = "--preserve" in sys.argv
    test_basic_archive_functionality(preserve_output=preserve)

    if preserve:
        print("\nTest output has been preserved in the 'test_output' directory for inspection.")

    print("All tests passed!")
"""
Unit and integration tests for tsktui.
"""

import os
import shutil
import pytest
from tsktui.backend import TSKBackend, Partition, FileEntry
from tsktui.ui import TSKTUIApp, SearchModal, PartitionModal, InfoModal, ViewFileScreen

# Sample disk images path
PARTITIONED_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../disk_disk_sleuth/dds1-alpine.flag.img"))
RAW_IMG = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../disko_1/disko-1.dd"))


def test_backend_partitions():
    """Verify partition detection on partitioned image."""
    if not os.path.exists(PARTITIONED_IMG):
        pytest.skip(f"Test image not found at {PARTITIONED_IMG}")
    
    backend = TSKBackend(PARTITIONED_IMG)
    partitions = backend.get_partitions()
    assert len(partitions) >= 1
    allocated = [p for p in partitions if p.is_allocated]
    assert len(allocated) >= 1
    assert allocated[0].start == 2048


def test_backend_raw_image():
    """Verify raw filesystem detection."""
    if not os.path.exists(RAW_IMG):
        pytest.skip(f"Test image not found at {RAW_IMG}")
        
    backend = TSKBackend(RAW_IMG)
    partitions = backend.get_partitions()
    assert len(partitions) == 1
    assert partitions[0].start == 0


def test_backend_file_listing():
    """Verify fls listing and parsing."""
    if not os.path.exists(PARTITIONED_IMG):
        pytest.skip(f"Test image not found at {PARTITIONED_IMG}")
        
    backend = TSKBackend(PARTITIONED_IMG)
    files = backend.list_files(offset=2048)
    assert len(files) > 0
    names = [f.name for f in files]
    assert "etc" in names or "home" in names


def test_backend_search_strings():
    """Verify srch_strings output."""
    if not os.path.exists(PARTITIONED_IMG):
        pytest.skip(f"Test image not found at {PARTITIONED_IMG}")
        
    backend = TSKBackend(PARTITIONED_IMG)
    results = backend.search_strings("pico", max_results=10)
    assert len(results) > 0
    assert any("pico" in r["content"].lower() for r in results)


@pytest.mark.asyncio
async def test_ui_app_pilot_navigation():
    """Verify Textual UI workflow end-to-end."""
    if not os.path.exists(PARTITIONED_IMG):
        pytest.skip(f"Test image not found at {PARTITIONED_IMG}")
        
    app = TSKTUIApp(PARTITIONED_IMG)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.partitions) > 0
        assert len(app.visible_files) > 0

        # Test filter
        app.filter_text = "doc"
        app.populate_table()
        await pilot.pause()
        assert len(app.visible_files) >= 1

        # Clear filter
        app.action_clear_filter()
        await pilot.pause()
        assert app.filter_text == ""

        # Test deleted toggle
        app.action_toggle_deleted()
        await pilot.pause()
        app.action_toggle_deleted()
        await pilot.pause()

        # Test view file
        app.action_view_file()
        await pilot.pause()
        if isinstance(app.screen, ViewFileScreen):
            app.screen.action_switch_tab()
            await pilot.pause()
            app.screen.action_close()
            await pilot.pause()

"""Progress tracking and display for long-running operations."""

import time
from typing import Optional

from coldstore.utils.formatters import format_size, format_time


class ProgressTracker:
    """
    Track and display progress for long-running operations.

    Provides time-based updates with ETA, throughput, and visual progress bar.
    Designed to be reusable across freeze, verify, and other operations.

    Features:
    - Time-based updates (not count-based) - updates every N seconds
    - ETA calculation based on elapsed time and items processed
    - Visual progress bar with customizable width
    - Current item display (truncated if too long)
    - Throughput metrics (items/sec, bytes/sec)

    Example:
        tracker = ProgressTracker(total_items=1000, total_bytes=10_000_000)
        for i, item in enumerate(items):
            process(item)
            tracker.update(
                items_processed=i+1,
                bytes_processed=bytes_so_far,
                current_item=str(item)
            )
        tracker.finish()
    """

    def __init__(
        self,
        total_items: int,
        total_bytes: Optional[int] = None,
        update_interval: float = 0.5,
        bar_width: int = 20,
        display_func=None,
    ):
        """
        Initialize progress tracker.

        Args:
            total_items: Total number of items to process
            total_bytes: Total bytes to process (optional, for throughput display)
            update_interval: Minimum seconds between display updates (default: 0.5)
            bar_width: Width of progress bar in characters (default: 20)
            display_func: Function to call with progress string (default: print)
        """
        self.total_items = total_items
        self.total_bytes = total_bytes
        self.update_interval = update_interval
        self.bar_width = bar_width
        self.display_func = display_func or print

        self.items_processed = 0
        self.bytes_processed = 0
        self.start_time = time.time()
        self.last_update_time = 0
        self.last_display_length = 0

    def update(
        self,
        items_processed: int,
        bytes_processed: Optional[int] = None,
        current_item: Optional[str] = None,
    ) -> None:
        """
        Update progress and optionally display.

        Updates are displayed at most once per update_interval seconds to avoid
        flooding output. Always displays when items_processed == total_items.

        Args:
            items_processed: Number of items processed so far
            bytes_processed: Number of bytes processed so far (optional)
            current_item: Current item being processed (optional, for display)
        """
        self.items_processed = items_processed
        if bytes_processed is not None:
            self.bytes_processed = bytes_processed

        current_time = time.time()
        is_complete = items_processed >= self.total_items

        # Only update display if enough time has passed OR operation is complete
        if (
            current_time - self.last_update_time >= self.update_interval
            or is_complete
        ):
            self._display_progress(current_item)
            self.last_update_time = current_time

    def finish(self) -> None:
        """
        Finish progress tracking and clear progress line.

        Call this after the operation completes to clean up the display.
        """
        # Clear the progress line by overwriting with spaces
        if self.last_display_length > 0:
            self.display_func("\r" + " " * self.last_display_length + "\r", end="")

    def _display_progress(self, current_item: Optional[str] = None) -> None:
        """
        Display current progress.

        Args:
            current_item: Current item being processed (optional)
        """
        # Calculate percentage
        percentage = (
            (self.items_processed / self.total_items * 100)
            if self.total_items > 0
            else 0
        )

        # Calculate elapsed time
        elapsed = time.time() - self.start_time

        # Calculate ETA
        if self.items_processed > 0 and elapsed > 0:
            avg_time_per_item = elapsed / self.items_processed
            remaining_items = self.total_items - self.items_processed
            eta_seconds = avg_time_per_item * remaining_items
            eta_str = format_time(eta_seconds)
        else:
            eta_str = "calculating..."

        # Calculate throughput
        items_per_sec = self.items_processed / elapsed if elapsed > 0 else 0

        # Format elapsed time
        elapsed_str = format_time(elapsed)

        # Create progress bar
        filled = int(self.bar_width * percentage / 100)
        bar = "█" * filled + "░" * (self.bar_width - filled)

        # Build progress line
        progress_parts = [
            f"\r📦 [{bar}] {percentage:5.1f}%",
            f"({self.items_processed}/{self.total_items})",
        ]

        # Add byte count if available
        if self.total_bytes is not None and self.bytes_processed > 0:
            progress_parts.append(f"| {format_size(self.bytes_processed)}")

        # Add timing info
        progress_parts.append(f"| Elapsed: {elapsed_str}")
        progress_parts.append(f"| ETA: {eta_str}")

        # Add throughput
        if items_per_sec > 0:
            progress_parts.append(f"| {items_per_sec:.1f} items/s")

        progress_line = " ".join(progress_parts)

        # Add current item on new line if provided
        if current_item:
            # Truncate if too long
            display_item = current_item
            if len(display_item) > 50:
                display_item = "..." + display_item[-47:]
            progress_line += f"\n   Current: {display_item}"

        # Display progress (overwrite previous line)
        self.display_func(progress_line, end="")

        # Track display length for cleanup
        self.last_display_length = len(progress_line.split("\n")[-1])

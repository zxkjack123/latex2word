"""File management utilities for tex2docx."""

import shutil
from pathlib import Path

from .config import ConversionConfig
from .exceptions import ConfigurationError


class FileManager:
    """Handles file and directory management operations."""
    
    def __init__(self, config: ConversionConfig) -> None:
        """
        Initialize the file manager.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.logger = config.setup_logger()
    
    def prepare_temp_directory(self) -> None:
        """Create or clean the temporary directory."""
        temp_dir = self._get_temp_directory()
        
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                self.logger.debug(
                    f"Removed existing temp directory: {temp_dir}"
                )
            
            temp_dir.mkdir(parents=True)
            self.logger.debug(f"Created temp directory: {temp_dir}")
        except OSError as e:
            self.logger.error(
                f"Error managing temp directory {temp_dir}: {e}"
            )
            raise
    
    def cleanup_temp_files(self) -> None:
        """Clean up temporary files and directories."""
        temp_dir = self._get_temp_directory()
        output_tex = self._get_output_texfile()

        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                self.logger.info(f"Removed temporary directory: {temp_dir}")
            except Exception as e:
                self.logger.error(f"Error removing temp directory: {e}")
        else:
            self.logger.debug(
                "Temporary directory not found, skipping removal"
            )
        
        if output_tex.exists():
            try:
                output_tex.unlink()
                self.logger.info(
                    f"Removed modified TeX file: {output_tex.name}"
                )
            except Exception as e:
                self.logger.error(f"Error removing modified TeX file: {e}")
        else:
            self.logger.debug("Modified TeX file not found, skipping removal")
    
    def should_cleanup(self) -> bool:
        """
        Determine if cleanup should be performed based on debug mode.
        
        Returns:
            True if cleanup should be performed, False otherwise.
        """
        return not self.config.debug
    
    def log_temp_file_locations(self, reason: str | None = None) -> None:
        """Log where temporary outputs can be inspected."""
        if reason is not None:
            self.logger.info(reason)
        elif self.config.debug:
            self.logger.info(
                "Debug mode enabled, skipping cleanup of temporary files"
            )
        else:
            self.logger.info("Skipping cleanup of temporary files")

        temp_dir = self._get_temp_directory()
        output_tex = self._get_output_texfile()

        self.logger.info(f"Temporary files are in: {temp_dir}")
        self.logger.info(f"Modified TeX file: {output_tex}")

    def _get_temp_directory(self) -> Path:
        """Return the configured temporary directory path."""
        if self.config.temp_subtexfile_dir is None:
            raise ConfigurationError("Temporary directory path is not set")
        return self.config.temp_subtexfile_dir

    def _get_output_texfile(self) -> Path:
        """Return the path to the modified TeX file."""
        if self.config.output_texfile is None:
            raise ConfigurationError("Output TeX file path is not set")
        return self.config.output_texfile

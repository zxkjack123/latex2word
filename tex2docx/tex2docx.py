"""Refactored LaTeX to Word converter with improved modularity."""

import logging
from pathlib import Path
from typing import Optional, Union

from .config import ConversionConfig, YamlValue
from .converter import PandocConverter
from .exceptions import Tex2DocxError
from .file_manager import FileManager
from .modifier import ContentModifier
from .parser import LatexParser
from .subfile import SubfileGenerator, SubfileCompiler


class LatexToWordConverter:
    """
    Main class for converting LaTeX documents to Word documents.

    This refactored version improves modularity, separates concerns,
    and provides better error handling.
    """
    
    def __init__(
        self,
        input_texfile: Union[str, Path],
        output_docxfile: Union[str, Path],
        bibfile: Union[str, Path, None] = None,
        cslfile: Union[str, Path, None] = None,
        reference_docfile: Union[str, Path, None] = None,
        debug: bool = False,
        multifig_texfile_template: Union[str, None] = None,  # Deprecated
        multifig_figenv_template: Union[str, None] = None,
        fix_table: bool = False,
        caption_locale: Optional[str] = None,
        author_metadata: Optional[YamlValue] = None,
    ) -> None:
        """
        Initialize the LaTeX to Word converter.

        Args:
            input_texfile: Path to the input LaTeX file.
            output_docxfile: Path to the output Word document file.
            bibfile: Path to the BibTeX file. Defaults to None
                (use the first .bib file found in the same directory
                 as input_texfile).
            cslfile: Path to the CSL file. Defaults to None
                (use the built-in ieee.csl file).
            reference_docfile: Path to the reference Word document file.
                Defaults to None (use the built-in default_temp.docx file).
            debug: Whether to enable debug mode. Defaults to False.
            multifig_texfile_template: Deprecated parameter, ignored.
            multifig_figenv_template: Template for figure environments
                in multi-figure LaTeX files. Defaults to built-in template.
            fix_table: Whether to fix tables by converting them to images.
                Defaults to False.
        """
        # Issue deprecation warning for old parameter
        if multifig_texfile_template is not None:
            logging.warning(
                "multifig_texfile_template parameter is deprecated and "
                "ignored. Templates are now generated dynamically."
            )

        input_path = Path(input_texfile)
        output_path = Path(output_docxfile)
        bib_path = Path(bibfile) if bibfile is not None else None
        csl_path = Path(cslfile) if cslfile is not None else None
        reference_path = (
            Path(reference_docfile) if reference_docfile is not None else None
        )

        self._caption_locale_explicit = caption_locale is not None

        # Create configuration
        self.config = ConversionConfig(
            input_texfile=input_path,
            output_docxfile=output_path,
            bibfile=bib_path,
            cslfile=csl_path,
            reference_docfile=reference_path,
            debug=debug,
            fix_table=fix_table,
            multifig_figenv_template=multifig_figenv_template,
        )

        if caption_locale is not None:
            locale_value = caption_locale.strip()
            self.config.apply_caption_preferences(locale=locale_value)

        if author_metadata is not None:
            self.config.set_author_metadata(author_metadata)
        
        # Set up logger
        self.logger = self.config.setup_logger()
        
        # Log initial configuration
        self.config.log_paths(self.logger)
        
        self.logger.debug(
            "LatexToWordConverter initialized with modular architecture"
        )
    
    def convert(self) -> None:
        """
        Execute the full LaTeX to Word conversion workflow.
        
        This method orchestrates the entire conversion process using
        specialized components for each stage.
        """
        file_manager = FileManager(self.config)
        conversion_failed = False

        try:
            self.logger.info("Starting LaTeX to Word conversion process")
            
            # Step 1: Parse and preprocess LaTeX content
            self.logger.info("Step 1: Parsing LaTeX content")
            parser = LatexParser(self.config)
            parser.read_and_preprocess()
            parser.analyze_structure()
            self._sync_author_metadata(parser)
            self._sync_caption_locale(parser)
            
            # Step 2: Prepare temporary directory
            self.logger.info("Step 2: Preparing temporary directory")
            file_manager.prepare_temp_directory()
            
            # Step 3: Generate and compile subfiles
            self.logger.info("Step 3: Generating and compiling subfiles")
            subfile_gen = SubfileGenerator(
                self.config,
                parser.get_analysis_summary(),
            )
            subfile_gen.generate_figure_subfiles(parser.figure_contents)
            
            if self.config.fix_table:
                subfile_gen.generate_table_subfiles(parser.table_contents)
            
            # Compile all subfiles
            compiler = SubfileCompiler(self.config)
            compiler.compile_all_subfiles(
                subfile_gen.created_figure_files,
                subfile_gen.created_table_files
            )
            
            # Step 4: Modify LaTeX content
            self.logger.info("Step 4: Creating modified LaTeX file")
            modifier = ContentModifier(self.config)
            cleaned_content = parser.clean_content
            if cleaned_content is None:
                raise Tex2DocxError(
                    "Parser did not produce cleaned LaTeX content."
                )

            modifier.create_modified_content(
                cleaned_content,
                parser.figure_contents,
                parser.table_contents,
                subfile_gen.created_figure_files,
                subfile_gen.created_table_files
            )
            modifier.write_modified_file()
            
            # Step 5: Convert to DOCX
            self.logger.info("Step 5: Converting to DOCX using Pandoc")
            pandoc_converter = PandocConverter(self.config)
            pandoc_converter.convert_to_docx()
            
            self.logger.info("Conversion process completed successfully")

        except Tex2DocxError as e:
            conversion_failed = True
            self.logger.error(f"Conversion failed: {e}")
            raise
        except Exception as e:
            conversion_failed = True
            self.logger.error(
                "Conversion failed due to unexpected error: %s",
                e,
                exc_info=True,
            )
            raise
        finally:
            if conversion_failed:
                file_manager.log_temp_file_locations(
                    "Skipping cleanup due to conversion failure."
                )
            elif file_manager.should_cleanup():
                file_manager.cleanup_temp_files()
            else:
                file_manager.log_temp_file_locations()

    def _sync_author_metadata(self, parser: LatexParser) -> None:
        """Populate configuration author metadata when available."""

        if self.config.author_metadata is not None:
            return

        if parser.author_metadata:
            self.config.set_author_metadata(parser.author_metadata)
            self.logger.debug("Author metadata extracted from LaTeX source")

    def _sync_caption_locale(self, parser: LatexParser) -> None:
        """Auto-adjust caption locale based on detected content."""

        if self._caption_locale_explicit:
            return

        if parser.contains_chinese and self.config.caption_style.is_default():
            self.config.apply_caption_preferences(locale="zh")
            self.logger.debug(
                "Caption locale auto-set to Chinese based on content"
            )


# Maintain backward compatibility by exposing the original interface
__all__ = ["LatexToWordConverter"]

# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

from unittest.mock import Mock, patch

from graphrag.config.models.chunking_config import ChunkingConfig
from graphrag.index.operations.chunk_text.strategies import run_sentences, run_tokens
from graphrag.index.operations.chunk_text.typing import TextChunk


class TestRunSentences:
    def test_basic_functionality(self):
        """Test basic sentence splitting without metadata"""
        input = ["This is a test. Another sentence."]
        tick = Mock()
        chunks = list(run_sentences(input, ChunkingConfig(), tick))

        assert len(chunks) == 2
        assert chunks[0].text_chunk == "This is a test."
        assert chunks[1].text_chunk == "Another sentence."
        assert all(c.source_doc_indices == [0] for c in chunks)
        tick.assert_called_once_with(1)

    def test_multiple_documents(self):
        """Test processing multiple input documents"""
        input = ["First. Document.", "Second. Doc."]
        tick = Mock()
        chunks = list(run_sentences(input, ChunkingConfig(), tick))

        assert len(chunks) == 4
        assert chunks[0].source_doc_indices == [0]
        assert chunks[2].source_doc_indices == [1]
        assert tick.call_count == 2

    def test_metadata_handling(self):
        """Test metadata prepending to sentences"""
        metadata = {"author": "John", "date": "2023"}
        chunks = list(
            run_sentences(["Test sentence."], ChunkingConfig(), Mock(), metadata)
        )

        expected = "author: John.\ndate: 2023.\nTest sentence."
        assert chunks[0].text_chunk == expected

    def test_custom_delimiter(self):
        """Test custom line delimiter usage"""
        chunks = list(
            run_sentences(
                ["Hello world."],
                ChunkingConfig(),
                Mock(),
                {"key": "value"},
                line_delimiter="|",
            )
        )

        assert chunks[0].text_chunk == "key: value|Hello world."

    def test_mixed_whitespace_handling(self):
        """Test input with irregular whitespace"""
        input = ["   Sentence with spaces.  Another one!   "]
        chunks = list(run_sentences(input, ChunkingConfig(), Mock()))
        assert chunks[0].text_chunk == "   Sentence with spaces."
        assert chunks[1].text_chunk == "Another one!"


class TestRunTokens:
    @patch("tiktoken.get_encoding")
    def test_basic_functionality(self, mock_get_encoding):
        """Test basic token-based chunking."""
        # Mock tiktoken encoding
        mock_encoder = Mock()
        mock_encoder.encode.side_effect = lambda x: list(
            x.encode()
        )  # Simulate encoding
        mock_encoder.decode.side_effect = lambda x: bytes(
            x
        ).decode()  # Simulate decoding
        mock_get_encoding.return_value = mock_encoder

        # Input and config
        input = ["hello world"]
        config = ChunkingConfig(size=5, overlap=1, encoding_model="fake-encoding")
        tick = Mock()

        # Run the function
        chunks = list(run_tokens(input, config, tick))

        # Verify output
        assert len(chunks) > 0  # At least one chunk should be produced
        assert all(isinstance(chunk, TextChunk) for chunk in chunks)
        tick.assert_called_once_with(1)

    @patch("tiktoken.get_encoding")
    def test_metadata_handling(self, mock_get_encoding):
        """Test metadata inclusion in chunks."""
        mock_encoder = Mock()
        mock_encoder.encode.side_effect = lambda x: list(x.encode())
        mock_encoder.decode.side_effect = lambda x: bytes(x).decode()
        mock_get_encoding.return_value = mock_encoder

        input = ["test"]
        config = ChunkingConfig(size=5, overlap=1, encoding_model="fake-encoding")
        tick = Mock()
        metadata = {"author": "John"}

        chunks = list(run_tokens(input, config, tick, metadata))

        # Verify metadata is included in the chunk
        assert len(chunks) > 0
        assert "author: John" in chunks[0].text_chunk

    @patch("tiktoken.get_encoding")
    def test_custom_delimiter(self, mock_get_encoding):
        """Test custom line delimiter usage."""
        mock_encoder = Mock()
        mock_encoder.encode.side_effect = lambda x: list(x.encode())
        mock_encoder.decode.side_effect = lambda x: bytes(x).decode()
        mock_get_encoding.return_value = mock_encoder

        input = ["test"]
        config = ChunkingConfig(size=5, overlap=1, encoding_model="fake-encoding")
        tick = Mock()
        metadata = {"key": "value"}

        chunks = list(run_tokens(input, config, tick, metadata, line_delimiter="|"))

        # Verify custom delimiter is used
        assert len(chunks) > 0
        assert "key: value|" in chunks[0].text_chunk

    @patch("tiktoken.get_encoding")
    def test_non_string_input(self, mock_get_encoding):
        """Test handling of non-string input (e.g., numbers)."""
        mock_encoder = Mock()
        mock_encoder.encode.side_effect = lambda x: list(str(x).encode())
        mock_encoder.decode.side_effect = lambda x: bytes(x).decode()
        mock_get_encoding.return_value = mock_encoder

        input = [123]  # Non-string input
        config = ChunkingConfig(size=5, overlap=1, encoding_model="fake-encoding")
        tick = Mock()

        chunks = list(run_tokens(input, config, tick))  # type: ignore

        # Verify non-string input is handled
        assert len(chunks) > 0
        assert "123" in chunks[0].text_chunk

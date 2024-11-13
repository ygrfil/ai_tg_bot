from typing import List
import re

def split_long_message(text: str, min_length: int = 1800, max_length: int = 2200) -> List[str]:
    """
    Split text into chunks intelligently:
    - Try to keep chunks between min_length and max_length
    - Split at sentence boundaries when possible
    - Preserve code blocks
    - Keep paragraphs together when possible
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""
    in_code_block = False
    code_block_content = ""

    # Split into lines to handle code blocks and paragraphs
    lines = text.split('\n')

    for line in lines:
        # Handle code block markers
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                # Starting new code block
                code_block_content = line + '\n'
            else:
                # Ending code block
                code_block_content += line + '\n'
                if len(current_chunk) + len(code_block_content) > max_length:
                    # If code block doesn't fit, start new chunk
                    if current_chunk:
                        chunks.append(current_chunk.rstrip())
                    current_chunk = code_block_content
                else:
                    current_chunk += code_block_content
                code_block_content = ""
            continue

        if in_code_block:
            code_block_content += line + '\n'
            continue

        # Regular text handling
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + '\n'
        else:
            # If chunk is too small, try to find a good split point
            if len(current_chunk) < min_length and not line.strip().startswith('#'):
                # Split at sentence boundary
                sentences = re.split(r'([.!?]+(?:\s+|$))', line)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) > max_length:
                        chunks.append(current_chunk.rstrip())
                        current_chunk = sentence
                    else:
                        current_chunk += sentence
            else:
                # Current chunk is long enough, start new one
                chunks.append(current_chunk.rstrip())
                current_chunk = line + '\n'

    # Add remaining content
    if current_chunk:
        chunks.append(current_chunk.rstrip())

    return chunks 
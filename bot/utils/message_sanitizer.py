import re
from typing import Optional

def sanitize_html_tags(text: str) -> str:
    """
    Enhanced HTML sanitizer that handles nested tags and malformed HTML.
    Supported tags: b, i, u, s, code, pre, a
    """
    # First, fix doubled closing tags (e.g., "</</b>" -> "</b>")
    text = re.sub(r'</+([a-zA-Z]+)>', r'</\1>', text)
    
    # List of allowed HTML tags in Telegram
    allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
    
    # Stack to keep track of opened tags and their positions
    tag_stack = []
    
    # Find all HTML tags in the text
    tag_pattern = re.compile(r'<(/?)([a-zA-Z]+)([^>]*)>')
    
    # Split text into chunks preserving tags
    chunks = []
    last_end = 0
    
    try:
        for match in tag_pattern.finditer(text):
            start, end = match.span()
            is_closing = bool(match.group(1))
            tag_name = match.group(2).lower()
            
            # Add text before the tag
            if start > last_end:
                chunks.append(text[last_end:start])
            
            # Handle only allowed tags
            if tag_name in allowed_tags:
                if not is_closing:
                    # Opening tag
                    if tag_name == 'a':
                        # Preserve href attribute for links
                        href_match = re.search(r'href=["\'](.*?)["\']', match.group(3))
                        if href_match:
                            chunks.append(f'<a href="{href_match.group(1)}">')
                        else:
                            # Skip malformed anchor tags
                            continue
                    else:
                        chunks.append(f'<{tag_name}>')
                    tag_stack.append(tag_name)
                else:
                    # Closing tag
                    if tag_stack:
                        # If the closing tag matches the last opened tag
                        if tag_stack[-1] == tag_name:
                            chunks.append(f'</{tag_name}>')
                            tag_stack.pop()
                        else:
                            # If we have a mismatched closing tag, close all tags up to the matching one
                            if tag_name in tag_stack:
                                while tag_stack and tag_stack[-1] != tag_name:
                                    chunks.append(f'</{tag_stack.pop()}>')
                                if tag_stack:
                                    chunks.append(f'</{tag_stack.pop()}>')
            last_end = end
        
        # Add remaining text
        if last_end < len(text):
            chunks.append(text[last_end:])
        
        # Close any remaining open tags in reverse order
        for tag in reversed(tag_stack):
            chunks.append(f'</{tag}>')
        
        result = ''.join(chunks)
        
        # Additional cleanup for common issues
        result = (result
                 .replace('<<', '<')
                 .replace('>>', '>')
                 .replace('<//', '</'))
        
        # Remove any remaining invalid HTML tags
        result = re.sub(r'<(?![/]?(?:' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', result)
        
        return result
    
    except Exception as e:
        # If any error occurs during sanitization, strip all HTML tags
        return re.sub(r'<[^>]+>', '', text)

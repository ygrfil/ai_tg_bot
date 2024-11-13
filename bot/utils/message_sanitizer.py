import re
from typing import Optional
import logging

def sanitize_html_tags(text: str) -> str:
    """
    Simplified HTML sanitizer that ensures all tags are properly closed.
    Supported tags: b, i, u, s, code, pre, a
    """
    try:
        # Strip any existing malformed or nested tags first
        text = re.sub(r'<([a-zA-Z]+)[^>]*</', '</', text)
        
        # Define allowed tags
        allowed_tags = '|'.join(['b', 'i', 'u', 's', 'code', 'pre', 'a'])
        
        # Remove any tags that aren't in our allowed list
        text = re.sub(f'<(?!/?)(?!(?:{allowed_tags})\b)[^>]*>', '', text)
        
        # Process the text character by character
        result = []
        tag_stack = []
        current_tag = []
        in_tag = False
        
        for char in text:
            if char == '<':
                in_tag = True
                current_tag = ['<']
                continue
                
            if in_tag:
                current_tag.append(char)
                if char == '>':
                    tag_str = ''.join(current_tag)
                    
                    # Check if it's a closing tag
                    if tag_str.startswith('</'):
                        tag_name = re.match(r'</([a-zA-Z]+)', tag_str)
                        if tag_name and tag_name.group(1).lower() in allowed_tags.split('|'):
                            if tag_stack and tag_stack[-1] == tag_name.group(1).lower():
                                result.append(tag_str)
                                tag_stack.pop()
                    
                    # Check if it's an opening tag
                    else:
                        tag_name = re.match(r'<([a-zA-Z]+)', tag_str)
                        if tag_name and tag_name.group(1).lower() in allowed_tags.split('|'):
                            if tag_name.group(1).lower() == 'a':
                                # Special handling for <a> tags with href
                                href_match = re.search(r'href=["\'](.*?)["\']', tag_str)
                                if href_match:
                                    result.append(f'<a href="{href_match.group(1)}">')
                                    tag_stack.append('a')
                            else:
                                result.append(f'<{tag_name.group(1).lower()}>')
                                tag_stack.append(tag_name.group(1).lower())
                    
                    in_tag = False
                    current_tag = []
                continue
            
            if not in_tag:
                result.append(char)
        
        # Close any remaining open tags in reverse order
        for tag in reversed(tag_stack):
            result.append(f'</{tag}>')
        
        sanitized = ''.join(result)
        
        # Final cleanup
        sanitized = (sanitized
            .replace('><', '> <')  # Add space between adjacent tags
            .replace('  ', ' ')    # Remove double spaces
            .strip())
        
        return sanitized
        
    except Exception as e:
        logging.error(f"Sanitization error: {e}")
        # If anything goes wrong, strip all HTML tags
        return re.sub(r'<[^>]*>', '', text)

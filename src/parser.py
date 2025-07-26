"""
Модуль для парсинга контента RanobeLIB
"""

import json
import html as html_lib
import re
from typing import Dict, List, Any, Callable

from .api import RanobeLibAPI

class RanobeLibParser:
    """Класс для парсинга контента с RanobeLIB"""
    
    def __init__(self, api: RanobeLibAPI):
        self.api = api
        
        self._element_handlers: Dict[str, Callable[[Dict[str, Any], List[Dict[str, Any]]], str]] = {
            "hardBreak": self._handle_hard_break,
            "horizontalRule": self._handle_horizontal_rule,
            "image": self._handle_image,
            "paragraph": lambda element, attachments: self._handle_simple_tag(element, attachments, "p"),
            "orderedList": lambda element, attachments: self._handle_simple_tag(element, attachments, "ol"),
            "listItem": lambda element, attachments: self._handle_simple_tag(element, attachments, "li"),
            "blockquote": lambda element, attachments: self._handle_simple_tag(element, attachments, "blockquote"),
            "italic": lambda element, attachments: self._handle_simple_tag(element, attachments, "i"),
            "bold": lambda element, attachments: self._handle_simple_tag(element, attachments, "b"),
            "underline": lambda element, attachments: self._handle_simple_tag(element, attachments, "u"),
            "heading": lambda element, attachments: self._handle_simple_tag(element, attachments, "h2"),
            "text": self._handle_text,
        }
        
    def json_to_html(self, json_content: List[Dict[str, Any]], attachments: List[Dict[str, Any]]) -> str:
        """Преобразование JSON-содержимого в HTML."""
        if not json_content:
            return ""
        
        html_parts = []
        for element in json_content:
            element_type = element.get("type")
            handler = self._handle_default
            if isinstance(element_type, str):
                handler = self._element_handlers.get(element_type, self._handle_default)
            html_parts.append(handler(element, attachments))
            
        return "".join(html_parts)
    
    def decode_html_entities(self, text: str, max_iterations: int = 5) -> str:
        """Рекурсивное декодирование HTML-сущностей."""
        if not isinstance(text, str):
            return text  # type: ignore

        previous = text
        for _ in range(max_iterations):
            decoded = html_lib.unescape(previous)
            if decoded == previous:
                break
            previous = decoded
        return previous
    
    def _handle_simple_tag(self, element: Dict[str, Any], attachments: List[Dict[str, Any]], tag: str) -> str:
        """Обработка простого тега с вложенным контентом."""
        content = self.json_to_html(element.get("content", []), attachments) if element.get("content") else "<br>"
        return f"<{tag}>{content}</{tag}>"

    def _handle_hard_break(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка тега <br>."""
        return "<br>"

    def _handle_horizontal_rule(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка тега <hr>."""
        return "<hr>"

    def _handle_image(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка тега <img>."""
        html = ""
        attrs = element.get("attrs", {})
        if attrs.get("images"):
            for img in attrs["images"]:
                image_id = img.get("image")
                file = next((f for f in attachments if f.get("name") == image_id or f.get("id") == image_id), None)
                if file:
                    html += f"<img src='{file['url']}'>"
        elif attrs:
            attr_str = " ".join([f'{key}="{value}"' for key, value in attrs.items() if value])
            html += f"<img {attr_str}>"
        return html

    def _handle_text(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка текста."""
        text_val = element.get("text", "")
        processed_text = re.sub(" +", " ", text_val.replace("\n", " "))
        return self.decode_html_entities(processed_text)

    def _handle_default(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка неизвестного типа элемента."""
        return f"<pre>{json.dumps(element, indent=2)}</pre>" 
"""
Модуль для парсинга контента RanobeLIB
"""

import html as html_lib
import json
import re
from typing import Any, Callable, Dict, List

from .api import RanobeLibAPI


class RanobeLibParser:
    """Класс для парсинга контента с RanobeLIB"""

    def __init__(self, api: RanobeLibAPI):
        self.api = api

        self._element_handlers: Dict[str, Callable[[Dict[str, Any], List[Dict[str, Any]]], str]] = {
            "hardBreak": self._handle_hard_break,
            "horizontalRule": self._handle_horizontal_rule,
            "image": self._handle_image,
            "paragraph": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "p"
            ),
            "orderedList": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "ol"
            ),
            "listItem": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "li"
            ),
            "blockquote": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "blockquote"
            ),
            "italic": lambda element, attachments: self._handle_simple_tag(element, attachments, "i"),
            "bold": lambda element, attachments: self._handle_simple_tag(element, attachments, "b"),
            "underline": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "u"
            ),
            "heading": lambda element, attachments: self._handle_simple_tag(
                element, attachments, "h2"
            ),
            "text": self._handle_text,
        }

        self._mark_tags: List[tuple] = [
            ("bold", "b"),
            ("italic", "i"),
            ("underline", "u"),
            ("strike", "s"),
            ("code", "code"),
            ("subscript", "sub"),
            ("superscript", "sup"),
        ]

    def json_to_html(
        self, json_content: List[Dict[str, Any]], attachments: List[Dict[str, Any]]
    ) -> str:
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

    def _handle_simple_tag(
        self, element: Dict[str, Any], attachments: List[Dict[str, Any]], tag: str
    ) -> str:
        """Обработка простого тега с вложенным контентом."""
        content = (
            self.json_to_html(element.get("content", []), attachments)
            if element.get("content")
            else "<br>"
        )
        return f"<{tag}>{content}</{tag}>"

    def _handle_hard_break(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка тега <br>."""
        return "<br>"

    def _handle_horizontal_rule(
        self, element: Dict[str, Any], attachments: List[Dict[str, Any]]
    ) -> str:
        """Обработка тега <hr>."""
        return "<hr>"

    def _handle_image(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка тега <img> (+ подпись/примечание)."""
        html = ""
        attrs = element.get("attrs", {})
        if attrs.get("images"):
            for img in attrs["images"]:
                image_id = img.get("image")
                file = next(
                    (
                        f
                        for f in attachments
                        if f.get("name") == image_id or f.get("id") == image_id
                    ),
                    None,
                )
                if file:
                    safe_url = html_lib.escape(file['url'], quote=True)
                    html += f'<img src="{safe_url}">'
        elif attrs:
            safe_attrs = []
            allowed_attrs = {"src", "alt", "width", "height", "title"}
            for key, value in attrs.items():
                if key in allowed_attrs and value:
                    safe_val = html_lib.escape(str(value), quote=True)
                    safe_attrs.append(f'{key}="{safe_val}"')
            attr_str = " ".join(safe_attrs)
            if attr_str:
                html += f"<img {attr_str}>"
            else:
                html += "<img>"

        description = attrs.get("description")
        if html and isinstance(description, str) and description.strip():
            caption = self.decode_html_entities(description)
            caption = html_lib.escape(caption, quote=True)
            caption = re.sub(" +", " ", caption.replace("\n", "<br>"))
            html = f"<figure>{html}<figcaption>{caption}</figcaption></figure>"

        return html

    def _handle_text(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка текста с учётом инлайн-форматирования."""
        text_val = element.get("text", "")
        text_val = self.decode_html_entities(text_val)
        text_val = html_lib.escape(text_val, quote=True)
        processed_text = re.sub(" +", " ", text_val.replace("\n", "<br>"))

        marks = element.get("marks")
        if not marks or not isinstance(marks, list):
            return processed_text

        mark_types = {
            m.get("type"): m for m in marks if isinstance(m, dict) and m.get("type")
        }

        for mark_type, tag in self._mark_tags:
            if mark_type in mark_types:
                processed_text = f"<{tag}>{processed_text}</{tag}>"

        link_mark = mark_types.get("link")
        if link_mark:
            href = (link_mark.get("attrs") or {}).get("href", "")
            safe_href = html_lib.escape(str(href), quote=True)
            processed_text = f'<a href="{safe_href}">{processed_text}</a>'

        return processed_text

    def _handle_default(self, element: Dict[str, Any], attachments: List[Dict[str, Any]]) -> str:
        """Обработка неизвестного типа элемента."""
        safe_json = html_lib.escape(json.dumps(element, indent=2))
        return f"<pre>{safe_json}</pre>" 
class html:
    @staticmethod
    def escape(text: str) -> str:
        return text

    @staticmethod
    def bold(text: str) -> str:
        return f"<b>{text}</b>"

    @staticmethod
    def italic(text: str) -> str:
        return f"<i>{text}</i>"

    @staticmethod
    def underline(text: str) -> str:
        return f"<u>{text}</u>"

    @staticmethod
    def strikethrough(text: str) -> str:
        return f"{text}​"

    @staticmethod
    def spoiler(text: str) -> str:
        return f"<tg-spoiler>{text}</tg-spoiler>"

    @staticmethod
    def code(text: str) -> str:
        return f"<code>{text}</code>"

    @staticmethod
    def pre(text: str) -> str:
        return f"<pre>{text}</pre>"

    @staticmethod
    def link(text: str, url: str) -> str:
        return f'<a href="{url}">{text}</a>'

    @staticmethod
    def hide_link(url: str) -> str:
        return f'<a href="{url}">&#8203;</a>'

    @staticmethod
    def quote(text: str) -> str:
        return f"<blockquote>{text}</blockquote>"

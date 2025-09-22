from __future__ import annotations

from typing import Any, Dict, Optional
import httpx


class ZoteroClient:
    def __init__(self, api_key: Optional[str], user_id: Optional[str] = None, group_id: Optional[str] = None, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.user_id = user_id
        self.group_id = group_id
        self.timeout = timeout

    def _base_url(self) -> Optional[str]:
        if self.user_id:
            return f"https://api.zotero.org/users/{self.user_id}"
        if self.group_id:
            return f"https://api.zotero.org/groups/{self.group_id}"
        return None

    def get_item(self, key: str) -> Optional[Dict[str, Any]]:
        base = self._base_url()
        if not base or not self.api_key:
            return None
        url = f"{base}/items/{key}"
        headers = {"Zotero-API-Key": self.api_key}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
        try:
            meta = data.get("data") or {}
            title = meta.get("title")
            year = None
            date = meta.get("date") or meta.get("year")
            if date:
                # простая вырезка года
                import re
                m = re.search(r"(\d{4})", str(date))
                if m:
                    year = int(m.group(1))
            creators = meta.get("creators") or []
            authors = []
            for c in creators:
                if (c.get("creatorType") or "").lower() in ("author", "editor", "contributor"):
                    parts = [p for p in [c.get("firstName"), c.get("lastName")] if p]
                    if parts:
                        authors.append(" ".join(parts))
            tags_raw = meta.get("tags") or []
            tags = [t.get("tag") for t in tags_raw if isinstance(t, dict) and t.get("tag")]
            return {
                "zotero_key": key,
                "title": title,
                "authors": authors or None,
                "year": year,
                "tags": tags or None,
            }
        except Exception:
            return None

    def search_items(self, title: str, limit: int = 5) -> Optional[list[Dict[str, Any]]]:
        base = self._base_url()
        if not base or not self.api_key or not title:
            return None
        url = f"{base}/items"
        headers = {"Zotero-API-Key": self.api_key}
        out: dict[str, Dict[str, Any]] = {}
        tries = [
            {"q": title, "qmode": "title"},      # 1) строго по названию
            {"q": title},                           # 2) по всему (title/creator/…)
        ]
        common = {
            "format": "json",
            "limit": max(1, min(20, int(limit))),
            "sort": "title",
            "direction": "asc",
            "itemType": "-attachment",  # исключить вложения
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for params in tries:
                    params_all = {**common, **params}
                    resp = client.get(url, headers=headers, params=params_all)
                    if resp.status_code != 200:
                        continue
                    items = resp.json()
                    for it in items:
                        data = it.get("data") or {}
                        key = it.get("key") or data.get("key")
                        ttl = data.get("title")
                        # фильтруем по типам, но не жёстко
                        # допускаем webpage, book, journalArticle и пр.
                        if not key or not ttl:
                            continue
                        # год
                        year = None
                        date = data.get("date") or data.get("year")
                        if date:
                            import re
                            m = re.search(r"(\d{4})", str(date))
                            if m:
                                year = int(m.group(1))
                        creators = data.get("creators") or []
                        authors = []
                        for c in creators:
                            if (c.get("creatorType") or "").lower() in ("author", "editor", "contributor"):
                                parts = [p for p in [c.get("firstName"), c.get("lastName")] if p]
                                if parts:
                                    authors.append(" ".join(parts))
                        tags_raw = data.get("tags") or []
                        tags = [t.get("tag") for t in tags_raw if isinstance(t, dict) and t.get("tag")]
                        out[key] = {
                            "zotero_key": key,
                            "title": ttl,
                            "authors": authors or None,
                            "year": year,
                            "tags": tags or None,
                        }
            return list(out.values())
        except Exception:
            return None

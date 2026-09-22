from __future__ import annotations

from pathlib import Path
from typing import Any

from ..client import MetaClient

CREATIVE_FIELDS = "id,name,status,object_story_spec,thumbnail_url,effective_object_story_id"
CTA_TYPES = ["LEARN_MORE", "SIGN_UP", "SHOP_NOW", "BOOK_TRAVEL", "CONTACT_US", "GET_OFFER",
             "GET_QUOTE", "SUBSCRIBE", "APPLY_NOW", "DOWNLOAD", "WATCH_MORE", "MESSAGE_PAGE",
             "WHATSAPP_MESSAGE", "CALL_NOW", "ORDER_NOW", "BUY_NOW", "NO_BUTTON"]


def list_creatives(client: MetaClient, account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return client.get_all(f"{account_id}/adcreatives", limit=limit, fields=CREATIVE_FIELDS)


def upload_image(client: MetaClient, account_id: str, path: str | None = None,
                 url: str | None = None) -> dict[str, Any]:
    """Upload an image and return {"hash": ..., "url": ..., "name": ...}."""
    if path:
        p = Path(path)
        with p.open("rb") as f:
            resp = client.request("POST", f"{account_id}/adimages",
                                  files={"filename": (p.name, f, "application/octet-stream")})
    elif url:
        resp = client.post(f"{account_id}/adimages", url=url)
    else:
        raise ValueError("path or url is required")
    images = resp.get("images", {})
    if not images:
        return resp
    name, info = next(iter(images.items()))
    return {"name": name, "hash": info.get("hash"), "url": info.get("url")}


def build_link_creative(*, page_id: str, link: str, message: str, headline: str | None = None,
                        description: str | None = None, image_hash: str | None = None,
                        video_id: str | None = None, cta: str = "LEARN_MORE",
                        instagram_actor_id: str | None = None, name: str | None = None,
                        extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble an object_story_spec for a single image (or video) link ad."""
    cta = cta.upper()
    if video_id:
        data: dict[str, Any] = {
            "video_id": video_id,
            "message": message,
            "title": headline,
            "link_description": description,
            "image_hash": image_hash,  # thumbnail for the video
            "call_to_action": {"type": cta, "value": {"link": link}},
        }
        story = {"page_id": page_id, "video_data": {k: v for k, v in data.items() if v is not None}}
    else:
        data = {
            "link": link,
            "message": message,
            "name": headline,
            "description": description,
            "image_hash": image_hash,
            "call_to_action": {"type": cta, "value": {"link": link}},
        }
        story = {"page_id": page_id, "link_data": {k: v for k, v in data.items() if v is not None}}
    if instagram_actor_id:
        story["instagram_user_id"] = instagram_actor_id
    payload: dict[str, Any] = {"name": name or (headline or message)[:60], "object_story_spec": story}
    if extra:
        payload.update(extra)
    return payload


def create_creative(client: MetaClient, account_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client.post(f"{account_id}/adcreatives", **payload)

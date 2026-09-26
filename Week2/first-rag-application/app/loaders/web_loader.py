"""Web page loader: download, strip <script>/<style>, keep the visible text."""

from typing import List

import requests
from bs4 import BeautifulSoup

from app.core.utils import stable_id
from app.models.document import Document

# Many sites (Wikipedia included) return 403 Forbidden to the default "python-requests/x.y"
# User-Agent. Identify your client honestly: app name/version + a way to contact you.
HTTP_HEADERS = {
    "User-Agent": "NovaCartFirstRAG/1.0 (educational RAG project; contact: your-email@example.com)",
    "Accept-Language": "en",
}


def load_webpage(url: str) -> List[Document]:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    title = soup.title.string.strip() if soup.title and soup.title.string else None

    return [Document(document_id=stable_id(url), text=text, source=url,
                     metadata={"source_type": "web", "url": url, "title": title, "page": None})]

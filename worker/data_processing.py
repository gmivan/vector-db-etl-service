from collections import Counter
import logging
import re
from typing import List, Optional, Tuple
import datetime

from openai import AsyncOpenAI


def join_lines(lines: List[str]) -> str:
    """Join lines into a single string."""
    return ' '.join(line.strip() for line in lines if line.strip())


def prepare_conversation_mongodb(conversation: str) -> dict:
    """Prepare conversation data for MongoDB storage."""
    tags = get_tags(conversation)
    min_len, max_len, avg_len = get_tags_statistics(tags)
    
    return {
        'text': conversation,
        'tags': tags,
        'tag_stats': {
            'min_length': min_len,
            'max_length': max_len,
            'avg_length': avg_len
        },
        'created_at': datetime.datetime.utcnow()
    }


def generate_convo_xml(convo: dict[str, ...]) -> str:
    xml_parts = [f"<conversation id='{83945}'>"]  # ???
    participants = {}
    for line in convo['lines']:
        if len(line) != 2:
            continue
        participant = f'p{line[0]}'
        xml_parts.append(f'<{participant}>{line[1]}</{participant}>')
        if participant not in participants:
            participants[participant] = 0
    xml_parts.append('</conversation>')
    xml = ''.join(xml_parts)
    return xml


def get_tags(text: str) -> List[str]:
    """Extract tags from text."""
    # Remove special characters and split into words
    words = re.sub(r'[^\w\s]', ' ', text.lower()).split()
    # Remove common words and short words
    common_words = {'the', 'and', 'or', 'but', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    tags = [word for word in words if word not in common_words and len(word) > 2]
    return list(set(tags))


async def get_tags(model: str, conversation: dict[str, ...], client: AsyncOpenAI | None = None) -> list[str]:
    if client is None:
        client = AsyncOpenAI()
    xml = generate_convo_xml(conversation)
    prompt1 = (  # TODO Experiment with prompt engineering
        'Analyze conversation in terms of topic interests of the participants.'
        'Analyze the conversation (provided in structured XML format) where <p0> has the questions '
        'and <p1> has the answers. Return comma-delimited tags.  Only return the tags without any English commentary.'
    )
    prompt = prompt1 + '\n\n\n' + xml
    completion = await client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
    content = completion.choices[0].message.content
    if content is None:
        logging.error(f'No content in response: {completion}, model: {model}')
        raise RuntimeError(f'No content in response: {completion}, model: {model}')
    tags = get_tags(content)
    return tags


def get_tags_statistics(tags: List[str]) -> Tuple[float, float, float]:
    """Calculate statistics for tags."""
    if not tags:
        return 0.0, 0.0, 0.0
    lengths = [len(tag) for tag in tags]
    return min(lengths), max(lengths), sum(lengths) / len(lengths)


def get_safe_tag(raw_tag: str, sep: str = ' ') -> str:
    # Remove non-alpha numeric
    pass1 = re.sub(r'\s{2,}|[^a-zA-Z0-9\s]', sep, raw_tag)
    return re.sub(r'[^\w\s]|(?<=\s)\s*', '', pass1).lower().strip()

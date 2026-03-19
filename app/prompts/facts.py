FACTS_EXTRACTION_PROMPT = """\
You are a memory assistant. Read the conversation below and extract factual information about the user that would be useful to remember for future conversations.

Focus on:
- Life events (job changes, trips, family events, challenges)
- Ongoing projects or goals the user mentioned
- Personal preferences revealed in the conversation
- Emotions or struggles the user shared

Rules:
- Extract only concrete, specific facts (not general impressions)
- Each fact should be one sentence, written in third person (e.g., "User is preparing for an English interview")
- Maximum 5 facts per session
- If there are no meaningful facts to extract, return an empty list
- Return ONLY a JSON array of strings, no other text

Conversation:
{conversation}

Return format (JSON array only):
["fact 1", "fact 2", ...]
"""

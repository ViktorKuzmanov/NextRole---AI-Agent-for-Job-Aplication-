"""LangChain chains: the two places NextRole calls an LLM."""

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from . import config
from .models import Classification

CLASSIFY_SYSTEM = """You screen job postings for one candidate and decide whether \
NextRole should apply on their behalf.

Candidate profile:
{profile}

Decide which target role the posting is ("ai_engineer" or "blockchain_developer"), \
or "skip" when it is neither or breaks one of the candidate's constraints.

Score the fit from 0 to 100 against the posting's actual requirements, not its title: \
required years of experience, required skills, seniority and location all count. \
Be strict. An application to a poor match wastes the candidate's reputation with \
that company, so when a hard requirement is clearly unmet, score below 50. \
A skipped posting gets a score of 0."""

JOB_BLOCK = """Company: {company}
Title: {title}
Location: {location}

{description}"""

COVER_LETTER_SYSTEM = """You write cover letters for one candidate.

Candidate profile:
{profile}

Write a cover letter for the posting below, in the candidate's first-person voice. \
Keep it to 150-220 words in three short paragraphs: why this company and role, the \
most relevant experience, and a brief close. Only claim skills and experience that \
appear in the profile; never invent employers, numbers or projects. Plain text, no \
placeholders in brackets, no subject line. Start with "Dear {company} team," and \
sign off with the candidate's name."""


def _llm(max_tokens: int) -> ChatAnthropic:
    # No temperature/top_p: current Claude models reject sampling parameters.
    return ChatAnthropic(model=config.MODEL, max_tokens=max_tokens, max_retries=3)


def build_classifier() -> Runnable:
    """job fields -> Classification. Uses Claude's native structured outputs
    (json_schema); the default forced-tool-call method is rejected by Opus 5.5."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", CLASSIFY_SYSTEM), ("human", JOB_BLOCK)]
    ).partial(profile=config.profile_text())
    return prompt | _llm(4000).with_structured_output(Classification, method="json_schema")


def build_cover_letter_writer() -> Runnable:
    """job fields -> cover letter text."""
    prompt = ChatPromptTemplate.from_messages(
        [("system", COVER_LETTER_SYSTEM), ("human", JOB_BLOCK)]
    ).partial(profile=config.profile_text())
    return prompt | _llm(4000) | StrOutputParser()

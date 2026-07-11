from __future__ import annotations

import pytest

from gcl.classifier.prompt_classifier import PromptClassifier, PromptTier


@pytest.fixture
def classifier():
    return PromptClassifier()


class TestPromptClassifier:
    def test_simple_question(self, classifier):
        result = classifier.classify("What is 2+2?")
        assert result.tier == PromptTier.SIMPLE
        assert result.confidence >= 0.7

    def test_complex_analysis(self, classifier):
        result = classifier.classify("Write a detailed analysis of distributed systems")
        assert result.tier == PromptTier.COMPLEX
        assert result.confidence >= 0.7

    def test_standard_summary(self, classifier):
        result = classifier.classify("Summarize the main points of this document")
        assert result.tier == PromptTier.STANDARD
        assert result.confidence >= 0.7

    def test_greeting_is_simple(self, classifier):
        result = classifier.classify("Hello, how are you?")
        assert result.tier == PromptTier.SIMPLE

    def test_code_generation_is_complex(self, classifier):
        result = classifier.classify("Implement a binary search algorithm in Python")
        assert result.tier == PromptTier.COMPLEX

    def test_unknown_defaults_to_standard(self, classifier):
        result = classifier.classify("Lorem ipsum dolor sit amet")
        assert result.tier == PromptTier.STANDARD
        assert result.confidence < 0.7

    def test_confidence_always_valid(self, classifier):
        for prompt in ["Hello", "Explain quantum physics", "Write an essay", "xyz123"]:
            result = classifier.classify(prompt)
            assert 0.0 <= result.confidence <= 1.0

    def test_estimated_tokens_by_tier(self, classifier):
        simple = classifier.classify("What is AI?")
        complex_r = classifier.classify("Write a comprehensive analysis")
        assert simple.estimated_tokens <= complex_r.estimated_tokens

    def test_models_for_tier(self, classifier):
        models = classifier.get_models_for_tier(PromptTier.SIMPLE)
        assert len(models) >= 1

    def test_describe_is_standard(self, classifier):
        result = classifier.classify("Describe the water cycle")
        assert result.tier == PromptTier.STANDARD

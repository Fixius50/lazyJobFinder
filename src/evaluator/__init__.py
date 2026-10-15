"""Capa de evaluación y scoring con Ollama y filtros deterministas."""

from .ollama_client import OllamaClient
from .scoring_engine import ScoringEngine

__all__ = ["OllamaClient", "ScoringEngine"]

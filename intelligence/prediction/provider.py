from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class Prediction:
    expected_replenishment_start: date
    expected_replenishment_end: date
    depletion_start: date | None
    depletion_end: date | None
    recommended_quantity: float | None
    confidence: float
    model_version: str


class PredictionProvider(Protocol):
    def predict(self, features: dict[str, float]) -> Prediction: ...


class ModelNotConfigured(RuntimeError):
    pass


class UnconfiguredProvider:
    def predict(self, features: dict[str, float]) -> Prediction:
        raise ModelNotConfigured('No trained ML model is configured. No prediction was generated.')


class ArtifactPredictionProvider:
    """Loads the active small model artifact and predicts one partner/product pair."""

    def __init__(self, model_loader, pair_predictor):
        self.model_loader = model_loader
        self.pair_predictor = pair_predictor

    def predict_pair(self, partner_id: str, product_id: str, events):
        artifact = self.model_loader()
        if artifact is None:
            raise ModelNotConfigured('No validated ML model is active. No prediction was generated.')
        result = self.pair_predictor(artifact, partner_id, product_id, events)
        if result is None:
            raise ModelNotConfigured('This partner/product pair has insufficient or unvalidated history.')
        return result

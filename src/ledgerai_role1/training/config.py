"""Configuration-driven parameter-efficient LoRA training definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoRATrainingConfig(BaseModel):
    """Configuration for reproducible LoRA / adapter fine-tuning."""

    model_config = ConfigDict(extra="forbid")

    base_model_name: str = "docintel-foundation-vlm"
    base_model_revision: str = (
        "sha256:d8a9f0e123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    )
    random_seed: int = 42
    lora_rank: int = Field(default=8, ge=1, le=64)
    lora_alpha: int = Field(default=16, ge=1, le=128)
    lora_dropout: float = Field(default=0.05, ge=0.0, le=0.5)
    learning_rate: float = Field(default=2e-4, gt=0.0)
    batch_size: int = Field(default=4, ge=1)
    max_epochs: int = Field(default=5, ge=1)
    allowed_splits: tuple[Literal["train", "val"], ...] = ("train", "val")
    checkpoint_dir: str = "checkpoints/role1_lora"

    @model_validator(mode="after")
    def forbid_test_split_access(self) -> LoRATrainingConfig:
        """Strictly prevent the held-out test evaluation set from being accessed during training."""
        if "test" in self.allowed_splits:
            raise ValueError(
                "Access to the held-out 'test' evaluation split "
                "during training is strictly prohibited."
            )
        return self

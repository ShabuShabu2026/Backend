"""Request models for the landing-site API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SlopeConstraint(BaseModel):
    enabled: bool = True
    maxDeg: float = Field(default=5, ge=0, le=15)


class CrewedConstraint(BaseModel):
    enabled: bool = True


class UncrewedConstraint(BaseModel):
    enabled: bool = False
    batteryEnduranceHours: float | None = Field(default=None, gt=0)
    maxCommBlackoutHours: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_limits(self) -> "UncrewedConstraint":
        if self.enabled and (self.batteryEnduranceHours is None or self.maxCommBlackoutHours is None):
            raise ValueError("Enabled uncrewed constraints require both limits.")
        return self


class Advanced(BaseModel):
    slopeConstraint: SlopeConstraint = Field(default_factory=SlopeConstraint)
    crewedSunlightConstraint: CrewedConstraint = Field(default_factory=CrewedConstraint)
    uncrewedConstraints: UncrewedConstraint = Field(default_factory=UncrewedConstraint)
    importanceWeights: list[int] | None = Field(default=None, min_length=5, max_length=5)
    requiredSunlightRatio: float | None = Field(default=None, ge=0, le=100)
    sunVisibilityCriterion: Literal["PARTIAL", "HALF_DISK", "FULL"] = "HALF_DISK"
    earthVisibilityCriterion: Literal["UPPER_EDGE", "CENTER_DELTA", "FULL"] = "CENTER_DELTA"
    heightM: Literal[1, 5, 10] = 1
    landingDateSearchRangeDays: int = Field(default=7, ge=0, le=30, strict=True)

    @model_validator(mode="after")
    def check_weights(self) -> "Advanced":
        if self.importanceWeights is not None and any(not 1 <= x <= 5 for x in self.importanceWeights):
            raise ValueError("Importance weights must be between 1 and 5.")
        return self


class AnalysisRequest(BaseModel):
    landingDate: date
    stayDays: int = Field(ge=1, strict=True)
    missionType: Literal["CREWED", "UNCREWED"]
    objective: Literal["GENERAL", "POLAR_VOLATILES", "PLANETARY_PROCESSES", "IMPACT_HISTORY",
                       "ANCIENT_SUN", "UNIQUE_OBSERVATION", "EXPERIMENTAL_SCIENCE", "EXPLORATION_RISKS"]
    powerRequirement: Literal["LOW", "NORMAL", "HIGH"]
    communicationDependency: Literal["INDEPENDENT", "NORMAL", "CRITICAL"]
    limit: int = Field(default=10, ge=1, le=50, strict=True)
    advanced: Advanced = Field(default_factory=Advanced)

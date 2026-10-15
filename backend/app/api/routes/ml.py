"""Protected Stage 6 ML integration endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import require_permission
from backend.app.core.config import Settings, get_settings
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.ml import (
    CashFlowForecastRequest,
    CashFlowForecastResponse,
    FeedbackRequest,
    FeedbackResponse,
    ForecastPointResponse,
    ModelRegisterRequest,
    ModelVersionResponse,
    PaymentRiskRequest,
    PaymentRiskResponse,
    PipelineName,
    PredictionHistoryResponse,
    SegmentationRequest,
    SegmentationResponse,
    TransactionClassifyRequest,
    TransactionPredictionResponse,
)
from backend.app.services.ml import MLService

router = APIRouter(prefix="/ml")
SessionDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
MLReader = Annotated[User, Depends(require_permission("ml:read"))]
MLPredictor = Annotated[User, Depends(require_permission("ml:predict"))]
MLManager = Annotated[User, Depends(require_permission("ml:manage"))]
MLFeedbackAuthor = Annotated[User, Depends(require_permission("ml:feedback"))]


@router.get("/models", response_model=list[ModelVersionResponse])
def list_models(
    session: SessionDep, settings: SettingsDep, _: MLReader, pipeline: PipelineName | None = None
) -> list[ModelVersionResponse]:
    return [
        ModelVersionResponse.model_validate(item)
        for item in MLService(session, settings).models(pipeline)
    ]


@router.get("/models/{pipeline}/active", response_model=ModelVersionResponse)
def active_model(
    pipeline: PipelineName, session: SessionDep, settings: SettingsDep, _: MLReader
) -> ModelVersionResponse:
    return ModelVersionResponse.model_validate(MLService(session, settings).active_model(pipeline))


@router.post(
    "/models/register", response_model=ModelVersionResponse, status_code=status.HTTP_201_CREATED
)
def register_model(
    data: ModelRegisterRequest, session: SessionDep, settings: SettingsDep, actor: MLManager
) -> ModelVersionResponse:
    item = MLService(session, settings).register_model(
        data.pipeline, data.artifact_identifier, actor
    )
    return ModelVersionResponse.model_validate(item)


@router.post("/models/{model_id}/activate", response_model=ModelVersionResponse)
def activate_model(
    model_id: UUID, session: SessionDep, settings: SettingsDep, actor: MLManager
) -> ModelVersionResponse:
    return ModelVersionResponse.model_validate(
        MLService(session, settings).activate_model(model_id, actor)
    )


@router.post("/transactions/classify", response_model=TransactionPredictionResponse)
def classify_transaction(
    data: TransactionClassifyRequest,
    session: SessionDep,
    settings: SettingsDep,
    actor: MLPredictor,
) -> TransactionPredictionResponse:
    prediction, value = MLService(session, settings).classify_transaction(
        data.description, actor, data.source_reference
    )
    if prediction.confidence is None:
        raise HTTPException(503, "Model prediction unavailable")
    return TransactionPredictionResponse(
        prediction_id=prediction.id,
        category=str(value["category"]),
        confidence=float(prediction.confidence),
        manual_review=bool(prediction.review_required),
        model_version=str(value["model_version"]),
        prediction_timestamp=prediction.predicted_at,
    )


@router.post("/payment-risk/predict", response_model=PaymentRiskResponse)
def payment_risk(
    data: PaymentRiskRequest, session: SessionDep, settings: SettingsDep, actor: MLPredictor
) -> PaymentRiskResponse:
    as_of = data.as_of or date.today()
    prediction, value = MLService(session, settings).payment_risk(data.invoice_id, as_of, actor)
    if prediction.confidence is None:
        raise HTTPException(503, "Model prediction unavailable")
    return PaymentRiskResponse(
        prediction_id=prediction.id,
        invoice_id=data.invoice_id,
        risk_category=str(value["risk_category"]),
        probability=float(prediction.confidence),
        model_version=str(value["model_version"]),
        explanation=value["explanation"],
        explanation_scope=str(value["scope"]),
        prediction_timestamp=prediction.predicted_at,
        as_of=as_of,
    )


@router.post("/cash-flow/forecast", response_model=CashFlowForecastResponse)
def cash_flow_forecast(
    data: CashFlowForecastRequest,
    session: SessionDep,
    settings: SettingsDep,
    actor: MLPredictor,
) -> CashFlowForecastResponse:
    as_of = data.as_of or date.today()
    prediction, points = MLService(session, settings).cash_flow_forecast(data.horizon, as_of, actor)
    return CashFlowForecastResponse(
        prediction_id=prediction.id,
        model_version=prediction.model_version.model_version,
        forecast_timestamp=prediction.predicted_at,
        as_of=as_of,
        horizon=data.horizon,
        points=[ForecastPointResponse.model_validate(item) for item in points],
    )


@router.post("/segmentation/predict", response_model=SegmentationResponse)
def customer_segmentation(
    data: SegmentationRequest, session: SessionDep, settings: SettingsDep, actor: MLPredictor
) -> SegmentationResponse:
    as_of = data.as_of or date.today()
    prediction, value = MLService(session, settings).segment_customer(data.party_id, as_of, actor)
    return SegmentationResponse(
        prediction_id=prediction.id,
        party_id=data.party_id,
        segment=int(value["segment"]),
        behavioral_description=str(value["behavioral_description"]),
        model_version=str(value["model_version"]),
        prediction_timestamp=prediction.predicted_at,
        as_of=as_of,
    )


@router.get("/predictions", response_model=list[PredictionHistoryResponse])
def prediction_history(
    session: SessionDep,
    settings: SettingsDep,
    actor: MLReader,
    pipeline: PipelineName | None = None,
) -> list[PredictionHistoryResponse]:
    return [
        PredictionHistoryResponse.model_validate(item)
        for item in MLService(session, settings).predictions(actor, pipeline)
    ]


@router.get("/predictions/{prediction_id}", response_model=PredictionHistoryResponse)
def prediction_detail(
    prediction_id: UUID, session: SessionDep, settings: SettingsDep, actor: MLReader
) -> PredictionHistoryResponse:
    return PredictionHistoryResponse.model_validate(
        MLService(session, settings).prediction(prediction_id, actor)
    )


@router.post(
    "/predictions/{prediction_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    prediction_id: UUID,
    data: FeedbackRequest,
    session: SessionDep,
    settings: SettingsDep,
    actor: MLFeedbackAuthor,
) -> FeedbackResponse:
    return FeedbackResponse.model_validate(
        MLService(session, settings).submit_feedback(prediction_id, data, actor)
    )

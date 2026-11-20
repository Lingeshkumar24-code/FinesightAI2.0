from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import TokenPayload, get_current_user
from app.engines.what_if_simulation import SimulationLevers, WhatIfSimulationEngine
from app.models.schemas import WhatIfRequest, WhatIfResponse

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/what-if", response_model=WhatIfResponse)
def what_if(
    payload: WhatIfRequest, _user: TokenPayload = Depends(get_current_user)
) -> WhatIfResponse:
    engine = WhatIfSimulationEngine()
    try:
        result = engine.simulate(
            starting_revenue=payload.starting_revenue,
            starting_costs=payload.starting_costs,
            starting_cash=payload.starting_cash,
            levers=SimulationLevers(**payload.levers.model_dump()),
            periods=payload.periods,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return WhatIfResponse(
        periods=[p.__dict__ for p in result.periods],
        ending_cash=result.ending_cash,
        breakeven_period=result.breakeven_period,
    )

# Intelligence and replenishment ML

The root `intelligence` package owns the reusable feature builder and provider
interface. The FastAPI pipeline in `backend/app/intelligence/pipeline.py` reads
real, non-voided `consumption_history` rows, aggregates same-day and same-order
lines, validates quantities and dates, builds temporal snapshots with
`build_features`, and trains one small ridge-regression model for each
partner/product relationship that passes the data and validation gates.

## Model contract

- Unit: one partner + one product.
- Targets: days until the next purchase and the quantity on that next order.
- Features: purchase count, historical and most recent interval, mean and last
  purchase quantity, and interval spread.
- Minimum: eight distinct purchase dates per relationship, five temporal
  snapshots, at least three training snapshots, and two holdout snapshots.
- Validation: the last chronological 30% of snapshots is held out. A pair is
  activated only if its interval and quantity MAE both beat the training-mean
  baseline. Snapshots only include records at or before their prediction date.
- Confidence is a reliability tier derived from out-of-time relative error and
  the number of observations. It is not a calibrated probability.
- Extreme daily values above ten times that relationship's median are excluded
  from training and counted in data quality output. Original history is never
  changed or removed.

Training is an explicit RBAC-protected `POST /api/intelligence/train` action
(`intelligence:train`); it does not run on page loads or every request. The
admin should retrain after new real order history accumulates. Model artifacts
are versioned JSON files written atomically. Set `INTELLIGENCE_MODEL_DIR` to a
persistent writable directory in hosted deployments. A Render instance with an
ephemeral filesystem needs a persistent disk mounted at that path to retain
the active model across restarts/deploys.

`GET /api/partners/{id}/predictions` loads the active artifact, predicts only
validated partner/product pairs, stores the forecast in `predictions`, and
creates a deduplicated commercial opportunity for medium/high reliability
tiers. Forecasts include a replenishment window, estimated next-order quantity,
model version, and an explanation that physical partner stock is not observed.
The next realized order automatically closes the latest eligible outstanding
forecast in `prediction_evaluations` and stores absolute quantity error.

No trained artifact or real production forecast is checked into this repository.
With fewer than eight useful observations for a relationship, the API reports
insufficient ML data and emits no ML number. Descriptive statistics remain
available separately from the model output.

import json
import math

import polars as pl

from barca.db.load import _finite, _rows


def test_non_finite_values_become_null_recursively():
    value = {"a": math.nan, "b": [1.0, math.inf, {"c": -math.inf}], "d": "x"}
    assert _finite(value) == {"a": None, "b": [1.0, None, {"c": None}], "d": "x"}


def test_rows_decode_json_columns_and_stay_serialisable():
    frame = pl.DataFrame(
        {
            "id": [1, 2],
            "score": [0.5, float("nan")],
            "per90": ['{"pass_completion": NaN, "xg": 0.2}', None],
        }
    )
    rows = _rows(frame, {"per90"})
    assert rows == [[1, 0.5, {"pass_completion": None, "xg": 0.2}], [2, None, None]]
    json.dumps(rows, allow_nan=False)

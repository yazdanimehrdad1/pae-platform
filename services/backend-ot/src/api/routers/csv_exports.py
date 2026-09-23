"""CSV export endpoints."""

import csv
import io

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from logger import get_logger

router = APIRouter(prefix="/csv-exports", tags=["csv-exports"])
logger = get_logger(__name__)


@router.get("/raw-register-map-csv")
async def export_raw_register_map_csv(
    type: str = Query(..., description="Export type (e.g., 'modbus')")
):
    """
    Export empty CSV file with register map column headers.

    If type is 'modbus', exports an empty CSV file with the following columns:
    - register_address
    - register_name
    - size
    - data_type
    - scale_factor
    - unit

    Args:
        type: Export type (must be 'modbus' for now)

    Returns:
        Empty CSV file with column headers only
    """
    if type != "modbus":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export type: {type}. Only 'modbus' is supported."
        )

    try:
        # Create CSV in memory with only headers
        output = io.StringIO()
        fieldnames = [
            "register_address",
            "register_name",
            "size",
            "data_type",
            "scale_factor",
            "unit",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Get CSV content as string (headers only, no data rows)
        csv_content = output.getvalue()
        output.close()

        # Return CSV as response
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=raw-register-map-csv.csv"
            }
        )

    except Exception as e:
        logger.error(f"Error exporting register map CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export CSV: {str(e)}"
        ) from e


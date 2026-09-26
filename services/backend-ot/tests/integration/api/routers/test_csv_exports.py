"""
Integration tests for /api/csv-exports.

The register-map export is currently a header-only template; guard its columns, content
type, and download filename so client importers don't silently break.
"""


class TestRawRegisterMapCsv:
    async def test_modbus_export_is_header_only_csv(self, client):
        response = await client.get(
            "/api/csv-exports/raw-register-map-csv", params={"type": "modbus"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "raw-register-map-csv.csv" in response.headers["content-disposition"]
        assert response.text.strip() == (
            "register_address,register_name,size,data_type,scale_factor,unit,class,severity"
        )

    async def test_unsupported_type_is_400(self, client):
        response = await client.get("/api/csv-exports/raw-register-map-csv", params={"type": "dnp"})
        assert response.status_code == 400

from app.services.export_service import DefaultExportPipeline
import json
import csv
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_export_json(tmp_path):
    pipeline = DefaultExportPipeline()
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    output = str(tmp_path / "output.json")
    result = await pipeline.export_json(data, output)
    assert result.success
    assert result.record_count == 2
    with open(output) as f:
        loaded = json.load(f)
    assert len(loaded) == 2
    assert loaded[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_export_csv(tmp_path):
    pipeline = DefaultExportPipeline()
    data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
    output = str(tmp_path / "output.csv")
    result = await pipeline.export_csv(data, output)
    assert result.success
    assert result.record_count == 2
    with open(output) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_export_csv_empty(tmp_path):
    pipeline = DefaultExportPipeline()
    output = str(tmp_path / "empty.csv")
    result = await pipeline.export_csv([], output)
    assert result.success
    assert result.record_count == 0

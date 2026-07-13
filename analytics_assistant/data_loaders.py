from pathlib import Path

import pandas as pd

SOURCE_SHEET_COL = "_source_sheet"


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame = frame.dropna(how="all")
    frame = frame.dropna(axis=1, how="all")
    frame.columns = [str(col).strip() for col in frame.columns]
    return frame


def _sheet_score(df: pd.DataFrame) -> int:
    frame = _normalize_frame(df)
    if len(frame) < 2 or len(frame.columns) < 2:
        return -1
    numeric_count = len(frame.select_dtypes(include=["number"]).columns)
    return int(len(frame) * 10 + numeric_count * 5 + len(frame.columns))


def _frames_compatible(frames: list[pd.DataFrame]) -> bool:
    if len(frames) < 2:
        return False
    base_columns = set(frames[0].columns)
    return all(set(frame.columns) == base_columns for frame in frames[1:])


def load_tabular_from_path(path: Path) -> tuple[pd.DataFrame, dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = _normalize_frame(pd.read_csv(path))
        if _sheet_score(frame) < 0:
            raise ValueError("CSV needs at least 2 rows and 2 columns with data.")
        return frame, {"format": "csv", "sheets_used": ["csv"], "strategy": "single"}

    if suffix not in (".xlsx", ".xls"):
        raise ValueError("Only CSV and Excel files are supported.")

    book = pd.ExcelFile(path)
    sheet_names = book.sheet_names
    scored: list[tuple[int, str, pd.DataFrame]] = []

    for name in sheet_names:
        raw = pd.read_excel(book, sheet_name=name)
        frame = _normalize_frame(raw)
        score = _sheet_score(frame)
        if score >= 0:
            scored.append((score, name, frame))

    if not scored:
        raise ValueError(
            "No usable worksheet found. Each sheet needs at least 2 rows and "
            "2 columns with data."
        )

    scored.sort(key=lambda item: item[0], reverse=True)

    if len(scored) == 1:
        _, name, frame = scored[0]
        return frame, {
            "format": "excel",
            "sheets_used": [name],
            "strategy": "single",
            "all_sheets": sheet_names,
        }

    frames = [item[2] for item in scored]
    names = [item[1] for item in scored]

    if _frames_compatible(frames):
        merged_parts = []
        for name, frame in zip(names, frames):
            part = frame.copy()
            part[SOURCE_SHEET_COL] = name
            merged_parts.append(part)
        merged = pd.concat(merged_parts, ignore_index=True)
        return merged, {
            "format": "excel",
            "sheets_used": names,
            "strategy": "merged",
            "all_sheets": sheet_names,
            "rows_per_sheet": {name: len(frame) for name, frame in zip(names, frames)},
        }

    _, best_name, best_frame = scored[0]
    return best_frame, {
        "format": "excel",
        "sheets_used": [best_name],
        "strategy": "best_sheet",
        "all_sheets": sheet_names,
        "note": (
            f"Used worksheet '{best_name}' (most complete). "
            "Other sheets had different column layouts and were skipped."
        ),
    }

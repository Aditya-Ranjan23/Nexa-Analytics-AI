import pandas as pd
import numpy as np
import re
from typing import Tuple, Dict, Any

class SmartDataPreparationEngine:
    def __init__(self):
        self.report = {
            "duplicate_rows_removed": 0,
            "missing_values_filled": 0,
            "dates_standardized": 0,
            "currencies_normalized": 0,
            "columns_cleaned": 0,
            "data_types_corrected": 0,
            "inferred_types": {},
            "quality_score": 100,
            "validation_errors": []
        }
        self.quality_deductions = 0

    def prepare(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        # Do not mutate the original
        df = df.copy()
        
        # 1. Validation
        if df.empty:
            self.report["validation_errors"].append("Dataset is empty.")
            self.report["quality_score"] = 0
            return df, self.report
            
        initial_rows = len(df)
        
        # 2. Clean Column Names
        df = self._clean_column_names(df)
        
        # 3. Drop exact duplicates
        df = self._remove_duplicates(df, initial_rows)
        
        # 4. Column-level Normalization & Type Inference
        for col in df.columns:
            df[col] = self._normalize_column(df[col], col)
            
        # 5. Fill Missing Values
        df = self._fill_missing_values(df)
        
        # Calculate final quality score
        # Deduct points for duplicates (up to 10), missing values (up to 20), etc.
        score = 100 - self.quality_deductions
        self.report["quality_score"] = max(0, min(100, score))
        
        return df, self.report

    def _clean_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        new_cols = []
        changed = 0
        for col in df.columns:
            orig = str(col)
            # convert to lowercase, replace spaces and special chars with underscores
            clean = re.sub(r'[^a-zA-Z0-9]+', '_', orig).strip('_').lower()
            if not clean:
                clean = "unnamed"
            
            # handle duplicate column names
            base_clean = clean
            counter = 1
            while clean in new_cols:
                clean = f"{base_clean}_{counter}"
                counter += 1
                
            new_cols.append(clean)
            if clean != orig:
                changed += 1
                
        df.columns = new_cols
        self.report["columns_cleaned"] = changed
        return df

    def _remove_duplicates(self, df: pd.DataFrame, initial_rows: int) -> pd.DataFrame:
        before = len(df)
        df.drop_duplicates(inplace=True)
        after = len(df)
        dups = before - after
        self.report["duplicate_rows_removed"] = dups
        
        if dups > 0:
            pct = (dups / initial_rows) * 100
            self.report["duplicate_percentage"] = round(pct, 2)
            self.quality_deductions += min(10, int(pct / 2))
            
        return df

    def _normalize_column(self, series: pd.Series, col_name: str) -> pd.Series:
        # Detect if empty
        if series.isna().all():
            self.report["validation_errors"].append(f"Column '{col_name}' contains all NULL values.")
            self.quality_deductions += 5
            self.report["inferred_types"][col_name] = "null"
            return series

        # Convert to string for regex checks if object
        if series.dtype == 'object':
            # Clean whitespaces
            series = series.apply(lambda x: x.strip() if isinstance(x, str) else x)
            
            # Replace common missing value string representations with NaN
            missing_vals = ["", "N/A", "n/a", "NA", "na", "-", "None", "null", "NULL"]
            series.replace(missing_vals, np.nan, inplace=True)
            
            non_nulls = series.dropna()
            if len(non_nulls) == 0:
                self.report["inferred_types"][col_name] = "null"
                return series
                
            sample = non_nulls.astype(str)
            
            # Check Boolean
            bool_map = {"yes": True, "no": False, "true": True, "false": False, "1": True, "0": False, "y": True, "n": False}
            if sample.str.lower().isin(bool_map.keys()).all():
                series = series.astype(str).str.lower().map(bool_map)
                self.report["inferred_types"][col_name] = "boolean"
                self.report["data_types_corrected"] += 1
                return series
                
            # Check Currency
            # Matches optional minus, currency symbol ($, €, £, ₹, etc), numbers with commas, optional decimals
            currency_pattern = r'^[-]?[\$€£₹¥]?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^[-]?\d+(?:\.\d+)?\s*[\$€£₹¥]$'
            if sample.str.match(currency_pattern).mean() > 0.8: # If 80%+ match
                # Clean and convert
                clean_series = series.astype(str).str.replace(r'[^\d\.-]', '', regex=True)
                series = pd.to_numeric(clean_series, errors='coerce')
                self.report["currencies_normalized"] += 1
                self.report["inferred_types"][col_name] = "currency"
                return series
                
            # Check Percentage
            pct_pattern = r'^[-]?\d+(?:\.\d+)?\s*%$'
            if sample.str.match(pct_pattern).mean() > 0.8:
                clean_series = series.astype(str).str.replace('%', '').str.strip()
                series = pd.to_numeric(clean_series, errors='coerce') / 100.0
                self.report["data_types_corrected"] += 1
                self.report["inferred_types"][col_name] = "percentage"
                return series
                
            # Check Date
            try:
                # pandas to_datetime is very good at inferring
                date_series = pd.to_datetime(series, errors='coerce')
                # If more than 50% are valid dates and not just numbers parsed as timestamps
                if date_series.notna().mean() > 0.5 and not sample.str.isnumeric().all():
                    self.report["dates_standardized"] += 1
                    self.report["inferred_types"][col_name] = "date"
                    return date_series
            except:
                pass
                
            # Check Email
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if sample.str.match(email_pattern).mean() > 0.8:
                self.report["inferred_types"][col_name] = "email"
                return series.str.lower()
                
            # Text Standardization (Title case for low cardinality categorical)
            if series.nunique() < len(series) * 0.5 or series.nunique() <= 20: # categorical-like
                series = series.apply(lambda x: x.title() if isinstance(x, str) else x)
                self.report["inferred_types"][col_name] = "category"
            else:
                self.report["inferred_types"][col_name] = "text"
                
            return series
            
        else:
            # Numeric types
            if pd.api.types.is_bool_dtype(series):
                self.report["inferred_types"][col_name] = "boolean"
            elif pd.api.types.is_integer_dtype(series):
                self.report["inferred_types"][col_name] = "integer"
            elif pd.api.types.is_float_dtype(series):
                self.report["inferred_types"][col_name] = "float"
            elif pd.api.types.is_datetime64_any_dtype(series):
                self.report["inferred_types"][col_name] = "date"
            else:
                self.report["inferred_types"][col_name] = "unknown"
                
            return series

    def _fill_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        missing_count = df.isna().sum().sum()
        if missing_count == 0:
            return df
            
        self.report["missing_values_filled"] = int(missing_count)
        total_cells = df.shape[0] * df.shape[1]
        missing_pct = (missing_count / total_cells) * 100
        self.quality_deductions += min(20, int(missing_pct))
        
        for col in df.columns:
            if df[col].isna().any():
                col_type = self.report["inferred_types"].get(col, "")
                
                if col_type in ["integer", "float", "currency", "percentage"]:
                    median_val = df[col].median()
                    if not pd.isna(median_val):
                        df[col] = df[col].fillna(median_val)
                elif col_type == "date":
                    # Preserve missing dates
                    pass
                elif col_type in ["boolean", "category", "text", "email"]:
                    mode_vals = df[col].mode()
                    if not mode_vals.empty:
                        df[col] = df[col].fillna(mode_vals[0])
                else:
                    # Generic fallback for object
                    if df[col].dtype == 'object':
                        mode_vals = df[col].mode()
                        if not mode_vals.empty:
                            df[col] = df[col].fillna(mode_vals[0])
                        else:
                            df[col] = df[col].fillna("Unknown")
                    else:
                        median_val = df[col].median()
                        if not pd.isna(median_val):
                            df[col] = df[col].fillna(median_val)
                            
        return df

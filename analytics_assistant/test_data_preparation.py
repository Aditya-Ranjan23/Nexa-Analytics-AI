import pandas as pd
import numpy as np
from django.test import TestCase
from analytics_assistant.data_preparation import SmartDataPreparationEngine

class DataPreparationTests(TestCase):
    def setUp(self):
        self.engine = SmartDataPreparationEngine()
        
    def test_clean_column_names(self):
        df = pd.DataFrame({
            "Sales Amount ": [1, 2],
            "Order-Date!!": ["2023", "2024"],
            "Duplicate": [1, 2],
            "DUPLICATE": [3, 4]
        })
        
        cleaned_df, report = self.engine.prepare(df)
        cols = list(cleaned_df.columns)
        
        self.assertIn("sales_amount", cols)
        self.assertIn("order_date", cols)
        self.assertIn("duplicate", cols)
        self.assertIn("duplicate_1", cols)
        self.assertEqual(report["columns_cleaned"], 4)
        
    def test_missing_values(self):
        df = pd.DataFrame({
            "nums": [1.0, np.nan, 3.0, 4.0, 5.0],
            "cats": ["Apple", "", "N/A", "Apple", "Banana"],
            "dates": pd.to_datetime(["2023-01-01", None, "2023-01-03", "2023-01-04", "2023-01-05"])
        })
        
        cleaned_df, report = self.engine.prepare(df)
        
        # median of 1, 3, 4, 5 is 3.5
        self.assertEqual(cleaned_df["nums"].iloc[1], 3.5)
        
        # Mode of ["Apple", "Apple", "Banana"] is "Apple"
        self.assertEqual(cleaned_df["cats"].iloc[1], "Apple")
        self.assertEqual(cleaned_df["cats"].iloc[2], "Apple")
        
        # Dates should be preserved
        self.assertTrue(pd.isna(cleaned_df["dates"].iloc[1]))
        
        self.assertEqual(report["missing_values_filled"], 4)
        self.assertEqual(report["inferred_types"]["nums"], "float")
        
    def test_currency_percentage_boolean(self):
        df = pd.DataFrame({
            "money": ["$1,000.50", "€2,500", "₹500.00", "-$100"],
            "pct": ["75%", "100 %", "-5.5%", "0%"],
            "bools": ["Yes", "NO", "true", "0"]
        })
        
        cleaned_df, report = self.engine.prepare(df)
        
        self.assertEqual(list(cleaned_df["money"]), [1000.5, 2500.0, 500.0, -100.0])
        self.assertEqual(list(cleaned_df["pct"]), [0.75, 1.0, -0.055, 0.0])
        self.assertEqual(list(cleaned_df["bools"]), [True, False, True, False])
        
        self.assertEqual(report["inferred_types"]["money"], "currency")
        self.assertEqual(report["inferred_types"]["pct"], "percentage")
        self.assertEqual(report["inferred_types"]["bools"], "boolean")

    def test_duplicates(self):
        df = pd.DataFrame({
            "colA": [1, 1, 2, 3],
            "colB": ["A", "A", "B", "C"]
        })
        
        cleaned_df, report = self.engine.prepare(df)
        self.assertEqual(len(cleaned_df), 3)
        self.assertEqual(report["duplicate_rows_removed"], 1)
        self.assertEqual(report["duplicate_percentage"], 25.0)

    def test_text_standardization(self):
        df = pd.DataFrame({
            "fruit": [" apple ", "APPLE", "Apple", "banana"]
        })
        
        cleaned_df, report = self.engine.prepare(df)
        # title cased and stripped
        self.assertEqual(list(cleaned_df["fruit"]), ["Apple", "Apple", "Apple", "Banana"])

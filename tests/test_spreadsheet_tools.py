"""spreadsheet-sort, spreadsheet-conditional-format and spreadsheet-data-validation (C-05).

WPS is simulated: each stand-in makes the change with openpyxl and saves, the way WPS would, so the offline
read-back runs on a real package.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, Rule
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.worksheet.datavalidation import DataValidation

from wps_ai_agent_cli import spreadsheet_tools as tools
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.sessions import register_document

SHEET = "销售"
ROWS = [["地区", "销量", "日期"], ["华东", 120, 3], ["华南", 90, 1], ["西北", 150, 2], ["华北", 90, 4]]


def wps_sort(*, scramble=False, drop_row=False):
    def run_com(path, sheet_name, range_address, keys, has_header):
        workbook = load_workbook(path)
        sheet = workbook[sheet_name]
        rows = [[cell.value for cell in row] for row in sheet[range_address]]
        head, body = (rows[:1], rows[1:]) if has_header else ([], rows)
        min_col = sheet[range_address][0][0].column
        for key in reversed(keys):
            body.sort(key=lambda row, k=key: row[k["column"] - min_col], reverse=key["descending"])
        if scramble:
            body.reverse()
        if drop_row:
            body[-1] = [None] * len(body[-1])
        for target, values in zip(sheet[range_address], head + body, strict=True):
            for cell, value in zip(target, values, strict=True):
                cell.value = value
        workbook.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps", "sorted_rows": len(rows)}}

    return run_com


def wps_format(*, wrong_operator=False):
    def run_com(path, sheet_name, params):
        workbook = load_workbook(path)
        sheet = workbook[sheet_name]
        cells = params["range"]
        if params["replace"]:
            sheet.conditional_formatting._cf_rules.pop(
                next((key for key in sheet.conditional_formatting._cf_rules if str(key.sqref) == cells), None), None
            )
        kind = params["kind"]
        if kind == "cell-value":
            names = {number: name for number, name in tools.OPERATORS.values()}
            operator = "lessThan" if wrong_operator else names[params["operator"]]
            formula = [tools._stored(params["formula1"])] + (
                [tools._stored(params["formula2"])] if params["formula2"] else []
            )
            rule = CellIsRule(operator=operator, formula=formula)
        elif kind == "color-scale":
            rule = ColorScaleRule(start_type="min", start_color="F8696B", end_type="max", end_color="63BE7B")
        elif kind == "data-bar":
            rule = DataBarRule(start_type="min", end_type="max", color="638EC6")
        else:
            rule = Rule(type="duplicateValues", dxf=DifferentialStyle())
        sheet.conditional_formatting.add(cells, rule)
        workbook.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps"}}

    return run_com


def wps_validate(*, wrong_values=False):
    def run_com(path, sheet_name, params):
        workbook = load_workbook(path)
        sheet = workbook[sheet_name]
        names = {number: name for number, name in tools.VALIDATION_TYPES.values()}
        operators = {number: name for number, name in tools.OPERATORS.values()}
        kind = names[params["type"]]
        formula1 = params["formula1"]
        formula1 = f'"{formula1}"' if kind == "list" and not formula1.startswith("=") else tools._stored(formula1)
        if wrong_values:
            formula1 = '"x"' if kind == "list" else "999"
        sheet.data_validations.dataValidation = [
            item for item in sheet.data_validations.dataValidation if params["range"] not in str(item.sqref).split()
        ]
        validation = DataValidation(
            type=kind,
            operator=operators.get(params["operator"]),
            formula1=formula1,
            formula2=tools._stored(params["formula2"]) if params["formula2"] else None,
            allow_blank=params["allow_blank"],
        )
        validation.add(params["range"])
        sheet.add_data_validation(validation)
        workbook.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps"}}

    return run_com


class SheetToolTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.workspace = root / "ws"
        self.workspace.mkdir()
        self.path = root / "book.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = SHEET
        for row in ROWS:
            sheet.append(row)
        sheet["F1"] = "=SUM(B2:B5)"
        workbook.save(self.path)
        self.register()

    def register(self):
        ok, record, errors = register_document("spreadsheets", str(self.path), self.workspace)
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]

    def values(self, cells="A1:C5"):
        sheet = load_workbook(self.path)[SHEET]
        return [[cell.value for cell in row] for row in sheet[cells]]

    # -------------------------------------------------------------------------------------------------- sort
    def sort(self, keys, com=None, request_id="s1", **options):
        with patch.object(tools, "_run_sort_com", side_effect=com or wps_sort()) as fake:
            outcome = tools.sort_spreadsheet_range(
                self.document_id,
                SHEET,
                options.pop("cells", "A1:C5"),
                keys,
                request_id,
                workspace=self.workspace,
                **options,
            )
        self.calls = fake.call_args_list
        return outcome

    def test_sort_by_a_number_then_a_header_name(self):
        ok, result, errors, _ = self.sort(["B:desc", "日期:asc"])
        self.assertTrue(ok, errors)
        self.assertEqual([row[0] for row in self.values()[1:]], ["西北", "华东", "华南", "华北"])
        self.assertEqual(result["read_back"]["order_check"], "strict")
        self.assertEqual(result["sort_keys"], [{"column": "B", "order": "desc"}, {"column": "C", "order": "asc"}])
        self.assertEqual(self.calls[0].args[3][1]["letter"], "C")

    def test_a_text_key_is_checked_for_grouping_only(self):
        ok, result, errors, _ = self.sort(["A:asc"])
        self.assertTrue(ok, errors)
        self.assertEqual(result["read_back"]["order_check"], "text keys: grouping only")

    def test_a_wrong_order_or_a_lost_row_is_rolled_back(self):
        before = self.path.read_bytes()
        for index, com in enumerate((wps_sort(scramble=True), wps_sort(drop_row=True))):
            with self.subTest(index=index):
                ok, result, errors, _ = self.sort(["B:asc"], com=com, request_id=f"bad{index}")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
                self.assertTrue(result["rollback"]["performed"], result.get("rollback"))
                self.assertEqual(self.path.read_bytes(), before)

    def test_sort_refusals_stop_before_wps(self):
        workbook = load_workbook(self.path)
        workbook[SHEET]["C3"] = "=1+1"
        workbook[SHEET].merge_cells("A7:B7")
        workbook.save(self.path)
        self.register()
        cases = [
            ({"keys": ["B:asc"]}, "SORT_RANGE_HAS_FORMULAS"),
            ({"keys": ["B:asc"], "cells": "A6:B8"}, "INVALID_RANGE"),  # merged cells
            ({"keys": ["Z:asc"], "cells": "A1:B5"}, "INVALID_ARGUMENT"),
            ({"keys": ["B:sideways"], "cells": "A1:B5"}, "INVALID_ARGUMENT"),
            ({"keys": ["A:asc", "B:asc", "A:desc", "B:desc"], "cells": "A1:B5"}, "INVALID_ARGUMENT"),
            ({"keys": ["B:asc"], "cells": "A1:B2"}, "INVALID_RANGE"),
            ({"keys": ["B:asc"], "cells": "A:B"}, "INVALID_RANGE"),
        ]
        for index, (options, code) in enumerate(cases):
            with self.subTest(code=code, options=options):
                ok, _result, errors, _ = self.sort(options.pop("keys"), request_id=f"r{index}", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                self.assertEqual(self.calls, [])

    def test_reading_wps_extensions_prints_no_openpyxl_warning(self):
        import warnings

        def warn_like_openpyxl(*args, **kwargs):
            warnings.warn(
                "Conditional Formatting extension is not supported and will be removed", UserWarning, stacklevel=2
            )
            return load_workbook(self.path)

        with (
            patch.object(tools, "load_workbook_guarded", side_effect=warn_like_openpyxl),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            tools._load(self.path).close()
        self.assertEqual(caught, [])

    def test_check_sorted_treats_blanks_as_last(self):
        keys = [{"column": 1, "letter": "A", "descending": False}]
        self.assertEqual(tools.check_sorted([(1,), (2,), (None,)], keys, 1), (True, "strict"))
        self.assertFalse(tools.check_sorted([(None,), (1,)], keys, 1)[0])
        self.assertFalse(tools.check_sorted([("a",), ("b",), ("a",)], keys, 1)[0])

    # -------------------------------------------------------------------------------------- conditional format
    def fmt(self, kind, com=None, request_id="f1", **options):
        with patch.object(tools, "_run_conditional_format_com", side_effect=com or wps_format()) as fake:
            outcome = tools.add_conditional_format(
                self.document_id,
                SHEET,
                options.pop("cells", "B2:B5"),
                kind,
                request_id,
                workspace=self.workspace,
                **options,
            )
        self.calls = fake.call_args_list
        return outcome

    def test_each_kind_of_conditional_format_reads_back(self):
        cases = [
            ("cell-value", {"operator": "greater", "value1": "100"}),
            ("cell-value", {"operator": "between", "value1": 90, "value2": "=MAX(B2:B5)"}),
            ("cell-value", {"operator": "equal", "value1": "华东", "cells": "A2:A5"}),
            ("color-scale", {}),
            ("data-bar", {}),
            ("duplicates", {"cells": "A2:A5"}),
        ]
        for index, (kind, options) in enumerate(cases):
            with self.subTest(kind=kind, options=options):
                ok, result, errors, _ = self.fmt(kind, request_id=f"k{index}", **dict(options))
                self.assertTrue(ok, errors)
                self.assertTrue(all(result["checks"].values()), result["checks"])
        params = self.calls[0].args[2]
        self.assertEqual(params["kind"], "duplicates")

    def test_text_and_formula_values_are_passed_the_way_wps_takes_them(self):
        ok, _result, errors, _ = self.fmt("cell-value", operator="equal", value1='说"好"', cells="A2:A5")
        self.assertTrue(ok, errors)
        self.assertEqual(self.calls[0].args[2]["formula1"], '="说""好"""')

    def test_a_rule_that_reads_back_wrong_is_rolled_back(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.fmt(
            "cell-value", com=wps_format(wrong_operator=True), operator="greater", value1=1
        )
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
        self.assertEqual(self.path.read_bytes(), before)

    def test_replace_leaves_one_rule_on_the_range(self):
        ok, _r, errors, _ = self.fmt("cell-value", operator="greater", value1=1, request_id="a")
        self.assertTrue(ok, errors)
        ok, result, errors, _ = self.fmt("data-bar", replace=True, request_id="b")
        self.assertTrue(ok, errors)
        self.assertEqual(len(result["read_back"]["rules_on_range"]), 1)

    def test_conditional_format_refusals(self):
        cases = [
            ({"kind": "rainbow"}, "INVALID_ARGUMENT"),
            ({"kind": "cell-value"}, "INVALID_ARGUMENT"),  # no operator
            ({"kind": "cell-value", "operator": "between", "value1": 1}, "INVALID_ARGUMENT"),
            (
                {"kind": "cell-value", "operator": "greater", "value1": '=WEBSERVICE("u")'},
                "FORMULA_FUNCTION_NOT_ALLOWED",
            ),
            ({"kind": "duplicates", "fill_color": "red"}, "INVALID_ARGUMENT"),
            ({"kind": "color-scale", "color_scale_points": 4}, "INVALID_ARGUMENT"),
        ]
        for index, (options, code) in enumerate(cases):
            with self.subTest(code=code, options=options):
                ok, _result, errors, _ = self.fmt(options.pop("kind"), request_id=f"x{index}", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                self.assertEqual(self.calls, [])

    # ---------------------------------------------------------------------------------------- data validation
    def validate(self, kind, com=None, request_id="v1", **options):
        with patch.object(tools, "_run_validation_com", side_effect=com or wps_validate()) as fake:
            outcome = tools.set_data_validation(
                self.document_id,
                SHEET,
                options.pop("cells", "D2:D9"),
                kind,
                request_id,
                workspace=self.workspace,
                **options,
            )
        self.calls = fake.call_args_list
        return outcome

    def test_each_validation_type_reads_back(self):
        cases = [
            ("list", {"values": ["已完成", "进行中", "未开始"]}),
            ("list", {"values": ["=$H$1:$H$3"]}),
            ("whole", {"operator": "between", "value1": 1, "value2": "100"}),
            ("decimal", {"operator": "greater", "value1": "0.5"}),
            ("date", {"operator": "greater-or-equal", "value1": "2026-01-01"}),
            ("text-length", {"operator": "less-or-equal", "value1": 20}),
        ]
        for index, (kind, options) in enumerate(cases):
            with self.subTest(kind=kind, options=options):
                ok, result, errors, _ = self.validate(kind, request_id=f"t{index}", **dict(options))
                self.assertTrue(ok, errors)
                self.assertTrue(all(result["checks"].values()), result["checks"])
        self.assertEqual(self.calls[0].args[2]["formula1"], "20")

    def test_a_date_is_given_to_wps_as_a_date_formula_and_read_back_as_a_serial(self):
        ok, _result, errors, _ = self.validate("date", operator="greater", value1="2026-01-01")
        self.assertTrue(ok, errors)
        self.assertEqual(self.calls[0].args[2]["formula1"], "=DATE(2026,1,1)")
        self.assertTrue(tools._same_formula("46023", "DATE(2026,1,1)", "date"))

    def test_a_validation_that_reads_back_wrong_is_rolled_back(self):
        before = self.path.read_bytes()
        ok, result, errors, _ = self.validate("list", com=wps_validate(wrong_values=True), values=["是", "否"])
        self.assertFalse(ok)
        self.assertFalse(result["checks"]["values_match"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_validation_refusals(self):
        cases = [
            ("list", {}, "INVALID_ARGUMENT"),
            ("list", {"values": ["a,b"]}, "INVALID_ARGUMENT"),
            ("whole", {"operator": "between", "value1": 1}, "INVALID_ARGUMENT"),
            ("date", {"value1": "明天", "value2": "2026-01-02"}, "INVALID_ARGUMENT"),
            ("colour", {}, "INVALID_ARGUMENT"),
        ]
        for index, (kind, options, code) in enumerate(cases):
            with self.subTest(kind=kind, options=options):
                ok, _result, errors, _ = self.validate(kind, request_id=f"n{index}", **options)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                self.assertEqual(self.calls, [])

    def test_dry_runs_change_nothing(self):
        before = self.path.read_bytes()
        with patch.object(tools, "create_backup") as backup:
            self.assertTrue(self.sort(["B:asc"], dry_run=True)[0])
            self.assertTrue(self.fmt("data-bar", dry_run=True)[0])
            self.assertTrue(self.validate("list", values=["a"], dry_run=True)[0])
        backup.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)


class CliTests(unittest.TestCase):
    def test_repeated_keys_and_values_reach_the_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                Workbook().save("b.xlsx")
                ok, record, _ = register_document("spreadsheets", "b.xlsx")
                document = record["document_id"]
                outputs = []
                with (
                    patch("wps_ai_agent_cli.cli_spreadsheet.sort_spreadsheet_range") as sort,
                    patch("wps_ai_agent_cli.cli_spreadsheet.set_data_validation") as validate,
                ):
                    sort.return_value = (True, {"normalized_range": "A1:B3"}, [], False)
                    validate.return_value = (True, {"normalized_range": "D2:D9"}, [], False)
                    for argv in (
                        [
                            "spreadsheet-sort",
                            "--document-id",
                            document,
                            "--sheet-name",
                            "S",
                            "--range",
                            "A1:B3",
                            "--key",
                            "B:desc",
                            "--key",
                            "名称:asc",
                            "--no-header",
                        ],
                        [
                            "spreadsheet-data-validation",
                            "--document-id",
                            document,
                            "--sheet-name",
                            "S",
                            "--range",
                            "D2:D9",
                            "--type",
                            "list",
                            "--value",
                            "是",
                            "--value",
                            "否",
                            "--no-blank",
                        ],
                    ):
                        stream = io.StringIO()
                        outputs.append((run(argv, output_stream=stream), json.loads(stream.getvalue())))
            finally:
                os.chdir(previous)
        self.assertEqual([code for code, _ in outputs], [0, 0], outputs)
        self.assertEqual(sort.call_args.args[3], ["B:desc", "名称:asc"])
        self.assertFalse(sort.call_args.kwargs["has_header"])
        self.assertEqual(validate.call_args.kwargs["values"], ["是", "否"])
        self.assertFalse(validate.call_args.kwargs["allow_blank"])


if __name__ == "__main__":
    unittest.main()

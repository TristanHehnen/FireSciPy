# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from io import StringIO

import pandas as pd

from .base import InstrumentFile


def read_mettler_toledo_sta_file(file_path):
    """
    Convenience wrapper around MettlerToledoSTAParser.
    """
    parser = MettlerToledoSTAParser(file_path=file_path)
    return parser.parse()


class MettlerToledoSTAParser:
    """
    Parser for Mettler Toledo STA/TGA/DSC ASCII export files.

    Expected structure
    ------------------
    - Optional metadata lines before the column header
    - Column header line: whitespace-separated column names, first column is "Index"
    - Units line: whitespace-separated unit tokens in brackets, e.g. "[#]", "[°C]"
    - Data rows: fixed-width, whitespace-separated, decimal point "."

    Example
    -------
             Index            Ts             t        Weight            Tr
               [#]          [°C]           [s]          [mg]          [°C]
                 0   3.06123e+01   0.00000e+00   9.99916e-01   3.00000e+01
                 1   3.15754e+01   1.00000e+00   9.99893e-01   3.00000e+01
    ...
    """

    SEPARATOR = r"\s+"
    DECIMAL = "."

    def __init__(self, file_path, instrument_file=None):
        """
        Parameters
        ----------
        file_path : str or Path
            Path to the Mettler Toledo export file.
        instrument_file : InstrumentFile, optional
            Pre-loaded InstrumentFile instance. If None, one is created.
        """
        self.file_path = file_path
        self.file = instrument_file or InstrumentFile(file_path).read()

        self.meta = dict()
        self.data_df = None

        self._column_names = None
        self._header_idx = None

    def parse(self):
        """
        Parse column header, units, and measurement table.

        Returns
        -------
        meta : dict
            Parsed metadata including "UNITS" and "USED_ENCODING".
        data_df : pandas.DataFrame
            Parsed measurement table.
        """
        self._find_and_parse_header()
        self._parse_data_table()

        self.meta["USED_ENCODING"] = self.file.used_encoding
        return self.meta, self.data_df

    def _find_and_parse_header(self):
        """
        Locate the "Index" column header line, parse column names and units.
        """
        for idx, line in enumerate(self.file.lines):
            if line.strip().startswith("Index"):
                self._header_idx = idx
                break

        if self._header_idx is None:
            raise ValueError(
                "Could not find column header line starting with 'Index'."
            )

        # Column names are whitespace-separated tokens on the header line.
        self._column_names = self.file.lines[self._header_idx].split()

        # Units are on the next line, formatted as "[unit]" tokens.
        units_idx = self._header_idx + 1
        if units_idx < len(self.file.lines):
            unit_tokens = self.file.lines[units_idx].split()
            self.meta["UNITS"] = {
                col: tok.strip("[]")
                for col, tok in zip(self._column_names, unit_tokens)
            }

    def _parse_data_table(self):
        """
        Parse measurement data rows below the units line.
        """
        data_start = self._header_idx + 2
        data_lines = self.file.lines[data_start:]

        # Strip leading/trailing whitespace from each line so that the leading
        # padding does not create an empty first column when split on \s+.
        table_text = "\n".join(
            line.strip() for line in data_lines if line.strip()
        )

        self.data_df = pd.read_csv(
            StringIO(table_text),
            sep=self.SEPARATOR,
            decimal=self.DECIMAL,
            header=None,
            names=self._column_names,
            engine="python",
            skip_blank_lines=True,
        )

        self.data_df = self.data_df.dropna(axis=1, how="all")
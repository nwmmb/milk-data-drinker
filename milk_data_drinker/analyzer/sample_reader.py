import csv
import logging
import pandas as pd
from io import StringIO


class SampleReader:
    def __init__(self, csvreader):
        self.csvreader = csvreader
        self.chunk = []
        self.name = ""
        self.type = ""
        self.macro_names = []
        self.replicates = pd.DataFrame()
        self.date = ""
        self.end_of_file = False

    def read_sample(self):
        self.get_chunk()
        self.get_name()
        self.get_type()
        self.get_macro_names()
        self.get_date()
        self.get_all_replicates()
        return self.replicates

    def setup(self):
        if self.chunk == []:
            self.get_chunk()
        if self.name == "":
            self.get_name()
        if self.type == "":
            self.get_type()
        if self.macro_names == []:
            self.get_macro_names()

    def get_chunk(self):
        self.chunk.clear()
        blank_flag = 0
        line_count = -1
        while blank_flag < 2:
            try:
                self.chunk.append(next(self.csvreader))
            except StopIteration:
                logging.debug("Reached end of file, processing last sample")
                self.end_of_file = True
                blank_flag = 2
            else:
                line_count += 1
                if self.chunk[line_count][0] == '':
                    blank_flag += 1

    def get_name(self):
        self.name = self.chunk[0][0]

    def get_type(self):
        self.type = self.chunk[0][2]

    def get_macro_names(self):
        self.macro_names.clear()
        for cell in self.chunk[1]:
            if cell != "":
                self.macro_names.append(cell)

    def get_all_replicates(self):
        self.setup()
        self.get_date()
        replicates_list = []
        for row in self.chunk:
            if row[0] != self.name and row[0] != "" and row[0] != "Replicate":
                replicates_list.append(self.get_replicate_from_row(row))
        self.replicates = pd.DataFrame(replicates_list)

    def get_replicate_from_row(self, current_row):
        self.setup()
        self.get_date()
        macros = [self.get_macronutrient(current_row, i + 1) for i in range(len(self.macro_names))]
        row_data = [("Name", self.name), ("Type", self.type), ("Date", self.date), ("Replicate", current_row[0])]
        row_data.extend(macros)
        return dict(row_data)

    def get_macronutrient(self, current_row, column_index):
        return (self.macro_names[column_index - 1], current_row[column_index])

    def get_date(self):
        self.setup()
        self.date = ""
        date_column_index = 3 + len(self.macro_names)
        for row in self.chunk:
            if date_column_index < len(row) and ":" in row[date_column_index]:
                self.date = row[date_column_index]

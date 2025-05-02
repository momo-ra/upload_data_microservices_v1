# File Parsers (utils/file_parser.py)
import pandas as pd
import xmltodict
import json
import io

def parse_csv(contents):
    return pd.read_csv(io.BytesIO(contents))

def parse_xml(contents):
    data_dict = xmltodict.parse(contents)
    return pd.DataFrame(data_dict["root"]["record"])

def parse_json(contents):
    data = json.loads(contents)
    return pd.DataFrame(data)

def parse_excel(contents):
    return pd.read_excel(io.BytesIO(contents))

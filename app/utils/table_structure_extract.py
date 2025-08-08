import requests

def format_table_for_api(table):
    header = table.get("header", [])
    rows = table.get("rows", [])
    if not header or not rows or not rows[0]:
        return []
    first_row = rows[0]
    result = [f'{h}("{str(d)}")' for h, d in zip(header, first_row)]
    return result

def get_table_structure_from_api(table, api_url="http://127.0.0.1:8080/infer_table_structure"):
    payload = {"table_header": format_table_for_api(table)}
    response = requests.post(api_url, json=payload)
    response.raise_for_status()
    return response.json().get("table_structure", [])
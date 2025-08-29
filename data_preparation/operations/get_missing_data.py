import pandas as pd
import requests
from fieds import WOS_FIELDS as fields
from fieds import CROSSREF_AVAILABLE_FIELDS as crossref_fields
from fieds import REFERENCE_FIELDS as reference_fields

def get_field_from_api(crossref_field, search_term):
    breakpoint()
    url = "https://api.crossref.org/works/" + search_term
    try:
        response = requests.get(url,timeout=10)
        response.raise_for_status()
        data = response.json()
        items = data['message']
        if items:
            return items[crossref_field]
    except requests.RequestException as e:
        print(f"Request failed for search of: {search_term}\nError: {e}")
        return None        

def parse_references(references):
    breakpoint()
    references_line = ""
    for reference in references:
        reference_text = ""
        for reference_field in reference_fields:
            if reference_field in reference:
                reference_text = reference_text + reference[reference_field] + ", "
        if not reference_text:
            continue
        reference_text = reference_text[:-2]
        references_line = references_line + reference_text + "; "
    return references_line

def parse_year(date):
    return date['date-parts'][0][0]

def parse_field_value(crossref_field, field_value, citation_field):
    if crossref_field == "title":
        field_value = field_value[0]
    if crossref_field == "reference":
        if citation_field == 'Article References':
            parse_references(field_value)
        elif citation_field == 'Author References':
            parse_references(field_value)
        field_value = parse_references(field_value)
    if crossref_field == "created":
        field_value = parse_year(field_value)
    return field_value

def fill_missing_field(excel_path, citation_field, output_path):
    breakpoint()
    df = pd.read_excel(excel_path)
    try:
        df = process_each_field(citation_field, df)
    except Exception as e:
        print(f"Unexpected error while processing field {citation_field}: {e}")
    df.to_excel(output_path, index=False)
    print(f"Output saved to {output_path}")

def fill_missing_fields(excel_path, output_path):
    df = pd.read_excel(excel_path)
    for key in crossref_fields:
        try:
            df = process_each_field(key, df)
        except Exception as e:
            print(f"Unexpected error while processing fields: {e}")
        df.to_excel(output_path, index=False)
        print(f"Output saved to {output_path}")

def process_each_field(citation_field, df):
    crossref_field = crossref_fields[citation_field]
    for index, citation in df.iterrows():
        if pd.isna(citation[citation_field]) or str(citation[citation_field]).strip() == '':
            if crossref_field == "DOI":
                search_term = citation["Title"]
            else:
                search_term = citation['DOI']
            try:
                field_value = get_field_from_api(crossref_field, search_term)
                if field_value:
                    field_value = parse_field_value(crossref_field, field_value, citation_field)
                    df.at[index, citation_field] = field_value
                    print(f" → Found %s: {field_value}", citation_field)
                    field_value = None
            except Exception as e:
                print(f"Unexpected error while processing fields: {e}")
            finally:
                continue
                
    return df
    








##Warning: This script takes a long time!
##python3  python3 /Users/i553815/lerning/graphics/biliographic-analysis-on-indicators/data_preparation/operations/main.py fill_missing_field /Users/i553815/lerning/graphics/biliographic-analysis-on-indicators/data_preparation/input_data/allMetadata.xlsx --citation_field "Article References"
##python3  python3 /Users/i553815/lerning/graphics/biliographic-analysis-on-indicators/data_preparation/operations/main.py fill_missing_field /Users/i553815/lerning/graphics/biliographic-analysis-on-indicators/data_preparation/input_data/output_1.xlsx --citation_field "Article References"

import argparse
import argparse
from get_missing_data import fill_missing_field, fill_missing_fields
from file_manager import get_next_output_filename

FUNCTIONS = {
    "fill_missing_field": fill_missing_field,
    "fill_missing_fields": fill_missing_fields
}

CROSSREF_AVAILABLE_FIELDS = {
    'Title': 'title',
    'Abstract': 'abstract',
    'Language': 'language',
    'Article References': 'reference',
    'Author References': 'reference',
    'Times Cited': 'is-referenced-by-count',
    'Publication Year': 'created',
    'DOI': 'DOI'
}




def main():
    parser = argparse.ArgumentParser(description="Run  one of the available operations.")
    subparsers = parser.add_subparsers(dest='function', help="Function to execute")
    parser_wos_to_excel = subparsers.add_parser('wos_to_excel', help='Convert WoS to Excel')
    parser_wos_to_excel.add_argument('input_file', help='Path to the input file')
    parser_excel_to_wos = subparsers.add_parser('excel_to_wos', help='Convert Excel to WoS')
    parser_excel_to_wos.add_argument('input_file', help='Path to the input file')
    fill_missing_fields = subparsers.add_parser('fill_missing_fields', help='Try to fill all of the missing fields using crossref api')
    fill_missing_fields.add_argument('input_file', help='Path to the input file')
    parser_fill_missing_field = subparsers.add_parser('fill_missing_field', help='Fill missing fields')
    parser_fill_missing_field.add_argument('input_file', help='Path to the input file')
    parser_fill_missing_field.add_argument('--citation_field', choices=CROSSREF_AVAILABLE_FIELDS.keys(), required=True, help='Citation field that needs to be filled')
    args = parser.parse_args()
    func = FUNCTIONS[args.function]

    if(args.function == "excel_to_wos"):
        output_file = get_next_output_filename(".txt")
    else:
        output_file = get_next_output_filename(".xlsx")


    try:
        print(f"Running {args.function} with file {args.input_file}...")
        
        if(func == fill_missing_field):
            result = func(args.input_file, args.citation_field, output_file)
        else:
            result = func(args.input_file, output_file)
        print("Output File Created:", output_file)
    except Exception as e:
        print(f"Error During Proccess: {e}")

if __name__ == "__main__":
    main()

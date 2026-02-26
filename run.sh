#!/bin/bash

INPUT_FILE="paperToData_batch0.txt"
PARSED_PMCIDS_FILE="paperToData_batch0_parsed_pmcids.txt"
CSV_OUTPUT_FILE="paperToData_batch0_output.csv"
ERROR_FILE="paperToData_batch0_errors.txt"
EMAIL="asamatt@umich.edu"
MODE="full_text"

python3 ./main.py --input_file $INPUT_FILE --parsed_pmcids_file $PARSED_PMCIDS_FILE \
 --csv_output_file $CSV_OUTPUT_FILE --error_file $ERROR_FILE --email $EMAIL --mode $MODE
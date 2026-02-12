#!/bin/bash

#SBATCH --job-name=paperToData
#SBATCH --account=yongqunh0
#SBATCH --partition=largemem
#SBATCH --time=01-00:00:00
#SBATCH --output=./logs/paperToData_batch0.log
export HTTPS_PROXY=http://proxy.arc-ts.umich.edu:3128
export HTTP_PROXY=http://proxy.arc-ts.umich.edu:3128
export HTTPX_DISABLE_IPV6=1

# --- Debugging: Verify Internet Access ---
echo "Starting job on node: $(hostname)"
echo "Testing connectivity to OpenAI..."
# Replace 'api.openai.com' with your specific LLM provider if different
curl -I https://api.openai.com > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Connection to API successful!"
else
    echo "Connection to API FAILED. Check proxy settings."
fi

set -a
source llm.env
source langchain.env
set +a

INPUT_FILE="paperToData_batch0.txt"
PARSED_PMCIDS_FILE="paperToData_batch0_parsed_pmcids.txt"
CSV_OUTPUT_FILE="paperToData_batch0_output.csv"
ERROR_FILE="paperToData_batch0_errors.txt"
EMAIL="asamatt@umich.edu"
MODE="full_text"

python3 ./main.py --input_file $INPUT_FILE --parsed_pmcids_file $PARSED_PMCIDS_FILE \
 --csv_output_file $CSV_OUTPUT_FILE --error_file $ERROR_FILE --email $EMAIL --mode $MODE
#!/bin/bash

#SBATCH --job-name=paperToData
#SBATCH --account=yongqunh0
#SBATCH --partition=largemem
#SBATCH --time=01-00:00:00
#SBATCH --output=./logs/paperToData_batch0.log

curl -I https://api.umgpt.umich.edu
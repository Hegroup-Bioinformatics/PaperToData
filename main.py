
from paperToData import paperToData
import argparse

def parse_args():
  parser = argparse.ArgumentParser()
  
  parser.add_argument('--input_file', type=str, required=True)
  parser.add_argument('--parsed_pmids_file', type=str, required=True)
  parser.add_argument('--csv_output_file', type=str, required=True)
  parser.add_argument('--error_file', type=str, required=True)
  parser.add_argument('--email', type=str, required=True)
  parser.add_argument('--mode', type=str, choices=['abstract', 'full_text'], required=True)
  
  return parser.parse_args()

def main():
  args = parse_args()
  print("args = ", args)
  
  pipeline = paperToData(args.input_file, args.parsed_pmids_file, args.csv_output_file, args.error_file, args.email, args.mode)
  pipeline.start()

if __name__ == "__main__":
  main()
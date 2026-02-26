from Bio import Entrez
from dotenv import load_dotenv
import os
import requests
import re
import json
import csv
import time
from bs4 import BeautifulSoup
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Load env variables globally once


class paperToData:
    def __init__(self, input_file, parsed_pmids_file, csv_file, error_file, email, mode="full_text"):
        # Setup Directories
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        print(f"Project Root detected as: {self.base_dir}")
        
        self.input_file = os.path.join(self.base_dir, "input", input_file)
        self.parsed_pmids_file = os.path.join(self.base_dir, "parsed", parsed_pmids_file)
        self.csv_file = os.path.join(self.base_dir, "output", csv_file)
        self.error_file = os.path.join(self.base_dir, "error", error_file)
        
        load_dotenv(os.path.join(self.base_dir, "llm.env"))
        load_dotenv(os.path.join(self.base_dir, "langchain.env"))
        
        self.email = email
        self.mode = mode
        self.parsed = self.getParsed()
        self.llm = self.getLLM()
        
        Entrez.email = self.email
        # Ideally set API key if available: Entrez.api_key = os.getenv("NCBI_API_KEY")

        #self.setup_langchain_env()

    def getParsed(self):
        parsed = set()
        if os.path.exists(self.parsed_pmids_file):
            with open(self.parsed_pmids_file, mode="r") as file:
                for line in file:
                    parsed.add(line.strip())
        return parsed

    def getLLM(self):
        print(f"Loading Model: {os.getenv('DEPLOYMENT')}")
        llm = AzureChatOpenAI(
            deployment_name=os.getenv("DEPLOYMENT"),
            openai_api_version=os.getenv("API_VERSION"),
            api_key=os.getenv("API_KEY"),
            azure_endpoint=os.getenv("ENDPOINT"),
            openai_organization=os.getenv("ORGANIZATION"),
            timeout=60,
            temperature=0  # Lower temp for extraction tasks
        )
        print("Model Loaded \n")
        return llm

    def setup_langchain_env(self):
        os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING") or ""
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY") or ""
        os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT") or ""
        print("Langchain Env Configured \n")

    def convert_pmid_to_pmcid(self, pmid):
        # Add sleep to respect rate limits
        time.sleep(0.35) 
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if "records" in data and data["records"]:
                return data["records"][0].get("pmcid", None)
        except Exception as e:
            print(f"Error converting PMID {pmid}: {e}")
        return None

    def fetch_full_text_pmcid(self, pmcid):
        try:
            time.sleep(0.35) # Rate limit
            handle = Entrez.efetch(db="pmc", id=pmcid, rettype="full", retmode="xml")
            response = handle.read()
            handle.close()
            
            # Use BeautifulSoup for robust XML parsing
            soup = BeautifulSoup(response, "xml")
            
            # Extract Abstract
            abstract_tag = soup.find("abstract")
            abstract_text = abstract_tag.get_text(separator=" ", strip=True) if abstract_tag else ""

            # Extract Body (excluding references to save context window)
            body_tag = soup.find("body")
            full_text = body_tag.get_text(separator=" ", strip=True) if body_tag else ""
            
            # Fallback if body is empty but response wasn't
            if not full_text:
                full_text = soup.get_text(separator=" ", strip=True)

            if not full_text:
                raise ValueError("Extracted text is empty")

            
            
            self.parsed.add(pmcid)
            return abstract_text, full_text

        except Exception as e:
            print(f"Error fetching {pmcid}: {e}")
            with open(self.error_file, mode="a") as file:
                file.write(f"{pmcid} failed to fetch/clean: {e}\n")
            return None, None

    def fetch_abstract(self, pmid):
        time.sleep(0.35)
        handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="xml")
        response = handle.read()
        handle.close()
        soup = BeautifulSoup(response, "xml")
        return soup.get_text(separator=" ", strip=True)

    def create_text_json(self, text):
        # Truncate text if it's too long for the LLM context window
        # Adjust 15000 chars based on your model's token limit
        truncated_text = text[:60000] 

        parser = JsonOutputParser()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a helpful assistant that extracts information from a PubMed article and formats it as JSON. 
            Your task is to only produce a JSON object from a vaccine design article.
            
            Return ONLY the JSON. Do not include markdown formatting like ```json ... ```.

            Keys required:
            - vaccine_name
            - vaccine_name_generated (boolean)
            - vaccine_target_pathogen
            - vaccine_target_host
            - vaccine_model_host
            - vaccine_delivery_method
            - vaccine_manufacturer
            - vaccine_storage_method
            - vaccine_stage (research, clinical, or licensed)
            - vaccine_license
            - vaccine_antigen
            - vaccine_formulation
            - vaccine_gene

            If information is missing, use an empty string "".
            """),
            ("human", "{text}")
        ])

        chain = prompt | self.llm | parser
        
        try:
            return chain.invoke({"text": truncated_text})
        except Exception as e:
            print(f"LLM extraction failed: {e}")
            return None

    def merge_json(self, data_dict):
        fieldnames = ["pmid", "paper_type", "vaccine_name", "vaccine_name_generated", 
                      "vaccine_target_pathogen", "vaccine_target_host", "vaccine_model_host", 
                      "vaccine_delivery_method", "vaccine_manufacturer", "vaccine_storage_method", 
                      "vaccine_stage", "vaccine_license", "vaccine_antigen", 
                      "vaccine_formulation", "vaccine_gene"]
        
        # Check if file exists to determine if we write the header
        file_exists = os.path.isfile(self.csv_file)
        
        with open(self.csv_file, 'a', newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            # Ensure only relevant keys are written
            clean_row = {k: data_dict.get(k, "") for k in fieldnames}
            writer.writerow(clean_row)

    def retrieve_data(self, pmid):
        pmid = pmid.strip()
        if not pmid: return

        pmcid = ""
        if self.mode == "full_text":
            pmcid = self.convert_pmid_to_pmcid(pmid)
        
        if pmid and pmid not in self.parsed:
            print(f"Processing {pmid}...")
            
            full_text_content = ""

            if self.mode == "full_text":
                if not pmcid:
                    with open(self.error_file, mode="a") as file:
                        file.write(f"{pmid} failed to convert\n")
                    return
            
            if self.mode == "full_text":
                abstract, full_text = self.fetch_full_text_pmcid(pmcid)
                if not full_text: return
                full_text_content = full_text
            else:
                full_text_content = self.fetch_abstract(pmid)
            
            # Get JSON from LLM
            extracted_data = self.create_text_json(full_text_content)
            
            if extracted_data:
                if isinstance(extracted_data, list):
                    if len(extracted_data) > 0:
                        extracted_data = extracted_data[0]
                    else:
                        print("empty list return")
                        return
                if not isinstance(extracted_data, dict):
                    print(f"recived extracted data of type {type(extracted_data)}")
                    return
                extracted_data["pmid"] = pmid
                extracted_data["paper_type"] = self.mode
                self.merge_json(extracted_data)
                
                # Update parsed file
                with open(self.parsed_pmids_file, "a") as f:
                    f.write(pmid + "\n")
        
        elif not pmcid:
            with open(self.error_file, mode="a") as file:
                file.write(f"{pmid} failed to convert to PMCID\n")
        else:
            print(f"Skipping {pmid}, already parsed.")

    def start(self):
        count = 0
        if not os.path.exists(self.input_file):
            print(f"Input file not found: {self.input_file}")
            return

        with open(self.input_file, mode="r") as file:
            for line in file:
                self.retrieve_data(line)
                count += 1
                if count % 10 == 0:
                    print(f"Processed {count} papers...")
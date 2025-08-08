# Utils module
import ast
import re

import sys
import os

import datetime
import concurrent.futures
from dateutil.parser import parse as date_parse
from typing import Union, List, Any


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openai_api.openai_client import OpenAIClient

from utils.sql_skeleton_extract import generate_sql_skeleton
from utils.table_structure_extract import get_table_structure_from_api
from utils.question_skeleton_extract import deal_question_skeneton

def normalize_answer(answer: Any) -> str:
    """
    Normalizes answer format by removing brackets, quotes, etc.
    
    Args:
        answer: The answer to normalize
        
    Returns:
        str: The normalized answer
    """
    if isinstance(answer, (list, tuple)):
        return str(answer).strip('[]()').replace("'", "").replace('"', '')
    
    answer_str = str(answer)
    if answer_str.startswith("[") and answer_str.endswith("]"):
        return answer_str.strip('[]()').replace("'", "").replace('"', '')
    
    return str(answer)

def advanced_matching(model_answer: str, expected_answer: str) -> bool:
    """
    Performs advanced matching for different content types
    
    Args:
        model_answer: The normalized model answer
        expected_answer: The normalized expected answer
        
    Returns:
        bool: Whether the answers match
    """
    if model_answer.lower() == expected_answer.lower():
        return True
    
    numeric_model_answer = model_answer.replace(',', '')
    numeric_expected_answer = expected_answer.replace(',', '')
    
    try:
        if float(numeric_model_answer) == float(numeric_expected_answer):
            return True
    except ValueError:
        pass
    
    model_numbers = extract_numbers(model_answer)
    expected_numbers = extract_numbers(expected_answer)
    
    if model_numbers and expected_numbers:
        if len(model_numbers) == len(expected_numbers):
            all_numbers_match = all(
                abs(model_num - expected_num) < 0.0001
                for model_num, expected_num in zip(model_numbers, expected_numbers)
            )
            
            if all_numbers_match:
                model_text = re.sub(r'[\d.,]+', '', model_answer).strip()
                expected_text = re.sub(r'[\d.,]+', '', expected_answer).strip()
                
                if model_text.lower() == expected_text.lower():
                    return True
    
    model_date = try_parse_date(model_answer)
    expected_date = try_parse_date(expected_answer)
    
    if model_date and expected_date:
        return model_date == expected_date
    
    return False

def extract_numbers(text: str) -> List[float]:
    """
    Extracts numbers from a string
    
    Args:
        text: The text to extract numbers from
        
    Returns:
        list: The extracted numbers
    """
    matches = re.findall(r'[-+]?[\d,]*\.?\d+', text)
    return [float(match.replace(',', '')) for match in matches] if matches else []

def try_parse_date(text: str) -> Union[datetime.datetime, None]:
    """
    Attempts to parse a string as a date
    
    Args:
        text: The text to parse as a date
        
    Returns:
        datetime or None: The parsed date or None if parsing failed
    """
    try:
        return date_parse(text, fuzzy=True)
    except (ValueError, TypeError):
        return None

class TableUtils:
    """
    Table processing utility class providing answer matching, confidence calculation and table formatting functions
    """
    @staticmethod
    def is_answer_correct(model_answer: str, expected_answer: Any) -> bool:
        """
        Matches a model answer against an expected answer with various normalization steps
        
        Args:
            model_answer: The answer provided by the model (with <Answer></Answer> tags)
            expected_answer: The correct answer to check against
            
        Returns:
            bool: Whether the answers match
        """
        answer_regex = r'<Answer>([\s\S]*?)<\/Answer>'
        match = re.search(answer_regex, model_answer)
        
        if not match:
            return False
        
        extracted_answer = match.group(1).strip()
        
        normalized_model_answer = normalize_answer(extracted_answer)
        normalized_expected_answer = normalize_answer(expected_answer)
        
        if normalized_model_answer == normalized_expected_answer:
            return True
        
        return advanced_matching(normalized_model_answer, normalized_expected_answer)
        
    @staticmethod
    def calculate_confidence(data_list):
        """
        Calculate model answer confidence (accuracy rate)
        
        Args:
            data_list (list): List of dictionaries containing questions, LLM answers and correct answers
        
        Returns:
            float: Accuracy rate (correct answers / total questions)
        """
        correct_count = 0
        total = len(data_list)
        
        for entry in data_list:
            llm_answer = entry.get('LLM_final_answer') or entry.get('LLM_answer')
            
            true_answer_str = entry['True_answer']
            try:
                true_answer = ast.literal_eval(true_answer_str)
            except:
                print(f"Format error in correct answer: {true_answer_str}")
                continue
            
            if TableUtils.is_answer_correct(llm_answer, true_answer):
                correct_count += 1
        
        return correct_count / total if total > 0 else 0.0

    @staticmethod
    def table2format(table):
        """
        Convert table data to Markdown format
        
        Args:
            table (dict): Table data dictionary containing header and rows
        
        Returns:
            str: Formatted Markdown table
        """
        header = ' | '.join(table['header'])
        separator = ' | '.join(['---'] * len(table['header']))

        rows = [' | '.join(row) for row in table['rows']]

        formatted_table = '\n'.join([header, separator] + rows)
        return formatted_table

    @staticmethod   
    def generate_table_structure(headers, sample_rows):
        """
        Generate table_structure based on table headers and first few rows
        
        Args:
            headers (list): List of table column names
            sample_rows: First few rows
            
        Returns:
            dict: Dictionary containing generated table_structure
        """
        def build_table_structure_prompt(headers, sample_rows):
            prompt = (f"""You are a table analysis expert. Given the table headers and a few sample rows, infer the **semantic data type** of each column.

            Please return only a JSON array of data types corresponding to the column order.

            ### Example 1:
            - **Table Header:** ["Year", "Division", "League", "Regular Season", "PlayOffs", "Open Cup", "Avg. Attendance"]
            - **Sample values for each column (first row):** ["2001", "2", "USL A-League", "4th, Western", "Quarterfinals", "Did not qualify", "7,169"]
            - **table structure:** ["date", "int", "string", "string", "string", "string", "int"]

            ### Example 2:
            - **Table Header:** ["Time", "Name", "Country", "Rank", "Promotion", "Avg. Score"]
            - **Sample values for each column (first row):** ["5:02:84", "James", "UK", "3", "False", "98.3245"]
            - **table structure:** ["date", "string", "string", "int", "boolean", "float"]

            You can choose from the following types:
            ["string", "int", "float", "date", "boolean"]

            **Table Header:** {headers}

            **Sample values for each column (first row):** {sample_rows}

            **table structure:**
            """)
            return prompt

        try:
            client = OpenAIClient()
            
            prompt_text = build_table_structure_prompt(headers, sample_rows)
            
            messages = [
                {"role": "system", "content": "You are a table analysis expert. Given the table headers and a few sample rows, infer the **semantic data type** of each column."},
                {"role": "user", "content": prompt_text}
            ]
            
            response = client.get_llm_response(messages)
            
            return response
                
        except Exception as e:
            print(f"Error generating table structure: {e}")
            return {"error": str(e)}

    @staticmethod
    def match_similar_data_processor(user_question, user_table):
        """
        Similar data matching processor
        
        Args:
            user_question (str): User question
            user_table (dict): User table data containing header and rows
            
        Returns:
            dict: Dictionary containing matching results
        """
        results = {}

        def run_generate_sql_skeleton():
            return generate_sql_skeleton(user_question)

        def run_get_table_structure_from_api():
            return get_table_structure_from_api(user_table)

        def run_deal_question_skeneton():
            return deal_question_skeneton(user_question, user_table)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_sql = executor.submit(run_generate_sql_skeleton)
            future_table_structure = executor.submit(run_get_table_structure_from_api)
            future_question_skeleton = executor.submit(run_deal_question_skeneton)

            sql_skeleton_result = future_sql.result()
            print("SQL Skeleton generation completed")
            
            table_structure_result = future_table_structure.result()
            print("Table Structure generation completed")
            
            question_skeleton_result = future_question_skeleton.result()
            if isinstance(question_skeleton_result, tuple) and len(question_skeleton_result) == 2:
                question_skeleton_embedding, question_skeleton = question_skeleton_result
                print("Question Skeleton Embedding generation completed")
            else:
                question_skeleton_embedding = question_skeleton_result
                question_skeleton = ""
                print("Question Skeleton generation completed (embedding only)")

            results['sql_skeleton'] = sql_skeleton_result
            results['table_structure'] = table_structure_result
            results['question_skeleton_embedding'] = question_skeleton_embedding
            results['question_skeleton'] = question_skeleton

        return results
        
        
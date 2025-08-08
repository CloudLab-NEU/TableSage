from db.db_manager import DatabaseManager
from openai_api.openai_client import OpenAIClient
from utils.utils import TableUtils
from core_progress.search_similar_question import string_similarity

class FinalAnswerProcessor:
    """
    Final answer processor, responsible for processing user's actual questions and providing answers
    Determines different answering strategies based on learning records and error records
    """
    def __init__(self):
        """Initialize the final answer processor"""
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClient()
        self.table_utils = TableUtils()
    
    def process_final_answer(self, user_question, user_table, similar_questions, is_training=False, true_answer=None):
        """
        Process user question and generate final answer
        
        Args:
            user_question (str): User's question
            user_table (dict): User's table data
            similar_questions (list): List of most similar questions containing table_id
            is_training (bool): Whether it's training phase
            true_answer (str): True answer for training phase (optional)
            
        Returns:
            dict: Dictionary containing final answer and related information
        """
        formatted_user_table = self.table_utils.table2format(user_table)
        
        learning_record_info = self._find_learning_record(similar_questions)
        
        error_record_info = self._find_similar_error_record(user_question)
        
        answer_result = self._generate_answer_by_context(
            user_question, 
            formatted_user_table,
            learning_record_info,
            error_record_info
        )
        
        if is_training and true_answer is not None:
            self._handle_training_result(
                user_question, 
                user_table, 
                answer_result["answer"], 
                true_answer
            )
        
        return answer_result
    
    def _find_learning_record(self, similar_questions):
        """
        Find learning records (flag=1) from similar questions
        
        Args:
            similar_questions (list): List of similar question table_ids (sorted by similarity)
            
        Returns:
            dict: Learning record information, returns None if not found
        """
        for table_id in similar_questions:
            learning_record = self.db_manager.get_learning_record(table_id)
            if learning_record and learning_record.get("flag") == 1:
                knowledge = self.db_manager.get_knowledge_by_id(table_id)
                if knowledge:
                    teaching_record = self.db_manager.get_teaching_record(table_id)
                    strategy_type = teaching_record.get("strategy_type", "") if teaching_record else ""
                    
                    return {
                        "table_id": table_id,
                        "knowledge": knowledge,
                        "rethink_summary": learning_record.get("rethink_summary", ""),
                        "strategy_type": strategy_type
                    }
        return None
    
    def _find_similar_error_record(self, user_question):
        """
        Find similar error records (similarity > 0.5)
        
        Args:
            user_question (str): User question
            
        Returns:
            dict: Error record information, returns None if not found
        """
        error_records_cursor = self.db_manager.error_records.find({})
        error_records = list(error_records_cursor)
        
        best_similarity = 0.0
        best_error_record = None
        
        for error_record in error_records:
            error_question = error_record.get("question", "")
            if error_question:
                similarity = string_similarity(user_question, error_question)
                if similarity > 0.5 and similarity > best_similarity:
                    best_similarity = similarity
                    best_error_record = error_record
        
        return best_error_record
    
    def _generate_answer_by_context(self, user_question, formatted_table, learning_record_info, error_record_info):
        """
        Generate answers based on different contexts
        
        Args:
            user_question (str): User question
            formatted_table (str): Formatted table
            learning_record_info (dict): Learning record information
            error_record_info (dict): Error record information
            
        Returns:
            dict: Answer result
        """
        # Case 1: Both learning records and error records
        if learning_record_info and error_record_info:
            learning_context = self._format_learning_context(learning_record_info)
            error_context = self._format_error_context(error_record_info)
            
            return self._answer_with_both_records(
                user_question,
                formatted_table,
                learning_context,
                error_context
            )
        
        # Case 2: Only learning records
        elif learning_record_info:
            learning_context = self._format_learning_context(learning_record_info)
            
            return self._answer_with_learning_record(
                user_question,
                formatted_table,
                learning_context
            )
        
        # Case 3: Only error records
        elif error_record_info:
            error_context = self._format_error_context(error_record_info)
            
            return self._answer_with_error_record(
                user_question,
                formatted_table,
                error_context
            )
        
        # Case 4: Neither learning records nor error records
        else:
            return self._direct_answer(user_question, formatted_table)
    
    def _format_learning_context(self, learning_record_info):
        """
        Format learning record context
        
        Args:
            learning_record_info (dict): Learning record information
            
        Returns:
            str: Formatted learning context
        """
        knowledge = learning_record_info["knowledge"]
        original_question = knowledge.get("question", "")
        original_table = self.table_utils.table2format(knowledge.get("table", {"header": [], "rows": []}))
        strategy_type = learning_record_info["strategy_type"]
        rethink_summary = learning_record_info["rethink_summary"]
        
        return f"""
        ## Strategy Type: {strategy_type}
        
        ## Original Question: {original_question}

        ## Original Table: {original_table}
        
        ## Learning Reflection:
        {rethink_summary}
        """
    
    def _format_error_context(self, error_record_info):
        """
        Format error record context
        
        Args:
            error_record_info (dict): Error record information
            
        Returns:
            str: Formatted error context
        """
        error_question = error_record_info.get("question", "")
        error_table = error_record_info.get("formatted_table", "")
        error_reflection = error_record_info.get("error_reflection", "")
        
        return f"""
        ## Similar Error Question: {error_question}

        ## Similar Error Table: {error_table}
        
        ## Error Analysis:
        {error_reflection}
        """
    
    def _handle_training_result(self, user_question, user_table, model_answer, true_answer):
        """
        Handle training phase answer results
        
        Args:
            user_question (str): User question
            user_table (dict): User table
            model_answer (str): Model answer
            true_answer (str): Correct answer
        """
        is_correct = self.table_utils.is_answer_correct(model_answer, true_answer)
        
        if not is_correct:
            formatted_table = self.table_utils.table2format(user_table)
            error_reflection = self._generate_error_reflection(
                user_question,
                formatted_table,
                model_answer,
                true_answer
            )
            
            error_record = {
                "question": user_question,
                "table": user_table,
                "model_answer": model_answer,
                "true_answer": true_answer,
                "error_reflection": error_reflection
            }
            
            self.db_manager.error_records.insert_one(error_record)
            print(f"Training phase incorrect: Error record saved")
        else:
            print(f"Training phase correct: No processing needed")
    
    def _generate_error_reflection(self, question, formatted_table, model_answer, true_answer):
        """
        Generate error reflection
        
        Args:
            question (str): Question
            formatted_table (str): Formatted table
            model_answer (str): Model answer
            true_answer (str): Correct answer
            
        Returns:
            str: Error reflection
        """
        prompt = f"""
        As an intelligent tutor, generate a comprehensive error analysis for a student who answered a table-based question incorrectly.
        
        Table:
        {formatted_table}
        
        Question:
        {question}
        
        Student's Answer:
        {model_answer}
        
        Correct Answer:
        {true_answer}
        
        Please provide a detailed error analysis that includes:
        
        ## Section 1: Error Identification
        - What specific mistake did the student make?
        - Which part of the table data was misinterpreted or overlooked?
        
        ## Section 2: Correct Approach
        - What is the correct way to approach this question?
        - Which table columns and rows should be focused on?
        - What logical steps should be followed?
        
        ## Section 3: Learning Points
        - What key concepts should the student review?
        - How can similar mistakes be avoided in the future?
        - What patterns or strategies should be remembered?
        
        Format your response as a structured analysis with the three sections clearly separated.
        """
        
        messages = [{"role": "user", "content": prompt}]
        error_reflection = self.openai_client.get_llm_response(messages,model="gpt-4o")
        
        return error_reflection
    
    def _direct_answer(self, question, formatted_table):
        """
        Answer questions directly without using any historical records
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table
            
        Returns:
            dict: Dictionary containing answer
        """
        prompt = f"""
        ### Task:
        You are given a table and a question. Your goal is to provide accurate answers based solely on the information in the table.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}
          
        ### Instructions:
        1. Carefully review the table structure, including headers and rows.
        2. Identify the relevant data needed to answer the question and use the exact cell value(s) from the table to answer the question.
        3. Carefully read the question to understand what type of answer is expected:
           - **Value-based questions**: Extract specific data from table.
           - **Yes/No questions**: Find values, then judge with 'yes'/'no'.
        
        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        ### Example Answers:
        
        - For the question "scotland played their first match of the 1951 british home championship against which team?", the answer is <Answer>['England']</Answer> .
        - For another question "are there at least 2 nationalities on the chart?", the answer is <Answer>['yes']</Answer>.
        
        <Answer></Answer>
        """
        
        messages = [{"role": "user", "content": prompt}]
        answer = self.openai_client.get_llm_response(messages)
        
        return {
            "answer": answer,
            "context_used": "direct_answer",
        }
    
    def _answer_with_both_records(self, question, formatted_table, learning_context, error_context):
        """
        Answer questions using both learning records and error records
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table
            learning_context (str): Learning context
            error_context (str): Error context
            
        Returns:
            dict: Dictionary containing answer
        """
        prompt = f"""
        ### Task:
        You are given a table and a question. You have both learning guide and error analysis from similar questions to help you answer accurately.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}

        ### Learning Guide from Similar Question:
        {learning_context}

        ### Error Analysis from Similar Question:
        {error_context}
        
        ### Instructions:
        1. Learn from the error analysis to avoid common mistakes.
        2. Apply the successful strategies demonstrated in the learning guide.
        3. Analyze the current table carefully to find the exact answer for this question.

        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        <Answer></Answer>
        """
        
        messages = [{"role": "user", "content": prompt}]
        answer = self.openai_client.get_llm_response(messages)
        
        return {
            "answer": answer,
            "context_used": "both_learning_and_error",
        }
    
    def _answer_with_learning_record(self, question, formatted_table, learning_context):
        """
        Answer questions using only learning records
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table
            learning_context (str): Learning context
            
        Returns:
            dict: Dictionary containing answer
        """
        prompt = f"""
        ### Task:
        You are given a table and a question. You have a learning guide from a similar question to help you apply effective strategies.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}
        
        ### Learning Guide from Similar Question:
        {learning_context}
        
        ### Instructions:
        1. Apply the strategies demonstrated in the learning guide to this question.
        2. Identify the relevant columns and data in the current table.
        3. Extract the specific information needed to answer the question.

        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags

        <Answer></Answer>
        """
        
        messages = [{"role": "user", "content": prompt}]
        answer = self.openai_client.get_llm_response(messages)
        
        return {
            "answer": answer,
            "context_used": "learning_only",
        }
    
    def _answer_with_error_record(self, question, formatted_table, error_context):
        """
        Answer questions using only error records
        
        Args:
            question (str): User question
            formatted_table (str): Formatted table
            error_context (str): Error context
            
        Returns:
            dict: Dictionary containing answer
        """
        prompt = f"""
        ### Task:
        You are given a table and a question. You have an error analysis from a similar question to help you avoid common mistakes.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}

        ### Error Analysis from Similar Question:
        {error_context}
        
        ### Instructions:
        1. Learn from the error analysis to avoid making similar mistakes.
        2. Apply the correct approach suggested in the error analysis.
        3. Carefully analyze the current table to find the accurate answer.

        **MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        <Answer></Answer>
        """
        
        messages = [{"role": "user", "content": prompt}]
        answer = self.openai_client.get_llm_response(messages)
        
        return {
            "answer": answer,
            "context_used": "error_only",
        }
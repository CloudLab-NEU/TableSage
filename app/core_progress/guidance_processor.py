import datetime
import uuid
from db.db_manager import DatabaseManager
from utils.utils import TableUtils
from openai_api.openai_client import OpenAIClient
from core_progress.search_similar_question import string_similarity

class GuidancingProcessor:
    """
    Guidance answering processor, responsible for executing strategic answering process 
    when regular answering confidence is insufficient
    """
    def __init__(self):
        """
        Initialize the guidance answering processor
        """
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClient()
        self.table_utils = TableUtils()
        self.available_strategies = ["cot", "coloumn_sorting", "schema_linking"]

        self.current_session_id = None
        self.current_session_time = None
    
    def process_guidance(self, need_guidance_list, initial_confidence=0.0, total_questions=0):
        """
        Process guidance answering workflow
        
        Args:
            need_guidance_list (list): List containing table_ids that need guidance for incorrect questions
            initial_confidence (float): Confidence from the first round of Q&A
            total_questions (int): Total number of questions from the first round of Q&A
            
        Returns:
            dict: Results of guidance answering
        """
        self.current_session_id = str(uuid.uuid4())
        self.current_session_time = datetime.datetime.now()

        guided_results = []
        updated_records = []
        
        for table_id in need_guidance_list:
            knowledge = self.db_manager.get_knowledge_by_id(table_id)
            
            if not knowledge:
                guided_results.append({
                    "table_id": table_id,
                    "error": "Knowledge not found",
                    "is_correct": False
                })
                continue
            
            existing_learning_record = self.db_manager.get_learning_record(table_id)
            
            result, record_update = self._reteach_problem(
                table_id,
                knowledge,
                existing_learning_record
            )
            
            guided_results.append(result)
            
            if record_update:
                updated_records.append(record_update)
        
        recalculated_confidence = self._recalculate_confidence(
            need_guidance_list, 
            updated_records, 
            initial_confidence, 
            total_questions
        )
        
        return {
            "guided_results": guided_results,
            "updated_records": updated_records,
            "initial_confidence": initial_confidence,
            "recalculated_confidence": recalculated_confidence,
        }
      
    def _reteach_problem(self, table_id, knowledge, existing_learning_record):
        """
        Re-teach a specific problem
        
        Args:
            table_id (str): Table ID
            knowledge (dict): Problem record from knowledge base
            existing_learning_record (dict): Existing learning record (may be None)
            
        Returns:
            tuple: (result dictionary, record update information)
        """
        true_answer = knowledge.get("answer")
        
        existing_flag = existing_learning_record.get("flag") if existing_learning_record else None
        existing_rethink_summary = existing_learning_record.get("rethink_summary", "") if existing_learning_record else ""
        guidance_error_count = existing_learning_record.get("guidance_error_count", 0) if existing_learning_record else 0
        
        optimal_strategy = self.find_optimal_strategy(table_id)
        result = self._try_single_strategy(table_id, knowledge, optimal_strategy)
        
        if result["is_correct"]:
            return self._handle_success_case(
                table_id, knowledge, optimal_strategy, result, 
                existing_flag, existing_rethink_summary
            )
        
        for strategy in self.available_strategies:
            if strategy == optimal_strategy:
                continue
                
            result = self._try_single_strategy(table_id, knowledge, strategy)
            
            if result["is_correct"]:
                return self._handle_success_case(
                    table_id, knowledge, strategy, result,
                    existing_flag, existing_rethink_summary
                )
        
        return self._handle_failure_case(
            table_id, knowledge, true_answer, result["model_answer"],
            existing_flag, existing_rethink_summary, guidance_error_count
        )
    
    def _handle_success_case(self, table_id, knowledge, strategy, result, existing_flag, existing_rethink_summary):
        """
        Handle successful guidance cases
        
        Args:
            table_id (str): Table ID
            knowledge (dict): Knowledge base record
            strategy (str): Successful strategy
            result (dict): Answer result
            existing_flag (int): Existing flag value
            existing_rethink_summary (str): Existing reflection summary
                
        Returns:
            tuple: (result dictionary, record update information)
        """
        existing_teaching_record = self.db_manager.get_teaching_record(table_id)
        existing_strategy = existing_teaching_record.get("strategy_type", "") if existing_teaching_record else ""
        
        need_update = True
        update_reason = ""
        
        if existing_flag == 1 and existing_strategy == strategy and existing_rethink_summary:
            need_update = False
            update_reason = "same_strategy_no_change"
            
            result["rethink_summary"] = existing_rethink_summary
            result["strategy_type"] = strategy
            result["guidance_result"] = update_reason
            return (result, None)
        
        elif existing_flag == 2:
            need_update = True
            update_reason = "flag2_to_flag1"
        
        elif existing_flag == 3 or existing_flag is None:
            need_update = True
            update_reason = "new_success"
        
        else:
            need_update = True
            update_reason = "strategy_change"
        
        if need_update:
            rethink_summary = self._generate_student_reflection(
                knowledge, 
                strategy,
                result["model_answer"]
            )
            
            update_data = {
                "rethink_summary": rethink_summary
            }
            
            if existing_flag == 2 or existing_flag == 3 or existing_flag is None:
                update_data["first_answer_time"] = datetime.datetime.now()
           
            self.db_manager.add_or_update_learning_record(table_id, 1, **update_data)
            
            teaching_record = {
                "table_id": table_id,
                "strategy_type": strategy,
                "session_id": self.current_session_id,
                "created_at": datetime.datetime.now(),
            }
            
            if existing_teaching_record:
                self.db_manager.update_teaching_record(table_id, teaching_record)
            else:
                self.db_manager.add_teaching_record(teaching_record)
            
            result["rethink_summary"] = rethink_summary
            result["strategy_type"] = strategy
            result["guidance_result"] = update_reason
            
            return (result, {"table_id": table_id, "flag": 1})
        
        return (result, None)
    
    def _handle_failure_case(self, table_id, knowledge, true_answer, model_answer, existing_flag, existing_rethink_summary, guidance_error_count):
        """
        Handle guidance failure cases
        
        Args:
            table_id (str): Table ID
            knowledge (dict): Knowledge base record
            true_answer (str): Correct answer
            model_answer (str): Model answer
            existing_flag (int): Existing flag value
            existing_rethink_summary (str): Existing reflection summary
            guidance_error_count (int): Number of guidance errors
            
        Returns:
            tuple: (result dictionary, record update information)
        """
        if existing_flag == 2:
            print(f"Table ID: {table_id} 原先flag=2，重新指导后仍错误，保持原状")
            return ({
                "table_id": table_id,
                "strategies_tried": self.available_strategies,
                "is_correct": False,
                "true_answer": true_answer,
                "model_answer": model_answer,
                "guidance_result": "flag2_no_change",
                "existing_rethink_summary": existing_rethink_summary
            }, None)
            
        elif existing_flag == 1:
            new_guidance_error_count = guidance_error_count + 1
            
            if new_guidance_error_count >= 3:
                error_summary = self._generate_student_error_summary(
                    knowledge,
                    self.available_strategies,
                    true_answer,
                    model_answer
                )
                
                self.db_manager.update_learning_record_with_rethink(table_id, 2, error_summary)
                
                self.db_manager.delete_teaching_record(table_id)
                
                return ({
                    "table_id": table_id,
                    "strategies_tried": self.available_strategies,
                    "is_correct": False,
                    "true_answer": true_answer,
                    "model_answer": model_answer,
                    "guidance_result": "flag1_to_flag2",
                    "error_summary": error_summary,
                    "guidance_error_count": new_guidance_error_count
                }, {"table_id": table_id, "flag": 2})
            else:
                self.db_manager.update_learning_record_guidance_error_count(table_id, new_guidance_error_count)
                
                return ({
                    "table_id": table_id,
                    "strategies_tried": self.available_strategies,
                    "is_correct": False,
                    "true_answer": true_answer,
                    "model_answer": model_answer,
                    "guidance_result": "flag1_error_count_increase",
                    "guidance_error_count": new_guidance_error_count,
                    "existing_rethink_summary": existing_rethink_summary
                }, None)
        
        else:
            error_summary = self._generate_student_error_summary(
                knowledge,
                self.available_strategies,
                true_answer,
                model_answer
            )
            
            self.db_manager.update_learning_record_with_rethink(table_id, 2, error_summary)
            
            return ({
                "table_id": table_id,
                "strategies_tried": self.available_strategies,
                "is_correct": False,
                "true_answer": true_answer,
                "model_answer": model_answer,
                "guidance_result": "new_flag2",
                "error_summary": error_summary
            }, {"table_id": table_id, "flag": 2})
    
    def _try_single_strategy(self, table_id, knowledge, strategy):
        """
        Try single strategy for answering
        
        Args:
            table_id (str): Table ID
            knowledge (dict): Knowledge entry
            strategy (str): Strategy type
            
        Returns:
            dict: Answer result
        """
        true_answer = knowledge.get("answer")
        question = knowledge.get("question", "")
        
        prompt = self._build_strategy_prompt(
            question,
            knowledge, 
            strategy
        )
        
        messages = [{"role": "user", "content": prompt}]
        model_answer = self.openai_client.get_llm_response(messages)
        
        is_correct = self.table_utils.is_answer_correct(model_answer, true_answer)
        
        return {
            "table_id": table_id,
            "strategy_type": strategy,
            "is_correct": is_correct,
            "model_answer": model_answer,
            "true_answer": true_answer
        }
    
    def find_optimal_strategy(self, table_id):
        """
        Find optimal strategy for current problem
        
        Find optimal strategy through the following steps:
        1. Get current question content
        2. Find similar questions from existing teaching records
        3. Count strategy types used by similar questions
        4. Return the most frequently used strategy type
        
        Args:
            table_id (str): Table ID
                
        Returns:
            str: Optimal strategy type
        """
        try:
            current_knowledge = self.db_manager.get_knowledge_by_id(table_id)
            if not current_knowledge or "question" not in current_knowledge:
                print(f"未找到表格 {table_id} 的问题内容")
                return "cot"
            
            current_question = current_knowledge["question"]
            
            guidance_records = self.db_manager.get_guidance_knowledge_with_lookup()
            if not guidance_records:
                print("未找到教学记录")
                return "cot"
                
            similar_records = []
            
            for record in guidance_records:
                if "question" in record:
                    question = record["question"]
                    strategy = record.get("strategy_type", "cot")
                    
                    similarity = string_similarity(current_question, question)
                    
                    similar_records.append({
                        "table_id": record["table_id"],
                        "question": question,
                        "strategy": strategy,
                        "similarity": similarity
                    })
            
            similar_records.sort(key=lambda x: x["similarity"], reverse=True)
            top_similar = similar_records[:5]
            
            if not top_similar:
                print("未找到相似问题")
                return "cot"
                
            print(f"找到 {len(top_similar)} 条相似问题")
            for i, record in enumerate(top_similar):
                print(f"相似问题 {i+1}: {record['question'][:50]}... (相似度: {record['similarity']:.2f}, 策略: {record['strategy']})")
            
            strategy_count = {}
            for record in top_similar:
                strategy = record["strategy"]
                if strategy not in strategy_count:
                    strategy_count[strategy] = 0
                strategy_count[strategy] += 1
                
            max_count = 0
            optimal_strategy = "cot"
            
            for strategy, count in strategy_count.items():
                if count > max_count:
                    max_count = count
                    optimal_strategy = strategy
                    
            print(f"最优策略: {optimal_strategy}, 出现次数: {max_count}")
            return optimal_strategy
            
        except Exception as e:
            print(f"查找最优策略时出错: {str(e)}")
            return "cot"
    
    def _build_strategy_prompt(self, question, knowledge, strategy):
        """
        Build prompt based on specific strategy
        
        Args:
            question (str): Question
            knowledge (dict): Problem record from knowledge base
            strategy (str): Strategy type
            
        Returns:
            str: Built prompt
        """
        formatted_table = self.table_utils.table2format(knowledge["table"])
        cot = knowledge['strategy'].get("cot", "")
        column_sorting = knowledge['strategy'].get("coloumn_sorting", "")
        schema_linking = knowledge['strategy'].get("schema_linking", "")
        
        base_prompt = f"""
        ### Task:
        You are given a table and a question. Your goal is to answer the question using provided strategy, ensuring the answer format matches the provided examples.
        
        ### Table:
        {formatted_table}
        
        ### Question:
        {question}
        """

        example_answers = f"""
        ### Instructions:
        1. Ensure the format of the answer is similar to the provided examples.
        2.**MANDATORY FORMAT REQUIREMENT**: You MUST put the final answer in the placeholder <Answer></Answer>, DO NOT include any explanation, reasoning, or additional text outside the Answer tags
        
        ### Example Answers:
        
        - For the question "scotland played their first match of the 1951 british home championship against which team?", the answer is <Answer>['England']</Answer> .
        - For another question "are there at least 2 nationalities on the chart?", the answer is <Answer>['yes']</Answer>.
        
        <Answer></Answer>
        """

        if strategy == "cot":
            strategy_prompt = f"""
            \n### Chain of Thought Strategy:
            Chain of Thought (CoT) is a reasoning strategy that breaks down complex problems into step-by-step logical processes. This approach helps you systematically analyze the question and identify the exact operations needed to find the answer from the table.

            ### Knowledge of the CoT:
            **Parse the CoT Structure**: The CoT provides a structured breakdown showing:
            - TARGET: What specific information you need to find
            - COLUMNS: Which table columns contain the relevant data
            - CONDITIONS: Any filtering criteria to apply
            - ORDER_BY: How to sort the results
            - LIMIT: The maximum number of results to return

            ### The following is this question's Chain of Thought:
            {cot}
            """
        
        elif strategy == "coloumn_sorting":
            strategy_prompt = f"""
            \n### Column Sorting Strategy:
            Column sorting is a strategy that helps you understand the table structure by organizing and prioritizing columns based on their relevance to the question.

            ### How to Use Column Sorting Strategy:
            1. Understand Column Hierarchy: The sorted columns are arranged in order of importance for answering the specific question
            2. Focus on Key Columns: Start by examining the columns that appear first in the sorted list, as they are most likely to contain the answer
            3. Identify Relevant Data: Look for the specific data points in these columns that directly relate to the questio
        
            ### The following is this question's Column Sorting:
            {column_sorting}
            """
        
        elif strategy == "schema_linking":
            strategy_prompt = f"""
            \n### Schema Linking Strategy:
            This schema linking shows which table columns (indicated in parentheses) are directly relevant to answering the question. 
            For example, if you see "drivers(Driver)", it means the concept "drivers" in the question maps to the "Driver" column in the table.

            ### How to Use Schema Linking Strategy:
            1. Identify Concept Mappings: Look for terms in parentheses that represent actual column names corresponding to concepts in the question
            2. Match Question Terms to Columns: Use the schema linking to understand which table columns directly relate to the concepts mentioned in the question
            3. Focus on Mapped Columns: Prioritize the columns identified in the schema linking as they are most relevant to answering the question

            ### The following is this question's Schema Linking:
            {schema_linking}
            """
        
        return base_prompt + strategy_prompt + example_answers

    def _generate_student_reflection(self, knowledge, strategy, model_answer):
        """
        Generate student reflection summary (when strategy succeeds)
        
        Args:
            knowledge (dict): Problem record from knowledge base
            strategy (str): Strategy used
            model_answer (str): Model answer
            
        Returns:
            str: Generated student reflection summary
        """
        question = knowledge.get("question", "")
        true_answer = knowledge.get("answer", "")
        formatted_table = self.table_utils.table2format(knowledge["table"])
        
        prompt = f"""
        As a student, generate a self-reflection summary about how you successfully solved this table-based question using the {strategy} strategy.
        
        Table:
        {formatted_table}
        
        Question:
        {question}
        
        Your answer:
        {model_answer}
        
        Correct answer:
        {true_answer}
        
        Strategy used: {strategy}
        
        Your self-reflection MUST include exactly three sections:
    
        ## Section 1: Strategy Understanding
        Explain your understanding of the {strategy} strategy and why it was effective for this question.
        
        ## Section 2: Solution Process Reflection
        Reflect on your problem-solving process:
        - How did you identify the key information in the table?
        - What was your logical reasoning step by step?
        - How did the {strategy} strategy guide your thinking?
    
        ## Section 3: Key Learning Points
        Summarize the key insights you gained from solving this question:
        - What did you learn about applying the {strategy} strategy?
        - What patterns or principles can you apply to similar questions?
        
        Format your response as a structured self-reflection with the three sections clearly separated and labeled.
        """
        messages = [{"role": "user", "content": prompt}]
        student_reflection = self.openai_client.get_llm_response(messages)
        
        return student_reflection
    
    def _generate_student_error_summary(self, knowledge, strategies_tried, true_answer, model_answer):
        """
        Generate student error summary (when strategy fails)
        
        Args:
            knowledge (dict): Problem record from knowledge base
            strategies_tried (list): List of strategies attempted
            true_answer (str): Correct answer
            model_answer (str): Model answer

        Returns:
            str: Student error summary
        """
        question = knowledge.get("question", "")
        formatted_table = self.table_utils.table2format(knowledge["table"])
        
        prompt = f"""
        As a student, generate a self-reflection error summary for this question that you consistently answer incorrectly despite trying multiple strategies.
        
        Table:
        {formatted_table}
        
        Question:
        {question}

        Your answer:
        {model_answer}

        Correct answer:
        {true_answer}
        
        Strategies tried: {', '.join(strategies_tried)}
        
        Your error self-reflection MUST include exactly THREE sections:
    
        ## Section 1: Error Analysis 
        Analyze what went wrong in your approach: 
        - Compare your incorrect answer to the correct answer
        - Identify the specific mistakes in your reasoning
        
        ## Section 2: Root Cause Reflection 
        Reflect on the fundamental issues: 
        - What part of the question did you misunderstand?
        - Which concepts or skills are you lacking?
            
        ## Section 3: Improvement Plan
        Create a plan for improvement: 
        - What specific areas do you need to focus on?
        - How will you approach similar questions differently in the future?

        Format your response as a structured error self-reflection with the three sections clearly separated and labeled.
        """
        
        messages = [{"role": "user", "content": prompt}]
        error_summary = self.openai_client.get_llm_response(messages)
        
        return error_summary  
    
    def _recalculate_confidence(self, need_guidance_list, updated_records, initial_confidence=0.0, total_questions=0):
        """
        Recalculate confidence (based on two rounds of Q&A results)
        
        Args:
            need_guidance_list (list): List of table_ids that need guidance
            updated_records (list): Records updated after guidance answering
            initial_confidence (float): Confidence from the first round of Q&A
            total_questions (int): Total number of questions from the first round of Q&A
            
        Returns:
            float: Recalculated confidence
        """
        if total_questions == 0:
            return 0.0
            
        initial_flag_0_count = int(initial_confidence * total_questions)
        
        updated_map = {record["table_id"]: record["flag"] for record in updated_records}
        
        new_flag_0_count = 0
        for table_id in need_guidance_list:
            if table_id in updated_map:
                if updated_map[table_id] == 0:
                    new_flag_0_count += 1
                elif updated_map[table_id] == 1:
                    new_flag_0_count += 1
            else:
                record = self.db_manager.get_learning_record(table_id)
                if record and record.get("flag") == 0:
                    new_flag_0_count += 1
        
        total_flag_0_count = initial_flag_0_count + new_flag_0_count
        final_confidence = total_flag_0_count / total_questions
        
        return final_confidence
    
    # def print_guidance_results(self, guidance_result):
    #     """
    #     Print detailed process and results of guidance answering
        
    #     Args:
    #         guidance_result (dict): Results returned by process_guidance method
    #     """
    #     print("\n" + "="*100)
    #     print("Detailed Guidance Answering Process Results")
    #     print("="*100)
        
    #     guided_results = guidance_result.get("guided_results", [])
    #     updated_records = guidance_result.get("updated_records", [])
    #     recalculated_confidence = guidance_result.get("recalculated_confidence", 0)
        
    #     if not guided_results:
    #         print("No questions need guidance")
    #         return
        
    #     without_teaching_count = 0
    #     success_count = 0
    #     error_count = 0
        
    #     print(f"\n📊 Overall Statistics:")
    #     print(f"Total number of questions needing guidance: {len(guided_results)}")
        
    #     for i, result in enumerate(guided_results, 1):
    #         table_id = result["table_id"]
    #         is_correct = result.get("is_correct", False)
            
    #         knowledge = self.db_manager.get_knowledge_by_id(table_id)
    #         if not knowledge:
    #             print(f"\n❌ Question {i} [Table ID: {table_id}] - Knowledge base data not found")
    #             error_count += 1
    #             continue
            
    #         question = knowledge.get("question", "Unknown question")
    #         true_answer = knowledge.get("answer", "Unknown answer")
    #         model_answer = result.get("model_answer", "Model answer not retrieved")
            
    #         status = "✅ Correct" if is_correct else "❌ Incorrect"
            
    #         print(f"\n{'='*20} Question {i} [Table ID: {table_id}] {status} {'='*20}")
    #         print(f"Question: {question}")
            
            
    #         if "strategies_tried" in result:
    #             without_teaching_count += 1
    #             strategies_tried = result.get("strategies_tried", [])
    #             print(f"🔄 Strategies tried: {', '.join(strategies_tried)}")
                
    #             if is_correct:
    #                 strategy_type = result.get("strategy_type", "Unknown strategy")
    #                 print(f"✅ Successful strategy: {strategy_type}")
    #                 if "teaching_progress" in result:
    #                     print("📝 Generated new student summary record, saved in current learning record database")
    #             else:
    #                 print("❌ All strategies failed")
    #                 error_summary = result.get("error_summary", "")
    #                 if error_summary:
    #                     print("📝 Generated new student reflection record, saved in current learning record database")
            
    #         elif "error" in result:
    #             error_count += 1
    #             print(f"❌ Error: {result['error']}")
            
    #         else:
    #             without_teaching_count += 1
    #             strategy_type = result.get("strategy_type", "Unknown strategy")
    #             print(f"🎯 Strategy used: {strategy_type}")
            
    #         print(f"Model answer: {model_answer}")
    #         print(f"True answer: {true_answer}")
            
    #         if is_correct:
    #             success_count += 1
        
    #     print(f"\n{'='*50} Learning Record Update Status {'='*50}")
    #     if updated_records:
    #         for update in updated_records:
    #             table_id = update["table_id"]
    #             flag = update["flag"]
    #             flag_meaning = {
    #                 0: "Completed and correct",
    #                 1: "Completed but correct under guidance", 
    #                 2: "Incorrect",
    #                 3: "Temporary"
    #             }
    #             print(f"📝 Table ID: {table_id} -> Flag updated to: {flag} ({flag_meaning.get(flag, 'Unknown')})")
    #     else:
    #         print("No learning record updates")
        
    #     print(f"\n{'='*50} Final Statistics {'='*50}")
    #     print(f"New strategies attempted: {without_teaching_count} questions")
    #     print(f"Guidance successful: {success_count} questions")
    #     print(f"Guidance failed/error: {error_count} questions")
        
    #     total_valid = len(guided_results) - error_count
    #     if total_valid > 0:
    #         success_rate = success_count / total_valid * 100
    #         print(f"Guidance success rate: {success_rate:.2f}%")
        
    #     print(f"Final confidence after teaching guidance: {recalculated_confidence:.4f}")
    #     print("="*100)


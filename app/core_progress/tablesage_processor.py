from core_progress.answer_processor import AnsweringProcessor
from core_progress.guidance_processor import GuidancingProcessor
from core_progress.final_processor import FinalAnswerProcessor
from utils.utils import TableUtils
from core_progress.search_similar_question import find_topn_question
from backend_api.config_api import config_params

class TableSageProcessor:
    """
    TableSage core processor that integrates search, answering, guidance and final answer processes
    """
    def __init__(self, confidence_threshold=0.8):
        """
        Initialize TableSage processor
        Args:
            confidence_threshold (float): Confidence threshold, below which strategy answering is required
        """
        self.answer_processor = AnsweringProcessor(confidence_threshold)
        self.guidance_processor = GuidancingProcessor()
        self.final_processor = FinalAnswerProcessor()
        self.table_utils = TableUtils()
        self.confidence_threshold = confidence_threshold

    def process(self, user_question, user_table, is_training=False, true_answer=None,generate_report=False):
        """
        Process user question and return answer
        
        Args:
            user_question (str): User question
            user_table (dict): User table data, containing header and rows
            is_training (bool): Whether in training mode
            true_answer: True answer for training
            generate_report (bool): Whether to generate report
            
        Returns:
            dict: Dictionary containing answer and related information
        """
        try: 
            # Step 1: Search for similar questions          
            question_deal_res = TableUtils.match_similar_data_processor(user_question, user_table)
            similar_questions,_ = find_topn_question(question_deal_res['sql_skeleton'],
                                                     question_deal_res['question_skeleton_embedding'],
                                                     question_deal_res['table_structure'],
                                                     config_params.get('topN', 5))
            
            # Step 2: First round answering using answer_processor
            answer_result = self.answer_processor.process_answering(similar_questions)

            if answer_result.get("processed_results"):
                self.answer_processor._print_detailed_answers(answer_result["processed_results"])

            self.answer_processor.print_answering_results(answer_result)
            
            # Get confidence metrics
            first_confidence = answer_result.get("confidence", 0)
            need_strategy = answer_result.get("need_strategy", False)
            need_guidance_list = answer_result.get("incorrect_table_ids", [])
            total_count = answer_result.get("total_count", 0)
            
            guidance_result = None
            # Step 3: If confidence is below threshold, use guidance_processor for guided answering
            if need_strategy:

                guidance_result = self.guidance_processor.process_guidance(need_guidance_list,first_confidence,total_count)

                self.guidance_processor.print_guidance_results(guidance_result)

                recalculated_confidence = guidance_result.get("recalculated_confidence")

                if recalculated_confidence is not None:
                    confidence = recalculated_confidence
            
                # Step 4: Generate final answer
                final_result = self.final_processor.process_final_answer(
                    user_question,
                    user_table,
                    similar_questions,
                    is_training=is_training,
                    true_answer=true_answer
                )
                
                # Integrate results
                result = {
                    "answer": final_result.get("answer", ""),
                    "context_used": final_result.get("context_used", ""),
                    "confidence": first_confidence,
                    "similar_questions": similar_questions,
                    "flow_path": "guidance" if need_strategy else "direct",
                    "first_answer_results": answer_result,
                    "guidance_result": guidance_result,
                    "user_question": user_question,
                    "user_table": user_table,
                    "true_answer": true_answer,
                    "sql_skeleton": question_deal_res["sql_skeleton"],
                    "question_skeleton": question_deal_res["question_skeleton"],
                }

            else:
                # Special case: if first answer confidence exceeds threshold, directly use model answer   
                final_result = self.final_processor.process_final_answer(
                    user_question,
                    user_table,
                    similar_questions,
                    is_training=is_training,
                    true_answer=true_answer
                )

                # Integrate results
                result = {
                    "answer": final_result.get("answer", ""),
                    "context_used": final_result.get("context_used", ""),
                    "confidence": first_confidence,
                    "similar_questions": similar_questions,
                    "flow_path": "guidance" if need_strategy else "direct",
                    "first_answer_results": answer_result,
                    "guidance_result": guidance_result,
                    "user_question": user_question,
                    "user_table": user_table,
                    "true_answer": true_answer,
                    "sql_skeleton": question_deal_res["sql_skeleton"],
                    "question_skeleton": question_deal_res["question_skeleton"],
                }
            return result
        
        except Exception as e:
            # Error handling
            import traceback
            error_details = traceback.format_exc()
            
            return {
                "error": str(e),
                "error_details": error_details,
                "answer": "An error occurred while processing the question.",
                "context_used": "error",
                "confidence": 0.0,
                "flow_path": "error"
            }
        
    def process_stream(self, user_question, user_table, is_training=False, true_answer=None):
        try:
            yield {"step": "start", "message": "开始处理问题"}
            
            # Step 1: Search for similar questions          
            question_deal_res = TableUtils.match_similar_data_processor(user_question, user_table)
            similar_questions,_ = find_topn_question(question_deal_res['sql_skeleton'],
                                                     question_deal_res['question_skeleton_embedding'],
                                                     question_deal_res['table_structure'],
                                                     config_params.get('topN', 5))
            yield {"step": "similar_search", "similar_questions": similar_questions}

            answer_result = self.answer_processor.process_answering(similar_questions)
            yield {"step": "answering", "answer_result": answer_result}

            first_confidence = answer_result.get("confidence", 0)
            need_strategy = answer_result.get("need_strategy", False)
            need_guidance_list = answer_result.get("incorrect_table_ids", [])
            total_count = answer_result.get("total_count", 0)
            
            guidance_result = None
            if need_strategy:
                yield {"step": "guidance", "message": "置信度不足，进入指导答题"}
                guidance_result = self.guidance_processor.process_guidance(
                    need_guidance_list, first_confidence, total_count
                )
                yield {"step": "guidance_result", "guidance_result": guidance_result}

            final_result = self.final_processor.process_final_answer(
                user_question, user_table, similar_questions,
                is_training=is_training, true_answer=true_answer
            )
            yield {"step": "final", "final_result": final_result}
            
            # Integrate complete results
            complete_result = {
                "answer": final_result.get("answer", ""),
                "context_used": final_result.get("context_used", ""),
                "confidence": first_confidence,
                "similar_questions": similar_questions,
                "flow_path": "guidance" if need_strategy else "direct",
                "first_answer_results": answer_result,
                "guidance_result": guidance_result,
                "user_question": user_question,
                "user_table": user_table,
                "true_answer": true_answer,
                "sql_skeleton": question_deal_res["sql_skeleton"],
                "question_skeleton": question_deal_res["question_skeleton"],
            }
            
            yield {"step": "end", "message": "答题流程结束", "complete_result": complete_result}

        except Exception as e:
            import traceback
            yield {
                "step": "error",
                "error": str(e),
                "error_details": traceback.format_exc()
            }
    
    def generate_result_report(self, complete_result):
        """
        Generate report based on complete results
        
        Args:
            complete_result (dict): Complete processing results
            
        Returns:
            str: Report file path
        """
        try:
            from document_general.document_genral import generate_tablesage_report
            
            user_question = complete_result.get("user_question", "")
            user_table = complete_result.get("user_table", {})
            
            report_path = generate_tablesage_report(user_question, user_table, complete_result)
            return report_path
            
        except Exception as e:
            raise Exception(f"Report generation failed: {str(e)}")